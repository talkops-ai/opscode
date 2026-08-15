variable "environment" {
  type        = string
  description = "Target deployment environment (e.g., dev, staging, prod)."

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  type        = string
  description = "Project or workload identifier for resource naming and tagging."
}

variable "tags" {
  type        = map(string)
  description = "Additional custom resource tags to apply to all module resources."
  default     = {}
}
