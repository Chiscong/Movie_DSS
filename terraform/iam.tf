# ─────────────────────────────────────────────
# IAM Role cho Lambda
# ─────────────────────────────────────────────

# Trust policy: cho phép Lambda service assume role này
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = local.lambda_role_name
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json

  tags = {
    Project = local.project
  }
}

# Gắn policy CloudWatch Logs cơ bản
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Inline policy: chỉ s3:GetObject trên prefix model/ — không có quyền ghi
data "aws_iam_policy_document" "s3_artifacts_read" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/model/*"]
  }
}

resource "aws_iam_role_policy" "s3_artifacts_read" {
  name   = "S3ArtifactsReadOnly"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.s3_artifacts_read.json
}
