"""Client for fetching creator data from Topmate API."""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class TopmateClient:
    """Client for Topmate API."""

    BASE_URL = "https://gcp.galactus.run"

    def __init__(self, timeout: int = 30):
        self.client = httpx.Client(timeout=timeout)

    def fetch_creator_by_username(self, username: str) -> Optional[dict]:
        """Fetch creator details by username.

        Args:
            username: Topmate username (e.g., 'ajay_shenoy')

        Returns:
            Dictionary with creator data, or None if not found

        Raises:
            httpx.HTTPError on API errors
        """
        endpoint = f"{self.BASE_URL}/fetchByUsernameAdditionalDetails/"
        params = {"username": username}

        try:
            logger.info(f"Fetching creator data for username: {username}")
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Successfully fetched data for {username}")
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Creator not found: {username}")
                return None
            logger.error(f"HTTP error fetching creator {username}: {e}")
            raise

        except httpx.HTTPError as e:
            logger.error(f"Error fetching creator {username}: {e}")
            raise

    def __del__(self):
        """Close HTTP client."""
        self.client.close()
