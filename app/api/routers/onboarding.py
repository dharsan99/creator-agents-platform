"""API router for creator onboarding."""
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_session
from app.domain.onboarding.service import OnboardingService
from app.domain.onboarding.agent_deployment import AgentDeploymentService
from app.domain.schemas import (
    OnboardingRequest,
    OnboardingResponse,
    CreatorProfileResponse,
    SyncProfileRequest,
    SyncProfileResponse,
    AgentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
def onboard_creator(
    request: OnboardingRequest,
    session: SessionDep,
):
    """Onboard a creator by fetching their data and generating LLM profile.

    This endpoint:
    1. Fetches creator data from external API (Topmate)
    2. Uses LLM to generate comprehensive, sales-optimized profile documentation
    3. Stores everything in the database
    4. Returns profile highlights

    Args:
        request: Onboarding request with username and optional name/email
        session: Database session

    Returns:
        OnboardingResponse with creator ID, profile ID, and profile highlights

    Raises:
        HTTPException: If creator not found or onboarding fails
    """
    service = OnboardingService(session)

    try:
        logger.info(f"Starting onboarding for username: {request.username}")

        # Onboard the creator
        creator, profile = service.onboard_creator(
            external_username=request.username,
            creator_name=request.name,
            creator_email=request.email,
        )

        # Get the onboarding log to extract processing time
        from app.infra.db.creator_profile_models import OnboardingLog
        from sqlmodel import select, desc

        log_stmt = select(OnboardingLog).where(
            OnboardingLog.external_username == request.username,
            OnboardingLog.status == "completed"
        ).order_by(desc(OnboardingLog.created_at)).limit(1)

        log = session.exec(log_stmt).first()
        processing_time = log.processing_time_seconds if log else 0.0

        logger.info(f"Successfully onboarded {request.username} in {processing_time:.2f}s")

        return OnboardingResponse(
            success=True,
            message=f"Successfully onboarded {request.username}",
            creator_id=creator.id,
            profile_id=profile.id,
            external_username=request.username,
            processing_time_seconds=processing_time,
            llm_summary=profile.llm_summary,
            sales_pitch=profile.sales_pitch,
            services=profile.services,
            value_propositions=profile.value_propositions,
        )

    except ValueError as e:
        logger.error(f"Validation error during onboarding: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error during onboarding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Onboarding failed: {str(e)}"
        )


@router.get("/profile/{creator_id}", response_model=CreatorProfileResponse)
def get_creator_profile(
    creator_id: UUID,
    session: SessionDep,
):
    """Get creator profile by creator ID.

    Args:
        creator_id: Creator UUID
        session: Database session

    Returns:
        CreatorProfileResponse with complete profile data

    Raises:
        HTTPException: If profile not found
    """
    service = OnboardingService(session)

    profile = service.get_creator_profile(creator_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found for creator {creator_id}"
        )

    return CreatorProfileResponse(
        id=profile.id,
        creator_id=profile.creator_id,
        external_username=profile.external_username,
        llm_summary=profile.llm_summary,
        sales_pitch=profile.sales_pitch,
        target_audience_description=profile.target_audience_description,
        value_propositions=profile.value_propositions,
        services=profile.services,
        pricing_info=profile.pricing_info,
        ratings=profile.ratings,
        social_proof=profile.social_proof,
        agent_instructions=profile.agent_instructions,
        objection_handling=profile.objection_handling,
        last_synced_at=profile.last_synced_at,
        created_at=profile.created_at,
    )


@router.post("/sync", response_model=SyncProfileResponse)
def sync_creator_profile(
    request: SyncProfileRequest,
    session: SessionDep,
):
    """Re-sync creator profile with latest data from external API.

    This endpoint:
    1. Fetches latest data from external API
    2. Regenerates LLM profile documentation
    3. Updates the profile in database

    Args:
        request: Sync request with creator ID
        session: Database session

    Returns:
        SyncProfileResponse with updated profile

    Raises:
        HTTPException: If profile not found or sync fails
    """
    service = OnboardingService(session)

    try:
        logger.info(f"Starting profile sync for creator: {request.creator_id}")

        profile = service.sync_creator_profile(request.creator_id)

        logger.info(f"Successfully synced profile for creator {request.creator_id}")

        return SyncProfileResponse(
            success=True,
            message="Profile synced successfully",
            profile=CreatorProfileResponse(
                id=profile.id,
                creator_id=profile.creator_id,
                external_username=profile.external_username,
                llm_summary=profile.llm_summary,
                sales_pitch=profile.sales_pitch,
                target_audience_description=profile.target_audience_description,
                value_propositions=profile.value_propositions,
                services=profile.services,
                pricing_info=profile.pricing_info,
                ratings=profile.ratings,
                social_proof=profile.social_proof,
                agent_instructions=profile.agent_instructions,
                objection_handling=profile.objection_handling,
                last_synced_at=profile.last_synced_at,
                created_at=profile.created_at,
            )
        )

    except ValueError as e:
        logger.error(f"Validation error during sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error during profile sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile sync failed: {str(e)}"
        )


@router.post("/deploy-agent/{creator_id}", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def deploy_sales_agent(
    creator_id: UUID,
    session: SessionDep,
):
    """Deploy a GenericSalesAgent for a creator.

    This endpoint creates and configures a sales agent that will automatically:
    - Reach out to new leads who visit the creator's page
    - Follow up with returning leads
    - Send enrollment messages when leads click on services

    The agent uses the creator's LLM-generated profile (sales pitch, instructions,
    objection handling) to personalize all outreach.

    Args:
        creator_id: Creator UUID
        session: Database session

    Returns:
        AgentResponse with created agent details

    Raises:
        HTTPException: If creator or profile not found
    """
    from app.infra.db.models import Creator

    logger.info(f"Deploying sales agent for creator: {creator_id}")

    # Get creator
    creator = session.get(Creator, creator_id)
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator {creator_id} not found"
        )

    # Get profile
    onboarding_service = OnboardingService(session)
    profile = onboarding_service.get_creator_profile(creator_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found for creator {creator_id}. Please onboard the creator first."
        )

    # Deploy agent
    deployment_service = AgentDeploymentService(session)

    try:
        agent = deployment_service.deploy_sales_agent(creator, profile)

        logger.info(f"Successfully deployed agent {agent.id} for creator {creator_id}")

        return AgentResponse.model_validate(agent)

    except Exception as e:
        logger.error(f"Error deploying agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent deployment failed: {str(e)}"
        )


@router.get("/agents/{creator_id}", response_model=list[AgentResponse])
def list_creator_agents(
    creator_id: UUID,
    session: SessionDep,
):
    """List all agents for a creator.

    Args:
        creator_id: Creator UUID
        session: Database session

    Returns:
        List of AgentResponse objects
    """
    deployment_service = AgentDeploymentService(session)

    agents = deployment_service.get_creator_agents(creator_id)

    return [AgentResponse.model_validate(agent) for agent in agents]
