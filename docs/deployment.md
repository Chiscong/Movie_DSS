# Deployment Guide: Movie DSS Web

This guide walks through every step needed to deploy the Movie Decision Support System to AWS — from running the offline ML pipeline through to a live CloudFront-hosted web application.

---

## Prerequisites

| Requirement | Version / Notes |
|-------------|-----------------|
| Python | 3.11 |
| AWS CLI | Installed and configured (`aws configure`) with a profile that has permissions to create S3 buckets, Lambda functions, API Gateway APIs, CloudFront distributions, and IAM roles |
| pip | Bundled with Python 3.11 |

Install development dependencies from the repository root:

```bash
pip install -r requirements-dev.txt
```

All subsequent commands are run from the **repository root** (`Movie_DSS/`) unless noted otherwise.

---

## Step 1 — Preprocess: Train the ML model

Run the offline preprocessor to clean the dataset and produce the three model artifacts:

```bash
python model/train_model.py
```

Verify the output files were created:

```bash
ls -lh model/vectorizer.pkl model/movie_vectors.pkl model/movies_clean.json
```

Expected output (sizes will vary by dataset size):

```
-rw-r--r-- 1 user user  2.3M model/vectorizer.pkl
-rw-r--r-- 1 user user  18M  model/movie_vectors.pkl
-rw-r--r-- 1 user user  4.1M model/movies_clean.json
```

If the script exits with a non-zero status, read the error message printed to stdout — the most common cause is a missing or unreadable `data/netflix_full.csv`.

---

## Step 2 — Create S3 Buckets

Two buckets are required:

| Bucket | Purpose | Access |
|--------|---------|--------|
| `movie-dss-artifacts` | Stores model artifacts; accessed only by Lambda | Private |
| `movie-dss-frontend` | Stores static frontend files; served via CloudFront OAC | Private (CloudFront OAC only) |

Replace `<REGION>` with your AWS region (e.g., `us-east-1`). **Note:** `us-east-1` does not accept a `LocationConstraint` — omit that flag for that region.

### Create the artifacts bucket (private, all regions except us-east-1)

```bash
aws s3api create-bucket \
  --bucket movie-dss-artifacts \
  --region <REGION> \
  --create-bucket-configuration LocationConstraint=<REGION>
```

### Create the artifacts bucket (us-east-1 only)

```bash
aws s3api create-bucket \
  --bucket movie-dss-artifacts \
  --region us-east-1
```

### Block all public access on the artifacts bucket

```bash
aws s3api put-public-access-block \
  --bucket movie-dss-artifacts \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### Create the frontend bucket (all regions except us-east-1)

```bash
aws s3api create-bucket \
  --bucket movie-dss-frontend \
  --region <REGION> \
  --create-bucket-configuration LocationConstraint=<REGION>
```

### Create the frontend bucket (us-east-1 only)

```bash
aws s3api create-bucket \
  --bucket movie-dss-frontend \
  --region us-east-1
```

### Block all public access on the frontend bucket

CloudFront OAC accesses this bucket directly through IAM; public access is not needed.

```bash
aws s3api put-public-access-block \
  --bucket movie-dss-frontend \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

---

## Step 3 — Upload Model Artifacts to S3

Upload the three artifact files to the `model/` prefix in the artifacts bucket:

```bash
aws s3 cp model/vectorizer.pkl    s3://movie-dss-artifacts/model/vectorizer.pkl
aws s3 cp model/movie_vectors.pkl s3://movie-dss-artifacts/model/movie_vectors.pkl
aws s3 cp model/movies_clean.json s3://movie-dss-artifacts/model/movies_clean.json
```

Verify the uploads:

```bash
aws s3 ls s3://movie-dss-artifacts/model/
```

Expected output:

```
... vectorizer.pkl
... movie_vectors.pkl
... movies_clean.json
```

---

## Step 4 — Build the Lambda Deployment Package

Install backend dependencies into a local `backend/package/` directory, then zip everything together:

```bash
# Install dependencies into the package directory
pip install -r backend/requirements.txt -t backend/package/

# Copy the Lambda handler into the package directory
cp backend/lambda_function.py backend/package/

# Create the zip archive (run from the package directory so paths are at the root of the zip)
cd backend/package
zip -r ../../lambda_deployment.zip .
cd ../..
```

Verify the zip was created:

```bash
ls -lh lambda_deployment.zip
```

> **Note:** `backend/package/` is excluded from version control. Only `lambda_deployment.zip` needs to be uploaded to Lambda. Add `backend/package/` to `.gitignore` if not already present.

---

## Step 5 — Create the Lambda Function

### 5a. Create the IAM execution role

Create a trust policy document:

```bash
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
```

Create the role:

```bash
aws iam create-role \
  --role-name movie-dss-lambda-role \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json
```

Attach the basic Lambda execution policy (CloudWatch Logs):

```bash
aws iam attach-role-policy \
  --role-name movie-dss-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

Create a least-privilege S3 read policy granting only `s3:GetObject` on the model artifacts prefix:

```bash
cat > /tmp/s3-artifacts-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::movie-dss-artifacts/model/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name movie-dss-lambda-role \
  --policy-name S3ArtifactsReadOnly \
  --policy-document file:///tmp/s3-artifacts-policy.json
```

> This role grants **no** `s3:PutObject`, `s3:DeleteObject`, or any other write permission on any S3 resource, satisfying Requirement 7.2.

### 5b. Create the Lambda function

Retrieve the role ARN:

```bash
ROLE_ARN=$(aws iam get-role \
  --role-name movie-dss-lambda-role \
  --query 'Role.Arn' \
  --output text)
echo "Role ARN: $ROLE_ARN"
```

Create the function (wait a few seconds after creating the role for IAM propagation):

```bash
aws lambda create-function \
  --function-name movie-dss-recommender \
  --runtime python3.11 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_deployment.zip \
  --memory-size 512 \
  --timeout 29 \
  --environment "Variables={ARTIFACTS_BUCKET=movie-dss-artifacts,MODEL_PREFIX=model/}"
```

Key configuration:
- **Runtime:** `python3.11`
- **Handler:** `lambda_function.lambda_handler`
- **Memory:** 512 MB
- **Timeout:** 29 s (stays within the API Gateway 29 s integration limit)
- **Environment variables:**
  - `ARTIFACTS_BUCKET` = `movie-dss-artifacts`
  - `MODEL_PREFIX` = `model/` (trailing slash required)

### 5c. Verify the function was created

```bash
aws lambda get-function \
  --function-name movie-dss-recommender \
  --query 'Configuration.[FunctionName,Runtime,MemorySize,Timeout,State]'
```

---

## Step 6 — Create the API Gateway HTTP API

### 6a. Create the HTTP API

```bash
API_ID=$(aws apigatewayv2 create-api \
  --name movie-dss-api \
  --protocol-type HTTP \
  --cors-configuration \
    AllowOrigins='["*"]',AllowMethods='["GET","POST","OPTIONS"]',AllowHeaders='["Content-Type"]' \
  --query 'ApiId' \
  --output text)
echo "API ID: $API_ID"
```

### 6b. Create the Lambda integration

Retrieve the Lambda function ARN:

```bash
LAMBDA_ARN=$(aws lambda get-function \
  --function-name movie-dss-recommender \
  --query 'Configuration.FunctionArn' \
  --output text)
echo "Lambda ARN: $LAMBDA_ARN"
```

Create the integration with a 29 s timeout:

```bash
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id "$API_ID" \
  --integration-type AWS_PROXY \
  --integration-uri "$LAMBDA_ARN" \
  --payload-format-version 2.0 \
  --timeout-in-millis 29000 \
  --query 'IntegrationId' \
  --output text)
echo "Integration ID: $INTEGRATION_ID"
```

### 6c. Create the POST /recommend route

```bash
aws apigatewayv2 create-route \
  --api-id "$API_ID" \
  --route-key "POST /recommend" \
  --target "integrations/$INTEGRATION_ID"
```

### 6d. Deploy the API

```bash
aws apigatewayv2 create-stage \
  --api-id "$API_ID" \
  --stage-name prod \
  --auto-deploy
```

### 6e. Grant API Gateway permission to invoke Lambda

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws lambda add-permission \
  --function-name movie-dss-recommender \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:<REGION>:${ACCOUNT_ID}:${API_ID}/*/*/recommend"
```

### 6f. Note the invoke URL

```bash
aws apigatewayv2 get-api \
  --api-id "$API_ID" \
  --query 'ApiEndpoint' \
  --output text
```

The invoke URL takes the form:
```
https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod
```

The full endpoint for the recommendation route is:
```
https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod/recommend
```

---

## Step 7 — Update `API_URL` in `frontend/app.js`

Open `frontend/app.js` and replace the placeholder on line 7:

```javascript
// Before
const API_URL = 'https://YOUR_API_GATEWAY_URL/recommend';

// After (substitute your actual invoke URL)
const API_URL = 'https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod/recommend';
```

Save the file. This change must be made before uploading the frontend in Step 8.

---

## Step 8 — Upload the Frontend to S3

Sync all frontend files to the frontend bucket, setting a 24-hour cache header:

```bash
aws s3 sync frontend/ s3://movie-dss-frontend/ \
  --cache-control "max-age=86400"
```

Verify the files are present:

```bash
aws s3 ls s3://movie-dss-frontend/
```

Expected output:

```
... index.html
... style.css
... app.js
```

---

## Step 9 — Create the CloudFront Distribution

### 9a. Create an Origin Access Control (OAC)

```bash
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config \
    "Name=movie-dss-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
  --query 'OriginAccessControl.Id' \
  --output text)
echo "OAC ID: $OAC_ID"
```

### 9b. Attach a bucket policy allowing CloudFront OAC to read the frontend bucket

Replace `<ACCOUNT_ID>` with your AWS account ID and `<OAC_ID>` with the value from the previous step:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws s3api put-bucket-policy \
  --bucket movie-dss-frontend \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Effect\": \"Allow\",
        \"Principal\": {
          \"Service\": \"cloudfront.amazonaws.com\"
        },
        \"Action\": \"s3:GetObject\",
        \"Resource\": \"arn:aws:s3:::movie-dss-frontend/*\",
        \"Condition\": {
          \"StringEquals\": {
            \"AWS:SourceArn\": \"arn:aws:cloudfront::${ACCOUNT_ID}:distribution/*\"
          }
        }
      }
    ]
  }"
```

### 9c. Create the distribution

```bash
BUCKET_REGIONAL_DOMAIN="movie-dss-frontend.s3.<REGION>.amazonaws.com"

aws cloudfront create-distribution \
  --distribution-config "{
    \"CallerReference\": \"movie-dss-$(date +%s)\",
    \"Comment\": \"Movie DSS frontend\",
    \"DefaultRootObject\": \"index.html\",
    \"Origins\": {
      \"Quantity\": 1,
      \"Items\": [
        {
          \"Id\": \"movie-dss-frontend-origin\",
          \"DomainName\": \"${BUCKET_REGIONAL_DOMAIN}\",
          \"S3OriginConfig\": { \"OriginAccessIdentity\": \"\" },
          \"OriginAccessControlId\": \"${OAC_ID}\"
        }
      ]
    },
    \"DefaultCacheBehavior\": {
      \"TargetOriginId\": \"movie-dss-frontend-origin\",
      \"ViewerProtocolPolicy\": \"redirect-to-https\",
      \"AllowedMethods\": { \"Quantity\": 2, \"Items\": [\"GET\", \"HEAD\"] },
      \"CachePolicyId\": \"658327ea-f89d-4fab-a63d-7e88639e58f6\"
    },
    \"CustomErrorResponses\": {
      \"Quantity\": 2,
      \"Items\": [
        {
          \"ErrorCode\": 403,
          \"ResponsePagePath\": \"/index.html\",
          \"ResponseCode\": \"200\",
          \"ErrorCachingMinTTL\": 0
        },
        {
          \"ErrorCode\": 404,
          \"ResponsePagePath\": \"/index.html\",
          \"ResponseCode\": \"200\",
          \"ErrorCachingMinTTL\": 0
        }
      ]
    },
    \"PriceClass\": \"PriceClass_100\",
    \"Enabled\": true,
    \"HttpVersion\": \"http2\"
  }"
```

Key settings:
- **Origin:** `movie-dss-frontend` S3 bucket via OAC (no public S3 URL)
- **Viewer protocol policy:** `redirect-to-https` (HTTPS only)
- **Default root object:** `index.html`
- **Custom error responses:** 403 and 404 → `/index.html` with HTTP 200 (preserves SPA routing)
- **Price class:** `PriceClass_100` (North America and Europe edge locations only)

### 9d. Wait for the distribution to deploy and note the domain name

```bash
aws cloudfront list-distributions \
  --query 'DistributionList.Items[?Comment==`Movie DSS frontend`].[DomainName,Status]' \
  --output table
```

Deployment typically takes 5–15 minutes. Once `Status` shows `Deployed`, the site is live at:

```
https://<DISTRIBUTION_DOMAIN>.cloudfront.net
```

---

## Step 10 — Run Smoke Tests

Set the environment variable pointing at the live API endpoint, then run the integration test suite:

```bash
export API_URL="https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod/recommend"
pytest tests/integration/ -v
```

The test suite covers:

| Test | What it checks |
|------|----------------|
| Valid payload → 200 | POST `/recommend` with a complete payload returns `{"status": "success", ...}` |
| Missing genre → 400 | POST `/recommend` without `genre` returns HTTP 400 with an `error` field |
| `top_k=0` → 400 | POST `/recommend` with an out-of-range `top_k` returns HTTP 400 |

All three tests must pass before the deployment is considered complete.

To also validate the CloudFront and S3 security checks (optional):

```bash
export CLOUDFRONT_URL="https://<DISTRIBUTION_DOMAIN>.cloudfront.net"
export ARTIFACTS_BUCKET_URL="https://movie-dss-artifacts.s3.<REGION>.amazonaws.com"
pytest tests/integration/ -v
```

---

## Environment Variable Reference

| Variable | Where used | Example value |
|----------|-----------|---------------|
| `ARTIFACTS_BUCKET` | Lambda environment | `movie-dss-artifacts` |
| `MODEL_PREFIX` | Lambda environment | `model/` |
| `API_URL` | Smoke test runner | `https://<id>.execute-api.<region>.amazonaws.com/prod/recommend` |
| `CLOUDFRONT_URL` | Optional integration test | `https://<domain>.cloudfront.net` |
| `ARTIFACTS_BUCKET_URL` | Optional integration test | `https://movie-dss-artifacts.s3.<region>.amazonaws.com` |

---

## Troubleshooting

**Lambda cold start is slow (>5 s)**
The first invocation downloads model artifacts from S3. Subsequent warm invocations reuse the in-memory cache. Consider enabling Lambda Provisioned Concurrency if cold starts are unacceptable in production.

**API returns HTTP 500 with `{"error": "Internal server error"}`**
Check CloudWatch Logs for the `movie-dss-recommender` log group. The most common causes are:
- The IAM role does not have `s3:GetObject` on `arn:aws:s3:::movie-dss-artifacts/model/*`.
- The `ARTIFACTS_BUCKET` or `MODEL_PREFIX` environment variables are set incorrectly.
- The artifact files were not uploaded to the correct S3 path.

**CloudFront returns 403**
Ensure the S3 bucket policy (Step 9b) is correctly attached and that the OAC ID in the bucket policy matches the one created in Step 9a. Note that it can take a few minutes for CloudFront to propagate the OAC configuration.

**`pytest tests/integration/` skips all tests**
The `API_URL` environment variable is not set. Export it before running pytest:

```bash
export API_URL="https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod/recommend"
```

---

## Updating the Deployment

To update model artifacts after retraining:

```bash
python model/train_model.py
aws s3 cp model/vectorizer.pkl    s3://movie-dss-artifacts/model/vectorizer.pkl
aws s3 cp model/movie_vectors.pkl s3://movie-dss-artifacts/model/movie_vectors.pkl
aws s3 cp model/movies_clean.json s3://movie-dss-artifacts/model/movies_clean.json
```

To update the Lambda function code:

```bash
pip install -r backend/requirements.txt -t backend/package/
cp backend/lambda_function.py backend/package/
cd backend/package && zip -r ../../lambda_deployment.zip . && cd ../..
aws lambda update-function-code \
  --function-name movie-dss-recommender \
  --zip-file fileb://lambda_deployment.zip
```

To update the frontend:

```bash
# Edit frontend/app.js, index.html, or style.css as needed
aws s3 sync frontend/ s3://movie-dss-frontend/ --cache-control "max-age=86400"
# Invalidate the CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id <DISTRIBUTION_ID> \
  --paths "/*"
```
