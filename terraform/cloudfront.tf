# ─────────────────────────────────────────────
# CloudFront Distribution + OAC
# ─────────────────────────────────────────────

# Origin Access Control (thay thế OAI cũ, bảo mật hơn)
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.project}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  http_version        = "http2"
  price_class         = "PriceClass_100" # Chỉ dùng edge ở Bắc Mỹ & Châu Âu — rẻ nhất
  comment             = "Movie DSS frontend"

  # Origin: S3 frontend bucket qua OAC
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "movie-dss-frontend-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Hành vi cache mặc định
  default_cache_behavior {
    target_origin_id       = "movie-dss-frontend-origin"
    viewer_protocol_policy = "redirect-to-https" # HTTP tự động chuyển sang HTTPS

    allowed_methods = ["GET", "HEAD"]
    cached_methods  = ["GET", "HEAD"]

    # Dùng Managed Cache Policy "CachingOptimized" của AWS
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    compress = true
  }

  # Lỗi 403 (S3 trả về khi file không tồn tại với block public access) → index.html
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  # Lỗi 404 → index.html (giữ SPA routing hoạt động)
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Dùng chứng chỉ CloudFront mặc định (*.cloudfront.net)
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Project = local.project
  }
}
