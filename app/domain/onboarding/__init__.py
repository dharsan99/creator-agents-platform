"""Onboarding domain module.

UPDATED FOR SUPERVISOR-WORKER ARCHITECTURE:
- Creator onboarding happens in creator-onboarding-service (external)
- This module only contains agent deployment logic
- Old onboarding services moved to deprecated/ directory
"""

from app.domain.onboarding.agent_deployment import AgentDeploymentService

__all__ = [
    "AgentDeploymentService",
]
