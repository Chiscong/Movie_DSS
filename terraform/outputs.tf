# ─────────────────────────────────────────────
# Outputs — in ra sau khi terraform apply xong
# ─────────────────────────────────────────────

output "api_endpoint" {
  description = "URL đầy đủ của API Gateway endpoint — dùng để cập nhật API_URL trong app.js"
  value       = "${aws_apigatewayv2_stage.prod.invoke_url}/recommend"
}

output "cloudfront_url" {
  description = "URL của CloudFront distribution — đây là địa chỉ website công khai"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "artifacts_bucket" {
  description = "Tên S3 bucket chứa model artifacts"
  value       = aws_s3_bucket.artifacts.bucket
}

output "frontend_bucket" {
  description = "Tên S3 bucket chứa frontend files"
  value       = aws_s3_bucket.frontend.bucket
}

output "lambda_function_name" {
  description = "Tên Lambda function"
  value       = aws_lambda_function.recommender.function_name
}

output "lambda_arn" {
  description = "ARN của Lambda function"
  value       = aws_lambda_function.recommender.arn
}
