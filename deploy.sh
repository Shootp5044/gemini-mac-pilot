#!/bin/bash
# Deploy Mac Pilot Brain to Google Cloud Run
set -e

PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project)}"
REGION="us-central1"
SERVICE_NAME="mac-pilot-brain"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "Deploying Mac Pilot Brain to Cloud Run..."
echo "  Project: ${PROJECT_ID}"
echo "  Region:  ${REGION}"
echo "  Image:   ${IMAGE}"
echo ""

# Build and push container
echo "Building container..."
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" --quiet

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --memory 512Mi \
  --timeout 60 \
  --quiet

# Get the URL
URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --platform managed \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)")

echo ""
echo "Deployed successfully!"
echo "  URL: ${URL}"
echo "  Health: ${URL}/health"
echo "  Task:   curl -X POST ${URL}/task -H 'Content-Type: application/json' -d '{\"task\": \"What day is it?\"}'"
