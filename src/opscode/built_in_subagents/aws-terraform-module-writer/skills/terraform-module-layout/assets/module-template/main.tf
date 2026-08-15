locals {
  default_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Module      = "terraform-module"
  }

  tags = merge(local.default_tags, var.tags)
}

# Example resource declaration
# resource "aws_s3_bucket" "this" {
#   bucket = "${var.project_name}-${var.environment}-bucket"
#   tags   = local.tags
# }
