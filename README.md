# GCE Creator Cloud Run Service

This service, when deployed to Google Cloud Run, provides an HTTP endpoint to trigger the creation of GCE virtual machines across all available European regions.

## Deployment Instructions

To deploy this service, follow the steps below using the `gcloud` CLI.

### 1. Set Environment Variables

First, replace the placeholders and run these commands in your terminal:

```bash
export GCP_PROJECT="[YOUR_GCP_PROJECT_ID]"
export GCP_REGION="[YOUR_DESIRED_REGION]" # e.g., us-central1
export SERVICE_NAME="gce-creator-service"
# The service account needs the "Compute Admin" role (roles/compute.admin)
export SERVICE_ACCOUNT_EMAIL="[YOUR_SERVICE_ACCOUNT_EMAIL]"
```

### 2. Build the Container Image

This command uses Google Cloud Build to build your container image from the source code and store it in the Artifact Registry.

```bash
gcloud builds submit --tag "gcr.io/$GCP_PROJECT/$SERVICE_NAME" .
```

### 3. Deploy to Cloud Run

This command deploys the container to Cloud Run.

**Note:** This command grants public access to the endpoint for easy testing. For production environments, you should remove the `--allow-unauthenticated` flag and configure secure access using IAM.

```bash
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$GCP_PROJECT/$SERVICE_NAME" \
  --platform managed \
  --region "$GCP_REGION" \
  --service-account "$SERVICE_ACCOUNT_EMAIL" \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT" \
  --set-env-vars="INSTANCE_COUNT=2" \
  --allow-unauthenticated
```

### 4. Trigger the Service

Once deployed, you can trigger the instance creation process by sending a POST request to the service's `/create` endpoint. The number at the end of the URL specifies how many instances to create *per zone*.

```bash
# Example: Create 2 instances per zone in the ZONES_TO_TRY list
curl -X POST "$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$GCP_REGION" --format='value(status.url)')/create/2"
```

