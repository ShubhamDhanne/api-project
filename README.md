# HealthTrack — Scalable Cloud-based Health Analytics Application

A cloud-hosted Health Analytics System where users log health data (steps, heart rate, sleep, meals, exercise) and receive meaningful analytics, insights, and a Routine Stability score.

---

## Architecture

```
Bootstrap 5 Frontend (Jinja2 templates)
        │
        ▼
Flask REST API  ──► AWS SQS (async analytics jobs)
        │
        ├──► DynamoDB  (HealthUsers, HealthRecords)
        ├──► AWS Lambda (SQS worker — analytics enrichment)
        ├──► Classmate API — Routine Stability Index
        │    https://2u736o5k8k.execute-api.us-east-1.amazonaws.com/prod
        └──► CalorieNinjas API (nutrition data)
             https://api.calorieninjas.com/v1/nutrition
```

---

## Project Structure

```
health-analytics/
├── backend/
│   ├── app.py                  # Flask application factory
│   ├── config.py               # Configuration from env vars
│   ├── wsgi.py                 # Gunicorn entry point
│   ├── requirements.txt
│   ├── routes/
│   │   ├── auth.py             # POST /api/auth/register|login
│   │   ├── health.py           # CRUD /api/health
│   │   ├── analytics.py        # GET /api/analytics/daily|weekly|monthly|stability
│   │   ├── pages.py            # HTML page routes
│   │   └── middleware.py       # JWT auth_required decorator
│   ├── aws/
│   │   ├── dynamodb.py         # DynamoDB CRUD helpers
│   │   └── sqs.py              # SQS queue helpers
│   └── services/
│       ├── auth_service.py     # bcrypt hashing, JWT
│       ├── health_service.py   # Health CRUD logic
│       ├── analytics_service.py
│       ├── nutrition_service.py  # CalorieNinjas integration
│       └── stability_service.py  # Classmate API integration
├── frontend/
│   ├── templates/              # Jinja2 HTML templates (Bootstrap 5)
│   └── static/
│       ├── css/style.css
│       └── js/                 # Per-page JavaScript files
├── lambda/
│   └── lambda_function.py      # SQS-triggered Lambda worker
├── deploy/
│   ├── setup_ec2.sh            # One-time EC2 bootstrap
│   ├── deploy.sh               # Rolling deploy via SSH
│   └── provision_aws.py        # Create DynamoDB, SQS, Lambda
└── .env                        # Secrets (gitignored)
```

---

## Quick Start (Local)

### 1. Clone the repository
```bash
git clone https://github.com/ShubhamDhanne/api-project.git
cd api-project
```

### 2. Create `.env`
Copy the template:
```env
AWS_REGION=eu-north-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
JWT_SECRET_KEY=change-this-in-production
CALORIE_NINJAS_API_KEY=your_calorieninjas_key   # get free at calorieninjas.com/api
SQS_QUEUE_NAME=health-analytics-queue
```

### 3. Install dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Provision AWS resources (run once)
```bash
cd deploy && python provision_aws.py
```

### 5. Run the app
```bash
cd backend && flask run --port 5000
```
Visit: http://localhost:5000

---

## Deploy to AWS EC2

### First-time setup
```bash
# SSH into your EC2 instance and run:
bash deploy/setup_ec2.sh
```

### Rolling update
```bash
bash deploy/deploy.sh <EC2_PUBLIC_IP>
```

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login → JWT token |

### Health Records (JWT required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/health` | Create record |
| GET | `/api/health` | List all records |
| GET | `/api/health/<date>` | Get single record |
| PUT | `/api/health/<date>` | Update record |
| DELETE | `/api/health/<date>` | Delete record |
| POST | `/api/health/nutrition-lookup` | Calorie lookup via CalorieNinjas |

### Analytics (JWT required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/daily?date=YYYY-MM-DD` | Daily analytics |
| GET | `/api/analytics/weekly?start_date=YYYY-MM-DD` | Weekly summary |
| GET | `/api/analytics/monthly?year=YYYY&month=MM` | Monthly summary |
| GET | `/api/analytics/stability?days=7` | Routine Stability Index |

---

## Integrated APIs

| API | Purpose | Auth |
|-----|---------|------|
| **Own Flask API** | Health CRUD & analytics | JWT Bearer token |
| **Classmate Stability API** | Routine Stability Index (0–100) | None — open CORS |
| **CalorieNinjas** | Nutrition data per food item | `X-Api-Key` header |

---

## AWS Infrastructure

| Resource | Details |
|----------|---------|
| Region | `eu-north-1` |
| EC2 | `t3.micro`, Amazon Linux 2023 |
| DynamoDB | `HealthUsers` (PK: user_id), `HealthRecords` (PK: user_id, SK: date) — on-demand |
| SQS | `health-analytics-queue` — decouples API from analytics compute |
| Lambda | `health-analytics-worker` — SQS-triggered, enriches nutrition data |

---

## Security Notes

- Passwords hashed with **bcrypt** — never stored in plain text
- JWT tokens signed with `JWT_SECRET_KEY` (24h expiry)
- All secrets loaded from `.env` — never hardcoded
- `.env` is gitignored
- Input validated at every API boundary
