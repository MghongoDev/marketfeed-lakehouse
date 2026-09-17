terraform {
  required_version = ">= 1.0"

  required_providers {
    minio = {
      source  = "aminueza/minio"
      version = "~> 2.0"
    }
  }
}

provider "minio" {
  minio_server   = var.minio_endpoint
  minio_user     = var.minio_root_user
  minio_password = var.minio_root_password
  minio_ssl      = var.minio_ssl
}

# Bronze layer bucket
resource "minio_s3_bucket" "bronze" {
  bucket = "${var.project_name}-bronze"
  acl    = "private"
}

# Silver layer bucket
resource "minio_s3_bucket" "silver" {
  bucket = "${var.project_name}-silver"
  acl    = "private"
}

# Gold layer bucket
resource "minio_s3_bucket" "gold" {
  bucket = "${var.project_name}-gold"
  acl    = "private"
}

# Output bucket names for reference
output "bronze_bucket" {
  value       = minio_s3_bucket.bronze.bucket
  description = "Bronze layer bucket name"
}

output "silver_bucket" {
  value       = minio_s3_bucket.silver.bucket
  description = "Silver layer bucket name"
}

output "gold_bucket" {
  value       = minio_s3_bucket.gold.bucket
  description = "Gold layer bucket name"
}
