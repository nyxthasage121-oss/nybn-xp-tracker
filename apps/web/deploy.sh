#!/bin/bash
# NYbN XP Tracker — Google Cloud Run Deployment Script
# Run this after completing the one-time GCP setup below.
#
# ============================================================
# ONE-TIME GCP SETUP (do these steps first, only once):
# ============================================================
#
# 1. Install Google Cloud CLI:
#      https://cloud.google.com/sdk/docs/install-sdk#windows
#
# 2. Log in and create/select a project:
#      gcloud auth login
#      gcloud projects create nybn-xp-tracker --name="NYbN XP Tracker"
#      gcloud config set project nybn-xp-tracker
#
#    NOTE: If "nybn-xp-tracker" is taken, pick a unique name and update
#    PROJECT_ID below.
#
# 3. Enable required APIs (free):
#      gcloud services enable run.googleapis.com
#      gcloud services enable artifactregistry.googleapis.com
#      gcloud services enable secretmanager.googleapis.com
#
# 4. Create Artifact Registry repo (stores Docker images):
#      gcloud artifacts repositories create nybn-repo \
#        --repository-format=docker \
#        --location=us-central1
#
# 5. Configure Docker to push to Artifact Registry:
#      gcloud auth configure-docker us-central1-docker.pkg.dev
#
# 6. Create secrets in GCP Secret Manager (run each line once):
#      echo -n "your-random-secret-key"    | gcloud secrets create nybn-flask-secret       --data-file=-
#      echo -n "your-discord-client-id"   | gcloud secrets create nybn-discord-client-id   --data-file=-
#      echo -n "your-discord-client-secret" | gcloud secrets create nybn-discord-client-secret --data-file=-
#      echo -n "your-discord-id-here"     | gcloud secrets create nybn-discord-allowed-ids --data-file=-
#      echo -n "libsql+https://your-db.turso.io?authToken=xxx" | gcloud secrets create nybn-database-url --data-file=-
#      echo -n "your-turso-auth-token"    | gcloud secrets create nybn-turso-auth-token    --data-file=-
#      echo -n "any-random-string"        | gcloud secrets create nybn-web-app-api-token   --data-file=-
#
# 7. Grant Cloud Run access to read secrets:
#      PROJECT_NUMBER=$(gcloud projects describe nybn-xp-tracker --format="value(projectNumber)")
#      gcloud secrets add-iam-policy-binding nybn-flask-secret \
#        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
#        --role="roles/secretmanager.secretAccessor"
#      # Repeat the above for each secret name listed in step 6.
#
# ============================================================
# After the above, run this script to deploy (or re-deploy):
#   bash deploy.sh   (from Git Bash or WSL)
# ============================================================

set -e

PROJECT_ID="nybn-xp-tracker"
REGION="us-central1"
SERVICE_NAME="nybn-xp-tracker"
REPO="us-central1-docker.pkg.dev/${PROJECT_ID}/nybn-repo"
IMAGE="${REPO}/${SERVICE_NAME}:latest"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "==> Building Docker image (linux/amd64 for Cloud Run)..."
docker build \
  --platform linux/amd64 \
  -f "${SCRIPT_DIR}/Dockerfile" \
  -t "${IMAGE}" \
  "${REPO_ROOT}"

echo "==> Pushing to Artifact Registry..."
docker push "${IMAGE}"

echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "FLASK_DEBUG=false" \
  --set-env-vars "SHEETS_CACHE_TTL=30" \
  --set-env-vars "SPREADSHEET_ID=" \
  --update-secrets "FLASK_SECRET_KEY=nybn-flask-secret:latest" \
  --update-secrets "DISCORD_CLIENT_ID=nybn-discord-client-id:latest" \
  --update-secrets "DISCORD_CLIENT_SECRET=nybn-discord-client-secret:latest" \
  --update-secrets "ALLOWED_DISCORD_IDS=nybn-discord-allowed-ids:latest" \
  --update-secrets "MODERATOR_DISCORD_IDS=nybn-discord-moderator-ids:latest" \
  --update-secrets "DATABASE_URL=nybn-database-url:latest" \
  --update-secrets "TURSO_AUTH_TOKEN=nybn-turso-auth-token:latest" \
  --update-secrets "WEB_APP_API_TOKEN=nybn-web-app-api-token:latest"

echo ""
echo "==> Deployed! Your app URL:"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)"
echo ""
echo "==> Add this URL as your Discord OAuth redirect URI:"
echo "    https://[your-url]/auth/callback"
echo "    Then update DISCORD_REDIRECT_URI in Cloud Run env vars."
