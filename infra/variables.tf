variable "project_name" {
  description = "Project name used for bucket naming"
  type        = string
  default     = "marketfeed-lakehouse"
}

variable "minio_endpoint" {
  description = "MinIO server endpoint"
  type        = string
  default     = "localhost:9000"
}

variable "minio_root_user" {
  description = "MinIO root user"
  type        = string
  default     = "minioadmin"
  sensitive   = true
}

variable "minio_root_password" {
  description = "MinIO root password"
  type        = string
  default     = "minioadmin"
  sensitive   = true
}

variable "minio_ssl" {
  description = "Use SSL for MinIO connection"
  type        = bool
  default     = false
}
