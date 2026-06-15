# ─────────────────────────────────────────────
# Upload Lambda zip lên S3 artifacts bucket
# (tránh giới hạn 50 MB khi upload trực tiếp)
# ─────────────────────────────────────────────
resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "lambda/lambda_deployment.zip"
  source = var.lambda_zip_path
  etag   = filemd5(var.lambda_zip_path)
}

# ─────────────────────────────────────────────
# Lambda Function — code lấy từ S3
# ─────────────────────────────────────────────
resource "aws_lambda_function" "recommender" {
  function_name = local.lambda_function_name
  role          = aws_iam_role.lambda.arn

  # Dùng S3 thay vì upload trực tiếp để vượt giới hạn 50 MB
  s3_bucket        = aws_s3_bucket.artifacts.bucket
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  runtime = "python3.12"
  handler = "lambda_function.lambda_handler"

  memory_size = var.lambda_memory_mb
  timeout     = var.lambda_timeout_sec

  environment {
    variables = {
      ARTIFACTS_BUCKET = aws_s3_bucket.artifacts.bucket
      MODEL_PREFIX     = var.model_prefix
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.s3_artifacts_read,
    aws_s3_object.lambda_zip,
  ]

  tags = {
    Project = local.project
  }
}

# Cho phép API Gateway gọi Lambda
resource "aws_lambda_permission" "apigateway_invoke" {
  statement_id  = "apigateway-invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.recommender.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*/recommend"
}
