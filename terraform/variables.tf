variable "aws_region" {
  description = "AWS region để deploy (ví dụ: ap-southeast-1)"
  type        = string
  default     = "ap-southeast-1"
}

variable "model_prefix" {
  description = "Prefix của model artifacts trong S3 (phải có dấu / ở cuối)"
  type        = string
  default     = "model/"
}

variable "lambda_memory_mb" {
  description = "Dung lượng RAM cấp cho Lambda (MB)"
  type        = number
  default     = 512
}

variable "lambda_timeout_sec" {
  description = "Timeout của Lambda (giây) — phải < 29 s để không vượt API Gateway limit"
  type        = number
  default     = 29
}

variable "lambda_zip_path" {
  description = "Đường dẫn tới file lambda_deployment.zip (relative hoặc absolute)"
  type        = string
  default     = "../lambda_deployment.zip"
}
