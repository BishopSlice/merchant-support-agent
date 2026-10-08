#!/usr/bin/env bash
# Deploy the demo to Google Cloud Run, set up to cost nothing while nobody visits.
# Prepared, not yet run: hosting needs Vikrant's go-ahead, his own `gcloud auth login`,
# and a project with billing. Run from the repo root:  PROJECT_ID=my-project deploy/cloudrun.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"     # a Tier 1 (cheapest) region
SERVICE="${SERVICE:-merchant-support-agent}"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

# Secrets live in Secret Manager, never in the image or the repo. Each value is typed in
# (hidden) by the person running this; nothing is read from .env.
for name in gemini-api-key access-code ops-code; do
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    read -r -s -p "Value for secret $name: " value; echo
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic
  fi
done

# The service runs as the default compute service account, which needs to read the secrets.
NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
for name in gemini-api-key access-code ops-code; do
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${NUMBER}-compute@developer.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor >/dev/null
done

# Builds the Dockerfile with Cloud Build and deploys it.
#   --min-instances 0      scale to zero: no instance (and no charge) when nobody visits
#   --max-instances 1      one instance at most: caps cost, and keeps the in-memory session
#                          and daily message caps consistent
#   --cpu-throttling       request-based billing: CPU is billed only while a request runs
#   --cpu-boost            extra CPU during start-up only, to shorten cold starts
#   --memory 512Mi         the app peaks at about 85 MiB locally; room for sessions in /tmp
#   --concurrency 20       one instance serves up to 20 requests at once
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --cpu 1 \
  --memory 512Mi \
  --concurrency 20 \
  --cpu-throttling \
  --cpu-boost \
  --timeout 120 \
  --set-env-vars "MODEL_NAME=gemini-3.6-flash,GRADER_MODEL=gemini-3.6-flash,SECURE_COOKIES=1,SESSION_CAP=30,DAILY_CAP=400,GRADING_DAILY_BUDGET_USD=0.50" \
  --set-secrets "GOOGLE_API_KEY=gemini-api-key:latest,ACCESS_CODE=access-code:latest,OPS_CODE=ops-code:latest"

gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
