terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}


provider "aws" {
  alias  = "ap_southeast_1"
  region = "ap-southeast-1"
}

# Lấy account ID tự động để tạo tên bucket unique toàn cầu
data "aws_caller_identity" "current" {}

locals {
  project               = "movie-dss"
  account_id            = data.aws_caller_identity.current.account_id
  # Tên bucket gắn account ID — đảm bảo unique trên toàn AWS
  artifacts_bucket_name = "${local.project}-artifacts-${local.account_id}"
  frontend_bucket_name  = "${local.project}-frontend-${local.account_id}"
  lambda_function_name  = "${local.project}-recommender"
  lambda_role_name      = "${local.project}-lambda-role"
  api_name              = "${local.project}-api"
}
