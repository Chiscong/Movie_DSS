# ─────────────────────────────────────────────
# Lambda Function
# ─────────────────────────────────────────────
resource "aws_lambda_function" "recommender" {
  function_name = local.lambda_function_name
  role          = aws_iam_role.lambda.arn

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  runtime = "python3.11"
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
