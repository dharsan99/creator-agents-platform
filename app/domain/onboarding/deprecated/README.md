# Deprecated Onboarding Code

**Date:** 2025-12-17
**Reason:** Migrated to supervisor-worker architecture

## What Changed

### Old Architecture (Deprecated)
- Creator onboarding happened in `creator-agents-platform`
- `OnboardingService` fetched external data and stored locally
- `CreatorProfileLLMService` generated LLM profiles locally
- Each creator had a dedicated sales agent deployed

### New Architecture (Current)
- Creator onboarding happens in `creator-onboarding-service` (external)
- This service receives `creator_onboarded` events via Redpanda
- Creator profiles fetched on-demand via `OnboardingServiceClient` (no sync)
- Single global `MainAgent` orchestrates workflows for ALL creators
- Worker agents execute delegated tasks

## Deprecated Files

- **service.py** - `OnboardingService` class
  - Used for local creator onboarding
  - Replaced by: `OnboardingServiceClient` (on-demand fetching)

- **llm_service.py** - `CreatorProfileLLMService` class
  - Used for generating LLM creator profiles
  - Replaced by: Profile generation in `creator-onboarding-service`

- **topmate_client.py** - `TopmateClient` class (if moved here)
  - Used for fetching creator data from Topmate API
  - Replaced by: External API calls in `creator-onboarding-service`

## Migration Path

If you need to reference old onboarding logic:
1. Check `creator-onboarding-service` repository
2. Use `OnboardingServiceClient` for on-demand data fetching
3. Use `MainAgent` for workflow orchestration (not per-creator agents)

## Test Scripts

The following test scripts are outdated and reference deprecated code:
- `scripts/test_onboarding.py`
- `scripts/test_e2e_agent_deployment.py`

These need updating to test the new supervisor-worker architecture.

## Files Kept

- **agent_deployment.py** - Still used for deploying MainAgent
