"""Client for creator-onboarding-service API integration.

This client enables creator-agents-platform to fetch data on-demand from
creator-onboarding-service without database syncing.

Architecture:
- creator-onboarding-service: Owns agent configs and consumer data
- creator-agents-platform: Fetches data as needed via this client
- No data duplication or syncing required
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from pydantic import BaseModel

from app.config import settings


logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent configuration from onboarding service."""
    id: UUID
    creator_id: UUID
    name: str
    implementation: str
    config: Dict[str, Any]
    enabled: bool
    created_at: str


class ConsumerInfo(BaseModel):
    """Consumer information from onboarding service."""
    id: UUID
    creator_id: UUID
    name: Optional[str]
    email: Optional[str]
    whatsapp: Optional[str]
    created_at: str


class CreatorProfile(BaseModel):
    """Enhanced creator profile from onboarding service."""
    id: UUID
    creator_id: UUID
    external_username: str
    llm_summary: Optional[str]
    sales_pitch: Optional[str]
    target_audience_description: Optional[str]
    value_propositions: List[str]
    services: List[Dict[str, Any]]
    agent_instructions: Optional[str]
    objection_handling: Dict[str, str]
    pricing_info: Dict[str, Any]
    ratings: Dict[str, Any]
    social_proof: Dict[str, Any]


class OnboardingServiceClient:
    """Client for interacting with creator-onboarding-service API.

    This client provides methods to fetch agent configurations, consumer data,
    and creator profiles on-demand without requiring database synchronization.

    Usage:
        client = OnboardingServiceClient()
        agent = client.get_agent(agent_id)
        consumers = client.get_agent_consumers(agent_id)
        profile = client.get_creator_profile(creator_id)
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """Initialize the onboarding service client.

        Args:
            base_url: Base URL of the onboarding service API
                      (defaults to settings.ONBOARDING_SERVICE_URL)
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url or settings.onboarding_service_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        logger.info(f"OnboardingServiceClient initialized with base_url: {self.base_url}")

    def __del__(self):
        """Close HTTP client on cleanup."""
        self.client.close()

    def get_agent(self, agent_id: UUID) -> Optional[AgentConfig]:
        """Fetch agent configuration by ID.

        Args:
            agent_id: UUID of the agent

        Returns:
            AgentConfig if found, None otherwise

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/agents/{agent_id}")
            response.raise_for_status()

            data = response.json()
            return AgentConfig(**data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Agent not found: {agent_id}")
                return None
            logger.error(f"Failed to fetch agent {agent_id}: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error fetching agent {agent_id}: {e}", exc_info=True)
            raise

    def get_agent_consumers(self, agent_id: UUID) -> List[ConsumerInfo]:
        """Fetch list of consumers associated with an agent.

        Args:
            agent_id: UUID of the agent

        Returns:
            List of ConsumerInfo objects

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            response = self.client.get(
                f"{self.base_url}/agents/{agent_id}/consumers"
            )
            response.raise_for_status()

            data = response.json()
            return [ConsumerInfo(**consumer) for consumer in data]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Agent not found: {agent_id}")
                return []
            logger.error(f"Failed to fetch consumers for agent {agent_id}: {e}")
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error fetching consumers for agent {agent_id}: {e}",
                exc_info=True
            )
            raise

    def get_creator_profile(self, creator_id: UUID) -> Optional[CreatorProfile]:
        """Fetch enhanced creator profile by creator ID.

        Args:
            creator_id: UUID of the creator

        Returns:
            CreatorProfile if found, None otherwise

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            response = self.client.get(
                f"{self.base_url}/onboarding/profile/{creator_id}"
            )
            response.raise_for_status()

            data = response.json()
            return CreatorProfile(**data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Creator profile not found: {creator_id}")
                return None
            logger.error(f"Failed to fetch creator profile {creator_id}: {e}")
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error fetching creator profile {creator_id}: {e}",
                exc_info=True
            )
            raise

    def get_consumer(self, consumer_id: UUID) -> Optional[ConsumerInfo]:
        """Fetch consumer information by ID.

        Args:
            consumer_id: UUID of the consumer

        Returns:
            ConsumerInfo if found, None otherwise

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/consumers/{consumer_id}")
            response.raise_for_status()

            data = response.json()
            return ConsumerInfo(**data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Consumer not found: {consumer_id}")
                return None
            logger.error(f"Failed to fetch consumer {consumer_id}: {e}")
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error fetching consumer {consumer_id}: {e}",
                exc_info=True
            )
            raise

    def list_agents(
        self,
        creator_id: Optional[UUID] = None,
        enabled_only: bool = True
    ) -> List[AgentConfig]:
        """List agents with optional filtering.

        Args:
            creator_id: Optional filter by creator
            enabled_only: Only return enabled agents

        Returns:
            List of AgentConfig objects

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            params = {}
            if creator_id:
                params["creator_id"] = str(creator_id)
            if enabled_only:
                params["enabled_only"] = "true"

            response = self.client.get(
                f"{self.base_url}/agents",
                params=params
            )
            response.raise_for_status()

            data = response.json()
            return [AgentConfig(**agent) for agent in data]

        except Exception as e:
            logger.error(f"Failed to list agents: {e}", exc_info=True)
            raise

    def health_check(self) -> bool:
        """Check if onboarding service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = self.client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"Onboarding service health check failed: {e}")
            return False


# Singleton instance
_client_instance: Optional[OnboardingServiceClient] = None


def get_onboarding_client() -> OnboardingServiceClient:
    """Get singleton OnboardingServiceClient instance.

    Returns:
        OnboardingServiceClient instance
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = OnboardingServiceClient()

    return _client_instance
