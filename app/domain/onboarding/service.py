"""Creator onboarding service."""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
import time

from sqlmodel import Session, select

from app.infra.db.models import Creator
from app.infra.db.creator_profile_models import CreatorProfile, OnboardingLog
from app.infra.external.topmate_client import TopmateClient
from app.domain.onboarding.llm_service import CreatorProfileLLMService
from app.domain.schemas import CreatorCreate

logger = logging.getLogger(__name__)


class OnboardingService:
    """Service for onboarding creators with LLM-generated profiles."""

    def __init__(self, session: Session):
        self.session = session
        self.topmate_client = TopmateClient()
        self.llm_service = CreatorProfileLLMService()

    def onboard_creator(
        self,
        external_username: str,
        creator_name: Optional[str] = None,
        creator_email: Optional[str] = None,
    ) -> tuple[Creator, CreatorProfile]:
        """Onboard a creator by fetching and processing their data.

        Args:
            external_username: Topmate username
            creator_name: Optional creator name (fetched if not provided)
            creator_email: Optional creator email (required if name provided)

        Returns:
            Tuple of (Creator, CreatorProfile)

        Raises:
            ValueError: If creator not found or data invalid
            Exception: On processing errors
        """
        start_time = time.time()

        # Create onboarding log
        log = OnboardingLog(
            external_username=external_username,
            status="processing",
        )
        self.session.add(log)
        self.session.commit()

        try:
            logger.info(f"Starting onboarding for {external_username}")

            # Step 1: Fetch data from external API
            logger.info("Fetching data from Topmate API...")
            raw_data = self.topmate_client.fetch_creator_by_username(external_username)

            if not raw_data:
                raise ValueError(f"Creator {external_username} not found on Topmate")

            log.external_api_response = raw_data
            self.session.add(log)
            self.session.commit()

            # Step 2: Extract basic info
            external_user_id = self._extract_user_id(raw_data)
            if not creator_name:
                creator_name = self._extract_name(raw_data)
            if not creator_email:
                # Generate a placeholder email if not provided
                creator_email = f"{external_username}@topmate.io"

            # Step 3: Create or get Creator
            logger.info("Creating/retrieving creator in database...")
            creator = self._create_or_get_creator(
                external_username=external_username,
                name=creator_name,
                email=creator_email,
            )
            log.creator_id = creator.id

            # Step 4: Generate LLM profile
            logger.info("Generating LLM profile document...")
            llm_result = self.llm_service.generate_profile_document(raw_data)
            log.llm_response = llm_result

            # Step 5: Create/Update CreatorProfile
            logger.info("Saving creator profile...")
            profile = self._create_or_update_profile(
                creator_id=creator.id,
                external_user_id=external_user_id,
                external_username=external_username,
                raw_data=raw_data,
                llm_result=llm_result,
            )

            # Complete log
            log.status = "completed"
            log.completed_at = datetime.utcnow()
            log.processing_time_seconds = time.time() - start_time
            self.session.add(log)
            self.session.commit()

            logger.info(
                f"Successfully onboarded {external_username} in "
                f"{log.processing_time_seconds:.2f}s"
            )

            return creator, profile

        except Exception as e:
            logger.error(f"Onboarding failed for {external_username}: {e}")
            log.status = "failed"
            log.error_message = str(e)
            log.completed_at = datetime.utcnow()
            log.processing_time_seconds = time.time() - start_time
            self.session.add(log)
            self.session.commit()
            raise

    def get_creator_profile(
        self,
        creator_id: UUID
    ) -> Optional[CreatorProfile]:
        """Get creator profile by creator ID."""
        statement = select(CreatorProfile).where(
            CreatorProfile.creator_id == creator_id
        )
        return self.session.exec(statement).first()

    def sync_creator_profile(
        self,
        creator_id: UUID
    ) -> CreatorProfile:
        """Re-sync creator profile with latest data from Topmate.

        Args:
            creator_id: Creator ID

        Returns:
            Updated CreatorProfile

        Raises:
            ValueError: If profile not found
        """
        profile = self.get_creator_profile(creator_id)
        if not profile:
            raise ValueError(f"No profile found for creator {creator_id}")

        if not profile.external_username:
            raise ValueError("Profile missing external_username, cannot sync")

        logger.info(f"Syncing profile for {profile.external_username}")

        # Fetch latest data
        raw_data = self.topmate_client.fetch_creator_by_username(
            profile.external_username
        )

        if not raw_data:
            raise ValueError(f"Creator {profile.external_username} not found")

        # Regenerate LLM content
        llm_result = self.llm_service.generate_profile_document(raw_data)

        # Update profile
        profile.raw_data = raw_data
        profile.llm_summary = llm_result["llm_summary"]
        profile.sales_pitch = llm_result["sales_pitch"]
        profile.target_audience_description = llm_result["target_audience_description"]
        profile.value_propositions = llm_result["value_propositions"]
        profile.services = llm_result.get("services", [])
        profile.agent_instructions = llm_result["agent_instructions"]
        profile.objection_handling = llm_result.get("objection_handling", {})
        profile.last_synced_at = datetime.utcnow()
        profile.updated_at = datetime.utcnow()

        # Extract reputation and pricing
        profile.ratings = self._extract_ratings(raw_data)
        profile.social_proof = self._extract_social_proof(raw_data)
        profile.pricing_info = self._extract_pricing(raw_data)

        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)

        return profile

    # ==================== Helper Methods ====================

    def _create_or_get_creator(
        self,
        external_username: str,
        name: str,
        email: str,
    ) -> Creator:
        """Create or get existing creator."""
        # Try to find existing creator by email
        from app.domain.creators.service import CreatorService
        creator_service = CreatorService(self.session)

        existing = creator_service.get_creator_by_email(email)
        if existing:
            logger.info(f"Found existing creator: {existing.id}")
            return existing

        # Create new creator
        logger.info(f"Creating new creator: {name}")
        creator = creator_service.create_creator(
            CreatorCreate(
                name=name,
                email=email,
                settings={
                    "external_username": external_username,
                    "onboarded_at": datetime.utcnow().isoformat(),
                }
            )
        )
        return creator

    def _create_or_update_profile(
        self,
        creator_id: UUID,
        external_user_id: Optional[int],
        external_username: str,
        raw_data: dict,
        llm_result: dict,
    ) -> CreatorProfile:
        """Create or update creator profile."""
        # Check if profile exists
        existing = self.get_creator_profile(creator_id)

        if existing:
            logger.info(f"Updating existing profile for creator {creator_id}")
            profile = existing
        else:
            logger.info(f"Creating new profile for creator {creator_id}")
            profile = CreatorProfile(
                creator_id=creator_id,
                external_user_id=external_user_id,
                external_username=external_username,
            )

        # Update all fields
        profile.raw_data = raw_data
        profile.llm_summary = llm_result["llm_summary"]
        profile.sales_pitch = llm_result["sales_pitch"]
        profile.target_audience_description = llm_result["target_audience_description"]
        profile.value_propositions = llm_result["value_propositions"]
        profile.services = llm_result.get("services", [])
        profile.agent_instructions = llm_result["agent_instructions"]
        profile.objection_handling = llm_result.get("objection_handling", {})
        profile.last_synced_at = datetime.utcnow()
        profile.updated_at = datetime.utcnow()

        # Extract structured data
        profile.ratings = self._extract_ratings(raw_data)
        profile.social_proof = self._extract_social_proof(raw_data)
        profile.pricing_info = self._extract_pricing(raw_data)

        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)

        return profile

    def _extract_user_id(self, raw_data: dict) -> Optional[int]:
        """Extract user ID from raw data."""
        # Try different possible locations
        return raw_data.get("user_id") or raw_data.get("id")

    def _extract_name(self, raw_data: dict) -> str:
        """Extract name from raw data."""
        return (
            raw_data.get("name") or
            raw_data.get("display_name") or
            raw_data.get("username", "Unknown Creator")
        )

    def _extract_ratings(self, raw_data: dict) -> dict:
        """Extract ratings data."""
        return {
            "average_rating": raw_data.get("average_rating", 0),
            "total_ratings": raw_data.get("total_ratings", 0),
            "reviews_count": raw_data.get("reviews_count", 0),
        }

    def _extract_social_proof(self, raw_data: dict) -> dict:
        """Extract social proof elements."""
        return {
            "total_bookings": raw_data.get("total_bookings", 0),
            "followers": raw_data.get("followers", 0),
            "testimonials_count": raw_data.get("testimonials_count", 0),
            "badges": raw_data.get("badges", []),
        }

    def _extract_pricing(self, raw_data: dict) -> dict:
        """Extract pricing information."""
        # This will depend on the structure of raw_data
        # For now, extract from current offering
        pricing = {}
        if "current_offering" in raw_data:
            offering = raw_data["current_offering"]
            if "pricing" in offering:
                pricing = offering["pricing"]
        return pricing
