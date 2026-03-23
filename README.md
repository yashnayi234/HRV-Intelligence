# Deployment Guide — AWS Lambda
## HRV Agentic Intelligence System

**Architecture:** Lambda + API Gateway → CloudFront + S3  
**Cost:** ~$2–3/month + Bedrock pay-per-use  
**Deploy time:** ~8 minutes first deploy, ~4 minutes after

---

## Prerequisites

Install these tools before starting:

```bash
# 1. AWS CLI v2
brew install awscli
aws configure  # Enter your Access Key, Secret, region: us-west-2, output: json

# 2. jq (used by setup.sh)
brew install jq

# 3. Docker Desktop — must be running
open /Applications/Docker.app

# 4. Verify everything works
aws sts get-caller-identity   # Should print your Account ID
docker --version              # Should print version
jq --version                  # Should print version
```

---

## Step 1 — Build the ML model (if not done)

The Lambda image requires the trained model to be present **before** building.

```bash
cd /Users/yashnayi/Desktop/HRV/hrv-agent
source ../venv/bin/activate   # or: /Users/yashnayi/Desktop/HRV/.venv/bin/activate

PYTHONPATH=. python ml/trainer.py \
  "../HRV data 20201209 2.xlsx" \
  ml/models/xgb_hrv_v1.pkl

# Expected: AUC-ROC 0.93, model saved to ml/models/xgb_hrv_v1.pkl
ls -lh ml/models/xgb_hrv_v1.pkl
```

---

## Step 2 — Run the infrastructure setup script (ONCE)

This creates all AWS resources and prints the GitHub Secrets you need.

```bash
cd /Users/yashnayi/Desktop/HRV

# Set your region
export AWS_REGION=us-west-2

# Run setup (takes ~2 minutes)
bash hrv-agent/infrastructure/setup.sh
```

**What this creates:**
- ECR repository (`hrv-agent`)
- S3 bucket for the React frontend
- CloudFront distribution (CDN)
- AWS Secrets Manager secret (copies your .env)
- Lambda IAM role with Bedrock + Secrets Manager permissions
- API Gateway HTTP API

At the end, the script prints a table like:
```
  AWS_ACCESS_KEY_ID          = (your key)
  AWS_SECRET_ACCESS_KEY      = (your secret)
  AWS_REGION                 = us-west-2
  ECR_REPOSITORY             = 123456789.dkr.ecr.us-west-2.amazonaws.com/hrv-agent
  LAMBDA_ROLE_ARN            = arn:aws:iam::123456789:role/hrv-agent-lambda-role
  S3_BUCKET                  = hrv-agent-frontend-123456789
  CLOUDFRONT_DIST_ID         = ABCDEF123456
  API_GATEWAY_ID             = abc123xyz
  VITE_API_URL               = https://abc123xyz.execute-api.us-west-2.amazonaws.com
```

---

## Step 3 — Add GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each value printed above

You need **9 secrets** total (copy exactly from setup.sh output).

---

## Step 4 — Push to GitHub → Auto-deploy

```bash
cd /Users/yashnayi/Desktop/HRV/hrv-agent

git add .
git commit -m "feat: add Lambda deployment infrastructure"
git push origin main
```

GitHub Actions will run automatically:

```
✅ Lint & Test          (~2 min)
✅ Build & Push to ECR  (~4 min)  — Lambda image
✅ Deploy to Lambda     (~1 min)  — create or update
✅ Build React app      (~1 min)  — npm run build
✅ Sync to S3           (~30 sec) — static files
✅ Invalidate CloudFront cache
```

Monitor at: **github.com/yashnayi234/hrv-agent/actions**

---

## Step 5 — Verify the live deployment

Once GitHub Actions shows all green ✅:

```bash
# Your API Gateway URL (from setup.sh output)
API_URL="https://abc123xyz.execute-api.us-west-2.amazonaws.com"

# Health check
curl "$API_URL/health"
# Expected: {"status":"healthy","model_loaded":true}

# Chat with the coach
curl -X POST "$API_URL/chat" \
  -H "X-API-Key: hrv-agent-dev-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is sepsis risk based on HRV?"}'
```

Open your CloudFront dashboard URL in a browser:
```
https://ABCDEF123456.cloudfront.net
```

The full dashboard should load and the AI Coach should respond.

---

## Updating the app after launch

Any push to `main` automatically redeploys:

```bash
# Make your code changes, then:
git add .
git commit -m "fix: improve clinical interpretation"
git push origin main
# → CI/CD runs, Lambda updates in ~4 min
```

---

## Monitoring & Logs

```bash
# View Lambda logs in real-time
aws logs tail /aws/lambda/hrv-agent --follow --region us-west-2

# View Lambda metrics
aws lambda get-function-configuration --function-name hrv-agent

# Lambda invocation stats (last 24h)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=hrv-agent \
  --start-time $(date -v-24H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

---

## Switching to ECS Fargate later (Option A)

When you're ready for always-warm production traffic:

1. Run `infrastructure/setup_fargate.sh` (creates ECS cluster + ALB)
2. Change GitHub Actions workflow: swap `aws lambda update-function-code` for `aws ecs update-service`
3. Zero code changes to the FastAPI app or Dockerfiles

The same ECR image works for both Lambda and ECS Fargate.

---

## Cost Breakdown

| Service | Cost |
|---|---|
| Lambda (1M requests/month) | $0.20 |
| API Gateway (1M calls) | $1.00 |
| CloudFront (1M requests) | $0.85 |
| S3 (static files) | $0.01 |
| CloudWatch Logs | $0.50 |
| ECR storage | $0.10 |
| **Total** | **~$2.66/month** |
| Bedrock Claude Sonnet 4 | ~$0.014/analysis |
