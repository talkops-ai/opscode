---
name: cloud-gcp
description: "GCP CLI operations, IAM, GKE, and Cloud Run deployment patterns"
domain: DevOps
compatibility: "gcloud >= 480"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: cloud-gcp
  difficulty: intermediate
---

# Google Cloud Platform Skill

You are an expert GCP cloud engineer. Follow these guidelines for gcloud CLI, IAM, and GCP services.

## IAM & Service Accounts

```bash
# Create a service account
gcloud iam service-accounts create my-sa --display-name="My Service Account"

# Grant roles (use predefined roles, avoid primitive roles)
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:my-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer" \
  --condition='expression=resource.name.startsWith("projects/_/buckets/my-bucket"),title=BucketOnly'
```

- Prefer **predefined roles** over primitive roles (Owner/Editor/Viewer).
- Use **IAM Conditions** to scope access to specific resources.
- Use **Workload Identity Federation** instead of exported service account keys.
- Enable **Organization Policies** for guardrails.

## Key Services

| Service | Use Case |
|---------|----------|
| GKE | Managed Kubernetes |
| Cloud Run | Serverless containers |
| Compute Engine | VMs and managed instance groups |
| Cloud SQL | Managed PostgreSQL/MySQL |
| Cloud Storage | Object storage |
| Pub/Sub | Event streaming |
| Cloud Functions | Serverless functions |
| Artifact Registry | Container and package registry |
| Secret Manager | Secrets storage |

## GKE Patterns

```bash
# Create an Autopilot cluster
gcloud container clusters create-auto my-cluster --region=us-central1

# Get credentials
gcloud container clusters get-credentials my-cluster --region=us-central1

# Deploy with Workload Identity
gcloud iam service-accounts add-iam-policy-binding my-sa@PROJECT.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="serviceAccount:PROJECT.svc.id.goog[NAMESPACE/KSA_NAME]"
```

## Cloud Run

```bash
gcloud run deploy my-service \
  --image=REGION-docker.pkg.dev/PROJECT/REPO/IMAGE:TAG \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="KEY=VALUE" \
  --min-instances=1 \
  --max-instances=10
```

## Security

- Enable VPC Service Controls for data exfiltration prevention.
- Use Secret Manager for secrets — never store in env vars or code.
- Enable Cloud Audit Logs for all services.
- Use Customer-Managed Encryption Keys (CMEK) for sensitive data.
- Enable Binary Authorization for GKE image trust.
