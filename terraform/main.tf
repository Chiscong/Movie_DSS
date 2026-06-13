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
  alias  = "us_east_1"
  region = "us-east-1"
}

locals {
  project      = "movie-dss"
  artifacts_bucket_name = "${local.project}-artifacts"
  frontend_bucket_name  = "${local.project}-frontend"
  lambda_function_name  = "${local.project}-recommender"
  lambda_role_name      = "${local.project}-lambda-role"
  api_name              = "${local.project}-api"
}
