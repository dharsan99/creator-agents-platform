# End-to-End Workflow Test Guide

This guide explains how to run the complete E2E test for the creator-agents-platform with time compression.

## What Was Built

### 1. Data Clearing Script
**File**: `scripts/clear_creator_data.py`

Clears all data for a specific creator to prepare for testing:
- Consumer contexts, events, actions, agent invocations
- Worker tasks
- Agent triggers and agents
- Consumers
- Creator profiles and onboarding logs
- Creator record

### 2. Time Compression Module
**File**: `app/utils/time_compression.py`

Provides utilities to compress time intervals for rapid testing:
- **7 days → 7 minutes** (1440x speedup)
- **1 day → 1 minute** (1440x speedup)
- **1 hour → 1 second** (3600x speedup)

This allows testing multi-day workflows in minutes instead of waiting days.

### 3. E2E Test Script
**File**: `scripts/test_e2e_workflow_execution.py`

Comprehensive test script that:
1. Verifies creator exists
2. Verifies workflow exists and displays structure
3. Creates 100 test consumers
4. Creates workflow execution
5. Simulates email campaign with time compression
6. Generates realistic engagement metrics (25% open, 10% click, 2% booking)
7. Displays final results and metrics

---

## Prerequisites

### 1. Creator Must Be Onboarded
The creator (Ajay Shenoy) must be onboarded first. If not already done:

```bash
# Run onboarding (if needed)
docker exec creator-agents-api python scripts/test_onboarding.py
```

### 2. Workflow Must Exist
The workflow must exist in the database. If using the workflow ID from the user:
- Workflow ID: `21b7b58a-8f2f-4ecf-b524-3e72a1faccd9`
- Creator ID: `81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3`

To verify workflow exists:
```bash
curl http://localhost:8002/workflows/21b7b58a-8f2f-4ecf-b524-3e72a1faccd9
```

### 3. Services Must Be Running
```bash
# Check services are running
docker ps | grep creator-agents
```

---

## Running the E2E Test

### Step 1: Clear Existing Data (if needed)

```bash
docker exec creator-agents-api python scripts/clear_creator_data.py 81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3
```

**Output**:
```
============================================================
CLEAR CREATOR DATA - E2E TESTING
============================================================

🔍 Found creator: Ajay Shenoy (bastyajay@gmail.com)
⚠️  This will DELETE ALL data for this creator!

📊 Data to be deleted:
  - Consumers: X
  - Events: X
  - ...

✅ Successfully cleared all data for creator: Ajay Shenoy
============================================================
```

### Step 2: Run E2E Test with Time Compression (Recommended)

```bash
docker exec creator-agents-api python scripts/test_e2e_workflow_execution.py \
  81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3 \
  21b7b58a-8f2f-4ecf-b524-3e72a1faccd9 \
  --consumers 100
```

**What Happens**:
1. **Verification** (~5 seconds)
   - Verifies creator exists
   - Verifies workflow exists
   - Displays workflow structure

2. **Consumer Creation** (~10 seconds)
   - Creates 100 test consumers
   - Stores consumer IDs for tracking

3. **Workflow Execution** (~7 minutes with time compression)
   - Creates workflow execution record
   - Iterates through all workflow stages
   - Applies time compression for stage delays
   - Sends emails in batches of 20
   - Simulates realistic engagement:
     - 25% open rate
     - 10% click rate
     - 2% booking rate

4. **Results Display** (~1 second)
   - Shows final metrics
   - Displays conversion rate
   - Confirms test success

**Total Duration**: ~7-8 minutes (compressed from 7 days!)

### Step 3: Run E2E Test WITHOUT Time Compression (Production Simulation)

⚠️ **Warning**: This will take actual days to complete!

```bash
docker exec creator-agents-api python scripts/test_e2e_workflow_execution.py \
  81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3 \
  21b7b58a-8f2f-4ecf-b524-3e72a1faccd9 \
  --consumers 100 \
  --disable-compression
```

---

## Understanding the Output

### Test Start
```
================================================================================
END-TO-END WORKFLOW EXECUTION TEST
================================================================================

📋 Configuration:
   Creator ID: 81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3
   Workflow ID: 21b7b58a-8f2f-4ecf-b524-3e72a1faccd9
   API Base: http://localhost:8002
   Time Compression: ENABLED

⏱️  Time Compression Ratios:
   7 days → 7.0 minutes
   1 day → 1.0 minute
   1 hour → 1.0 second
```

### Stage Execution
```
🎯 Stage: initial_assessment
   Day: 1
   Actions: send_intro_email, track_page_views
   ⏳ Waiting: 0.0 seconds (no delay for first stage)
   📨 Sent emails to 20/100 consumers
   📨 Sent emails to 40/100 consumers
   ...
   📊 Engagement: 25 opens, 10 clicks, 2 bookings
```

### Final Results
```
================================================================================
TEST RESULTS
================================================================================

📊 Workflow Execution Summary:
   Execution ID: abc123...
   Status: completed
   Started: 2025-12-21 23:45:00
   Completed: 2025-12-21 23:52:00
   Duration: 420.00 seconds (7.00 minutes)

📈 Final Metrics:
   consumers_total: 100
   consumers_contacted: 100
   emails_sent: 800  # 8 stages × 100 consumers
   emails_delivered: 800
   emails_opened: 200  # 25% open rate
   emails_clicked: 80  # 10% click rate
   bookings_completed: 16  # 2% booking rate
   conversion_rate: 2.00%

✅ Test completed successfully!
   Total stages executed: 8
   Total consumers: 100
   Conversion rate: 2.00%

================================================================================
🎉 E2E TEST PASSED!
================================================================================
```

---

## Customizing the Test

### Number of Consumers
```bash
# Test with 10 consumers (faster)
docker exec creator-agents-api python scripts/test_e2e_workflow_execution.py \
  <creator_id> <workflow_id> --consumers 10

# Test with 500 consumers (stress test)
docker exec creator-agents-api python scripts/test_e2e_workflow_execution.py \
  <creator_id> <workflow_id> --consumers 500
```

### Time Compression Settings

Edit `.env` file:
```env
# Disable time compression (for production testing)
DISABLE_TIME_COMPRESSION=true
```

Or modify `app/utils/time_compression.py` to adjust ratios:
```python
# Change compression ratios
DAY_TO_MINUTE_RATIO = 1440  # Default: 1 day = 1 minute
HOUR_TO_SECOND_RATIO = 3600  # Default: 1 hour = 1 second
```

---

## Monitoring the Test

### Watch Logs
```bash
# API logs
docker logs -f creator-agents-api

# Database queries
docker exec -it creator-agents-db psql -U postgres -d creator_agents
```

### Check Workflow Execution Status
```bash
# Get workflow execution details
curl http://localhost:8002/workflows/<workflow_id>/executions

# Get specific execution
curl http://localhost:8002/workflows/<workflow_id>/executions/<execution_id>
```

### Check Events
```bash
# Get events for a consumer
curl http://localhost:8002/events?consumer_id=<consumer_id>&limit=100

# Get timeline
curl http://localhost:8002/events/consumer/<consumer_id>/timeline
```

---

## Troubleshooting

### Test Fails at Creator Verification
```
❌ Creator not found: 81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3
```

**Solution**: Run onboarding first:
```bash
docker exec creator-agents-api python scripts/test_onboarding.py
```

### Test Fails at Workflow Verification
```
❌ Workflow not found: 21b7b58a-8f2f-4ecf-b524-3e72a1faccd9
```

**Solution**: Check if workflow exists in database:
```bash
docker exec -it creator-agents-db psql -U postgres -d creator_agents -c \
  "SELECT id, purpose, workflow_type FROM workflows WHERE creator_id = '81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3';"
```

If no workflow exists, you need to create one (likely via creator-onboarding-service wizard).

### Test Runs Too Slowly
- Check that time compression is enabled (should see "Time Compression: ENABLED")
- Verify `.env` doesn't have `DISABLE_TIME_COMPRESSION=true`
- Check system resources (CPU, memory)

### Missing Tools Warning
```
⚠️  Missing Tools:
   - send_sms (priority: high)
```

This is expected. The test script logs missing tools but continues execution using available tools.

---

## What's Next

After successful E2E test:

1. **Review Metrics**: Check conversion rates and engagement
2. **Analyze Workflow**: Review which stages performed best
3. **Iterate Workflow**: Main agent can update workflow based on metrics
4. **Scale Testing**: Test with more consumers (500, 1000+)
5. **Production Deployment**: Deploy with real consumers

---

## Architecture Overview

```
Test Script
    ↓
Creates Consumers (100)
    ↓
Creates WorkflowExecution
    ↓
For each Workflow Stage:
    ├── Wait (with time compression)
    ├── Send Emails (batches of 20)
    ├── Create EMAIL_DELIVERED events
    ├── Simulate Engagement (opens, clicks, bookings)
    ├── Create EMAIL_OPENED/CLICKED/BOOKING_CREATED events
    ├── Update Metrics
    └── Move to next stage
    ↓
Display Results
```

---

## Files Created

1. **`scripts/clear_creator_data.py`** - Clear all creator data
2. **`app/utils/time_compression.py`** - Time compression utilities
3. **`app/utils/__init__.py`** - Utils package initialization
4. **`scripts/test_e2e_workflow_execution.py`** - Main E2E test script
5. **`E2E_TEST_GUIDE.md`** - This guide

---

## Key Features

✅ **Time Compression** - Test 7-day workflows in 7 minutes
✅ **Realistic Engagement** - 25% open, 10% click, 2% booking rates
✅ **Batch Processing** - Emails sent in batches of 20
✅ **Comprehensive Metrics** - Track all engagement metrics
✅ **Stage-by-Stage Execution** - Follows workflow structure
✅ **Event Generation** - Creates realistic event timeline
✅ **Flexible Configuration** - Customize consumers, compression, etc.

---

## Contact & Support

For issues or questions:
- Check logs: `docker logs creator-agents-api`
- Review workflow: `curl http://localhost:8002/workflows/<workflow_id>`
- Check database: `docker exec -it creator-agents-db psql ...`
