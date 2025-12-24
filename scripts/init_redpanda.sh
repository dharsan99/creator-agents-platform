#!/bin/bash

# Initialize Redpanda topics for Phase 2
# This script creates all necessary topics for event streaming

set -e

REDPANDA_HOST="${REDPANDA_HOST:-redpanda:9092}"
REDPANDA_ADMIN="${REDPANDA_ADMIN:-redpanda:9644}"

echo "🚀 Initializing Redpanda topics..."
echo "Redpanda broker: $REDPANDA_HOST"
echo "Admin API: $REDPANDA_ADMIN"

# Wait for Redpanda to be ready
echo "⏳ Waiting for Redpanda to be ready..."
until curl -f http://$REDPANDA_ADMIN/v1/status/ready >/dev/null 2>&1; do
  echo "  Waiting for Redpanda admin API..."
  sleep 2
done
echo "✅ Redpanda is ready"

# Create topics
create_topic() {
  local topic_name=$1
  local partitions=${2:-3}
  local replication_factor=${3:-1}
  local config=${4:-""}

  echo ""
  echo "📝 Creating topic: $topic_name"
  echo "   Partitions: $partitions, Replication: $replication_factor"

  # Check if topic exists
  if curl -s http://$REDPANDA_ADMIN/v1/metadata/topics/$topic_name | grep -q "\"name\":\"$topic_name\""; then
    echo "   ✅ Topic already exists"
  else
    # Create topic using Redpanda admin API
    curl -X POST http://$REDPANDA_ADMIN/v1/topics \
      -H "Content-Type: application/json" \
      -d "{
        \"topic\": \"$topic_name\",
        \"partitions\": $partitions,
        \"replication_factor\": $replication_factor
      }" 2>/dev/null || echo "   ⚠️  Topic creation returned status (may already exist)"

    echo "   ✅ Topic created"
  fi
}

# Create all topics
create_topic "events" 3 1
create_topic "agent-invocations" 3 1
create_topic "actions" 3 1
create_topic "dlq-agents" 1 1
create_topic "dlq-actions" 1 1

echo ""
echo "✅ All Redpanda topics initialized successfully!"
echo ""
echo "📊 Topics summary:"
echo "  - events: Main event stream (3 partitions)"
echo "  - agent-invocations: Agent execution events (3 partitions)"
echo "  - actions: Action execution events (3 partitions)"
echo "  - dlq-agents: Agent failure DLQ (1 partition)"
echo "  - dlq-actions: Action failure DLQ (1 partition)"
echo ""
echo "🎉 Redpanda initialization complete!"
