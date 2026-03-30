# Scalable Cloud-based Health Analytics Application

## Project Overview

A cloud-hosted Health Analytics System where users enter health data (steps, heart rate, sleep, meals, exercise) and receive meaningful analytics, insights, and routine stability scores. The system integrates 3 APIs and is deployed on AWS.

---

## Architecture

```
Frontend (Bootstrap 5 + Jinja2 / S3 Static)
        │
        ▼
Flask REST API  ──► AWS SQS (async processing)
        │
        ├──► DynamoDB (health records, user data)
        ├──► AWS Lambda (background processing / FaaS scalability)
        ├──► Classmate API  (Routine Stability Index)
        │    https://2u736o5k8k.execute-api.us-east-1.amazonaws.com/prod
        └──► Public API (Nutritionix / CalorieNinjas — calorie/nutrition data)
```

### Component Locations

| Component | Path |
|-----------|------|
| Flask backend | `backend/app.py` |
| API routes | `backend/routes/` |
| AWS helpers (boto3) | `backend/aws/` |
| Frontend templates | `frontend/templates/` |
| Frontend static assets | `frontend/static/` |
| Deployment scripts | `deploy/` |
| Environment config | `.env` |

---

## AWS Infrastructure

| Resource | Detail |
|----------|--------|
| Region | `eu-north-1` |
| Account ID | `985100584832` |
| EC2 Instance | `t3.micro`, AMI `ami-0cc38fb663faa09c2` (Amazon Linux 2023) |
| Key Pair | `cloud-key-pair` / `cloud-key-pair.pem` |
| DynamoDB | Tables: `HealthUsers`, `HealthRecords` |
| SQS | Queue for async health data processing |
| IAM User | `AdminUser` (Access Key in `.env`) |

All AWS interactions must use **boto3**. Read credentials from environment variables via `python-dotenv` — never hardcode them.

---

## Environment Variables

All secrets and config live in `.env`. Load with `python-dotenv`. Key variables:

```
AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
AMI_ID, INSTANCE_TYPE
EC2_KEY_PAIR_NAME, EC2_KEY_PAIR_FILE
GITHUB_PAT, GITHUB_REPO, GITHUB_USERNAME, GITHUB_EMAIL
```

---

## Backend Conventions (Flask + Python)

- Python 3.11+, Flask, boto3, python-dotenv, requests
- REST API — all responses must be **JSON** with appropriate HTTP status codes
- Follow this response envelope:
  ```json
  { "success": true, "data": { ... } }
  { "success": false, "error": "message" }
  ```
- Use Flask Blueprints for route organisation (`/auth`, `/health`, `/analytics`)
- Authentication: JWT tokens stored client-side; each user owns their own records
- Input validation at every API boundary — reject malformed requests with 400
- Use SQS to queue heavy analytics jobs (do not block the HTTP response)

### DynamoDB Patterns

- `HealthUsers` table — partition key: `user_id` (email)
- `HealthRecords` table — partition key: `user_id`, sort key: `date` (YYYY-MM-DD)
- Health record attributes: `steps`, `heart_rate`, `sleep_hours`, `sleep_time`, `wake_time`, `meals` (list), `exercise` (map), `calories_burned`, `weight_kg`

---

## API Integrations

### 1. Own Health API (this project — Flask)
- Handles CRUD for health records, analytics, summaries
- Endpoints: `POST /api/health`, `GET /api/health`, `PUT /api/health/<date>`, `DELETE /api/health/<date>`
- Analytics: `GET /api/analytics/daily`, `/weekly`, `/monthly`

### 2. Classmate — Routine Stability API
- Base URL: `https://2u736o5k8k.execute-api.us-east-1.amazonaws.com/prod`
- Main endpoint: `POST /api/stability`
- No auth required, CORS open
- Send: `sleep_times`, `wake_times`, `meals`, `exercise` from stored health records
- Returns: `overall_score` (0–100), `label`, `breakdown`, `irregularity_alerts`, `recommendations`
- Time format MUST be 24-hour `HH:MM` — no seconds
- Minimum: 2 sleep entries, 1 meal day, `frequency_per_week` + `duration_minutes` for exercise

### 3. Public API — Calorie / Nutrition
- Use CalorieNinjas (`https://api.calorieninjas.com/v1/nutrition`) or Nutritionix
- Fetch calorie data based on user-entered food/exercise
- Store result in DynamoDB alongside the health record

---

## Frontend Conventions (Bootstrap 5)

- Bootstrap 5 CDN — no build step required
- Chart.js for analytics graphs (line/bar charts for steps, sleep, calories)
- Pages: Login, Register, Dashboard, Add/Edit Health Data, Analytics, History
- Display data date-wise; support daily / weekly / monthly summary views
- All API calls via `fetch()` with JSON body and `Authorization: Bearer <token>` header
- Show loading spinners during API calls; display error toasts on failure

---

## Scalability Requirements

- Use **AWS SQS** to decouple data ingestion from processing
- Backend EC2 should be behind an **Auto Scaling Group** or use **AWS Lambda** for processing workers
- DynamoDB on-demand billing mode (auto-scales)
- No blocking synchronous calls for analytics — queue them and poll or use WebSocket

---

## Build & Deploy

```bash
# Install backend dependencies
pip install -r backend/requirements.txt

# Run locally
cd backend && flask run --port 5000

# Deploy to EC2
bash deploy/deploy.sh

# SSH to EC2
ssh -i cloud-key-pair.pem ec2-user@<EC2_PUBLIC_IP>
```

---

## Code Standards

- Add comments to all functions explaining inputs, outputs, and AWS interactions
- Use `logging` module — not `print` — for server-side logs
- Keep route handlers thin; business logic in `services/` layer
- Never log or expose secret keys, tokens, or passwords
- `.env` is gitignored — never commit it
