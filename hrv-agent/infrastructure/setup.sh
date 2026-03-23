#!/usr/bin/env bash
# =============================================================================
# HRV Agent — One-time AWS Infrastructure Setup (Option B: Lambda)
# Run this ONCE before the GitHub Actions CI/CD pipeline can work.
#
# Usage:
#   chmod +x infrastructure/setup.sh
#   AWS_PROFILE=your-profile bash infrastructure/setup.sh
#
# Requirements: AWS CLI v2, jq
# =============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
APP_NAME="hrv-agent"
REGION="${AWS_REGION:-us-west-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "══════════════════════════════════════════════"
echo " HRV Agent — AWS Setup"
echo " Account: $ACCOUNT_ID"
echo " Region:  $REGION"
echo "══════════════════════════════════════════════"

# ── 1. ECR Repository ─────────────────────────────────────────────────────────
echo ""
echo "▶ Creating ECR repository..."

ECR_REPO=$(aws ecr describe-repositories \
    --repository-names "$APP_NAME" \
    --region "$REGION" \
    --query 'repositories[0].repositoryUri' \
    --output text 2>/dev/null || \
  aws ecr create-repository \
    --repository-name "$APP_NAME" \
    --region "$REGION" \
    --image-scanning-configuration scanOnPush=true \
    --query 'repository.repositoryUri' \
    --output text)

echo "  ✅ ECR: $ECR_REPO"

# ── 2. S3 Bucket for Frontend ─────────────────────────────────────────────────
echo ""
echo "▶ Creating S3 bucket for frontend..."

S3_BUCKET="${APP_NAME}-frontend-${ACCOUNT_ID}"

if ! aws s3 ls "s3://$S3_BUCKET" 2>/dev/null; then
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$S3_BUCKET" --region "$REGION"
  else
    aws s3api create-bucket \
      --bucket "$S3_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
fi

# Disable block public access for static hosting
aws s3api put-public-access-block \
  --bucket "$S3_BUCKET" \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Bucket policy — public read
aws s3api put-bucket-policy --bucket "$S3_BUCKET" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Sid\": \"PublicReadGetObject\",
    \"Effect\": \"Allow\",
    \"Principal\": \"*\",
    \"Action\": \"s3:GetObject\",
    \"Resource\": \"arn:aws:s3:::${S3_BUCKET}/*\"
  }]
}"

# Enable static website hosting
aws s3 website "s3://$S3_BUCKET" \
  --index-document index.html \
  --error-document index.html

echo "  ✅ S3: s3://$S3_BUCKET"

# ── 3. CloudFront Distribution ────────────────────────────────────────────────
echo ""
echo "▶ Creating CloudFront distribution..."

CF_ORIGIN="${S3_BUCKET}.s3-website-${REGION}.amazonaws.com"

CF_DIST_ID=$(aws cloudfront create-distribution \
  --origin-domain-name "$CF_ORIGIN" \
  --default-root-object index.html \
  --query 'Distribution.Id' \
  --output text 2>/dev/null || echo "already-exists")

if [ "$CF_DIST_ID" = "already-exists" ]; then
  CF_DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='$CF_ORIGIN'].Id" \
    --output text)
fi

CF_DOMAIN=$(aws cloudfront get-distribution \
  --id "$CF_DIST_ID" \
  --query 'Distribution.DomainName' \
  --output text)

echo "  ✅ CloudFront ID: $CF_DIST_ID"
echo "  ✅ CloudFront Domain: $CF_DOMAIN"

# ── 4. AWS Secrets Manager ────────────────────────────────────────────────────
echo ""
echo "▶ Creating Secrets Manager secret..."

SECRET_NAME="${APP_NAME}/production"

# Read from .env file
if [ ! -f "hrv-agent/.env" ]; then
  echo "  ⚠️  hrv-agent/.env not found. Create it first."
  exit 1
fi

SECRET_VALUE=$(cat hrv-agent/.env | grep -v '^#' | grep -v '^$' | \
  jq -Rs 'split("\n") | map(select(length > 0)) |
  map(split("=") | {(.[0]): (.[1:] | join("="))}) | add')

aws secretsmanager create-secret \
  --name "$SECRET_NAME" \
  --description "HRV Agent production environment" \
  --secret-string "$SECRET_VALUE" \
  --region "$REGION" 2>/dev/null || \
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string "$SECRET_VALUE" \
  --region "$REGION"

SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "$SECRET_NAME" \
  --query 'ARN' \
  --output text \
  --region "$REGION")

echo "  ✅ Secret ARN: $SECRET_ARN"

# ── 5. Lambda IAM Role ────────────────────────────────────────────────────────
echo ""
echo "▶ Creating Lambda IAM role..."

ROLE_NAME="${APP_NAME}-lambda-role"

# Trust policy
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

ROLE_ARN=$(aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" \
  --query 'Role.Arn' \
  --output text 2>/dev/null || \
aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)

# Attach managed policies
for POLICY in \
  "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
  "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"; do
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY" 2>/dev/null || true
done

# Inline policy for Secrets Manager
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "SecretsManagerRead" \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"secretsmanager:GetSecretValue\"],
      \"Resource\": \"$SECRET_ARN\"
    }]
  }"

echo "  ✅ IAM Role ARN: $ROLE_ARN"

# ── 6. API Gateway ────────────────────────────────────────────────────────────
echo ""
echo "▶ Creating API Gateway HTTP API..."

API_ID=$(aws apigatewayv2 create-api \
  --name "${APP_NAME}-api" \
  --protocol-type HTTP \
  --cors-configuration \
    AllowOrigins="*",AllowMethods="GET,POST,OPTIONS",AllowHeaders="Content-Type,X-API-Key" \
  --query 'ApiId' \
  --output text 2>/dev/null || \
aws apigatewayv2 get-apis \
  --query "Items[?Name=='${APP_NAME}-api'].ApiId" \
  --output text)

API_URL=$(aws apigatewayv2 get-api \
  --api-id "$API_ID" \
  --query 'ApiEndpoint' \
  --output text)

echo "  ✅ API Gateway ID: $API_ID"
echo "  ✅ API URL: $API_URL"

# Wait for IAM role to propagate
echo ""
echo "⏳ Waiting 10s for IAM role to propagate..."
sleep 10

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo " ✅ Infrastructure Created Successfully!"
echo "══════════════════════════════════════════════"
echo ""
echo "Add these as GitHub Repository Secrets:"
echo "(Settings → Secrets and variables → Actions → New repository secret)"
echo ""
echo "  AWS_ACCESS_KEY_ID          = (your key)"
echo "  AWS_SECRET_ACCESS_KEY      = (your secret)"
echo "  AWS_REGION                 = $REGION"
echo "  ECR_REPOSITORY             = $ECR_REPO"
echo "  LAMBDA_ROLE_ARN            = $ROLE_ARN"
echo "  S3_BUCKET                  = $S3_BUCKET"
echo "  CLOUDFRONT_DIST_ID         = $CF_DIST_ID"
echo "  API_GATEWAY_ID             = $API_ID"
echo "  VITE_API_URL               = $API_URL"
echo ""
echo "Your frontend will be live at:"
echo "  https://$CF_DOMAIN"
echo ""
echo "Next: commit & push to main → GitHub Actions deploys everything 🚀"
