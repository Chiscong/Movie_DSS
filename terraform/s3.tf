# ─────────────────────────────────────────────
# S3 Bucket 1: Model Artifacts (private)
# ─────────────────────────────────────────────
resource "aws_s3_bucket" "artifacts" {
  bucket        = local.artifacts_bucket_name
  force_destroy = false # Đặt true nếu muốn xoá bucket khi terraform destroy

  tags = {
    Project = local.project
    Role    = "artifacts"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# Upload 3 model artifacts lên S3 (chạy sau khi train_model.py đã tạo file)
resource "aws_s3_object" "vectorizer" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "model/vectorizer.pkl"
  source = "../model/vectorizer.pkl"
  etag   = filemd5("../model/vectorizer.pkl")
}

resource "aws_s3_object" "movie_vectors" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "model/movie_vectors.pkl"
  source = "../model/movie_vectors.pkl"
  etag   = filemd5("../model/movie_vectors.pkl")
}

resource "aws_s3_object" "movies_clean" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "model/movies_clean.json"
  source = "../model/movies_clean.json"
  etag   = filemd5("../model/movies_clean.json")
}

# ─────────────────────────────────────────────
# S3 Bucket 2: Frontend (private, phục vụ qua CloudFront OAC)
# ─────────────────────────────────────────────
resource "aws_s3_bucket" "frontend" {
  bucket        = local.frontend_bucket_name
  force_destroy = true

  tags = {
    Project = local.project
    Role    = "frontend"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# Upload các file frontend
resource "aws_s3_object" "index_html" {
  bucket        = aws_s3_bucket.frontend.id
  key           = "index.html"
  source        = "../frontend/index.html"
  content_type  = "text/html"
  cache_control = "max-age=86400"
  etag          = filemd5("../frontend/index.html")
}

resource "aws_s3_object" "style_css" {
  bucket        = aws_s3_bucket.frontend.id
  key           = "style.css"
  source        = "../frontend/style.css"
  content_type  = "text/css"
  cache_control = "max-age=86400"
  etag          = filemd5("../frontend/style.css")
}

resource "aws_s3_object" "app_js" {
  bucket        = aws_s3_bucket.frontend.id
  key           = "app.js"
  source        = "../frontend/app.js"
  content_type  = "application/javascript"
  cache_control = "max-age=86400"
  etag          = filemd5("../frontend/app.js")
}

# Bucket policy: chỉ cho CloudFront OAC đọc
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  # Phải đợi CloudFront distribution và OAC tạo xong
  depends_on = [aws_cloudfront_distribution.frontend]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
}
