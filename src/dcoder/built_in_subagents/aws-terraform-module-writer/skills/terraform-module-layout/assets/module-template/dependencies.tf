// ============================================================
// dependencies.tf — Remote state & data sources
// ============================================================
// Pattern: Declare all terraform_remote_state data sources and
// AWS data sources here. Keep main.tf focused on resources.
// ============================================================

// ---- AWS Identity ----
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

// ---- Remote State: KMS Module ----
// Consume KMS key ARNs from the KMS module's state output.
// Usage: lookup(data.terraform_remote_state.kms.outputs.key_arns, "my-key-name")
data "terraform_remote_state" "kms" {
  count   = var.kms_state_bucket != "" ? 1 : 0
  backend = "s3"
  config = {
    bucket  = var.kms_state_bucket
    key     = var.kms_state_key
    region  = var.region
    profile = var.profile
  }
}

// ---- Remote State: IAM Module ----
// Consume IAM role ARNs from the IAM module's state output.
// Usage: lookup(data.terraform_remote_state.iam.outputs.role_arns, "MyRole")
# data "terraform_remote_state" "iam" {
#   backend = "s3"
#   config = {
#     bucket  = var.iam_state_bucket
#     key     = var.iam_state_key
#     region  = var.region
#     profile = var.profile
#   }
# }

// ---- Service-Specific Data Sources ----
// Uncomment as needed for your module:

# data "aws_elb_service_account" "elb" {}     // For S3 access logging
# data "aws_partition" "current" {}            // For GovCloud/China regions

// ---- CloudFormation Exports ----
// For resources created outside Terraform:
# data "aws_cloudformation_export" "legacy_key_arn" {
#   name = "export-name-here"
# }
