terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration will be enabled after bootstrap
  backend "s3" {
    bucket         = "pynewb-terraform-state"
    key            = "global/s3/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "pynewb-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "pynewb"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

module "portfolio" {
  source      = "./modules/portfolio"
  domain_name = var.domain_name
}

module "precipitation" {
  source     = "./modules/precipitation"
  table_name = "ChicagoSnowfall"
}

output "api_url" {
  value = module.precipitation.api_url
}

module "github_oidc" {
  source = "./modules/github_oidc"
}

output "github_role_arn" {
  value = module.github_oidc.github_role_arn
}
