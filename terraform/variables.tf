variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment (dev/prod)"
  type        = string
  default     = "dev"
}

variable "domain_name" {
  description = "Domain name for the portfolio"
  type        = string
  default     = "pynewb.com"
}
