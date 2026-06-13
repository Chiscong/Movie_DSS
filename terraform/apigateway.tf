# ─────────────────────────────────────────────
# API Gateway HTTP API
# ─────────────────────────────────────────────
resource "aws_apigatewayv2_api" "main" {
  name          = local.api_name
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
  }

  tags = {
    Project = local.project
  }
}

# Lambda proxy integration với timeout 29 s
resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.recommender.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

# Route: POST /recommend
resource "aws_apigatewayv2_route" "recommend" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /recommend"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Stage prod với auto-deploy
resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "prod"
  auto_deploy = true

  tags = {
    Project = local.project
  }
}
