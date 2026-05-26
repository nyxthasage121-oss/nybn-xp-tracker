#!/usr/bin/env bash
# update-staff-access.sh
# Reads ALLOWED_DISCORD_IDS from .env and pushes to GCP Secret Manager,
# then updates the Cloud Run service to pick up the new version.
#
# Usage: ./update-staff-access.sh

set -euo pipefail

GCLOUD="/opt/homebrew/share/google-cloud-sdk/bin/gcloud"
PROJECT="nybn-xp-tracker"
SECRET_STAFF="nybn-discord-allowed-ids"
SECRET_MOD="nybn-discord-moderator-ids"
SERVICE_NAME="nybn-xp-tracker"
REGION="us-central1"

# Read IDs from .env
IDS=$(grep '^ALLOWED_DISCORD_IDS=' .env | cut -d'=' -f2-)
MOD_IDS=$(grep '^MODERATOR_DISCORD_IDS=' .env | cut -d'=' -f2-)

if [ -z "$IDS" ]; then
    echo "❌ Could not find ALLOWED_DISCORD_IDS in .env"
    exit 1
fi

echo "📋 Staff IDs from .env:"
echo "   $IDS"
echo ""
echo "📋 Moderator IDs from .env:"
echo "   ${MOD_IDS:-(empty — all staff treated as Moderators)}"
echo ""

# Push to GCP Secret Manager
echo "🔐 Updating GCP secret '$SECRET_STAFF'..."
echo "$IDS" | $GCLOUD secrets versions add "$SECRET_STAFF" \
    --data-file=- \
    --project="$PROJECT"

if [ -n "$MOD_IDS" ]; then
    echo "🔐 Updating GCP secret '$SECRET_MOD'..."
    echo "$MOD_IDS" | $GCLOUD secrets versions add "$SECRET_MOD" \
        --data-file=- \
        --project="$PROJECT"
fi

echo ""

# Update Cloud Run to pick up the new secret versions
echo "🚀 Updating Cloud Run service '$SERVICE_NAME'..."
$GCLOUD run services update "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT" \
    --update-secrets="ALLOWED_DISCORD_IDS=${SECRET_STAFF}:latest,MODERATOR_DISCORD_IDS=${SECRET_MOD}:latest"

echo ""
echo "✅ Staff access updated and deployed!"
