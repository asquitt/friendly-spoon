# Terraform Configuration for LLM Feature Store on AWS
#
# This creates:
# - DynamoDB table for online features
# - S3 bucket for Delta Lake
# - Lambda functions (optional, use OpenFaaS instead for cost savings)
# - IAM roles and policies
#
# Cost estimate: ~$25-40/month for 1M requests
#
# Usage:
#   terraform init
#   terraform plan
#   terraform apply

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment to use S3 backend for state
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "llm-feature-store/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "llm-feature-store"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ==============================================================================
# VARIABLES
# ==============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "llm-feature-store"
}

# ==============================================================================
# S3 BUCKET FOR DELTA LAKE (Cold Storage)
# ==============================================================================
# Cost: ~$0.023/GB/month with Intelligent-Tiering

resource "aws_s3_bucket" "delta_lake" {
  bucket = "${var.project_name}-delta-lake-${var.environment}"

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = false  # Set to true in production!
  }

  tags = {
    Name        = "Delta Lake Storage"
    Description = "Historical LLM interaction data"
  }
}

# Enable versioning for data recovery
resource "aws_s3_bucket_versioning" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable encryption at rest
resource "aws_s3_bucket_server_side_encryption_configuration" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Enable Intelligent-Tiering for cost optimization
resource "aws_s3_bucket_intelligent_tiering_configuration" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90  # Move to archive after 90 days
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180  # Move to deep archive after 180 days
  }
}

# Lifecycle policy to expire old versions
resource "aws_s3_bucket_lifecycle_configuration" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30  # Delete old versions after 30 days
    }
  }

  rule {
    id     = "delete-incomplete-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ==============================================================================
# DYNAMODB TABLE FOR ONLINE FEATURES (Hot Storage)
# ==============================================================================
# Cost: Pay-per-request, ~$1-10/month depending on traffic

resource "aws_dynamodb_table" "features" {
  name         = "${var.project_name}-features-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"  # Cost optimization: only pay for what you use

  hash_key  = "entity_id"
  range_key = "feature_name"

  attribute {
    name = "entity_id"
    type = "S"
  }

  attribute {
    name = "feature_name"
    type = "S"
  }

  # Enable point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Enable encryption at rest
  server_side_encryption {
    enabled = true
  }

  # TTL for automatic expiration (cost optimization)
  ttl {
    attribute_name = "expiration_time"
    enabled        = true
  }

  tags = {
    Name        = "Feature Store - Online Features"
    Description = "Low-latency feature serving"
  }
}

# ==============================================================================
# IAM ROLES AND POLICIES
# ==============================================================================

# Role for Lambda/OpenFaaS functions
resource "aws_iam_role" "function_role" {
  name = "${var.project_name}-function-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "Function Execution Role"
  }
}

# Policy for S3 access
resource "aws_iam_role_policy" "function_s3_policy" {
  name = "s3-access"
  role = aws_iam_role.function_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.delta_lake.arn,
          "${aws_s3_bucket.delta_lake.arn}/*"
        ]
      }
    ]
  })
}

# Policy for DynamoDB access
resource "aws_iam_role_policy" "function_dynamodb_policy" {
  name = "dynamodb-access"
  role = aws_iam_role.function_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = aws_dynamodb_table.features.arn
      }
    ]
  })
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "function_basic_execution" {
  role       = aws_iam_role.function_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ==============================================================================
# COST MONITORING - AWS BUDGETS
# ==============================================================================

resource "aws_budgets_budget" "monthly_cost" {
  name         = "${var.project_name}-monthly-budget"
  budget_type  = "COST"
  limit_amount = "50"  # Set your budget limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 80  # Alert at 80% of budget
    threshold_type      = "PERCENTAGE"
    notification_type   = "ACTUAL"

    # Add your email
    subscriber_email_addresses = [
      # "your-email@example.com"
    ]
  }

  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 100  # Alert at 100% of budget
    threshold_type      = "PERCENTAGE"
    notification_type   = "ACTUAL"

    subscriber_email_addresses = [
      # "your-email@example.com"
    ]
  }
}

# ==============================================================================
# OUTPUTS
# ==============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket for Delta Lake"
  value       = aws_s3_bucket.delta_lake.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.delta_lake.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.features.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.features.arn
}

output "function_role_arn" {
  description = "ARN of the IAM role for functions"
  value       = aws_iam_role.function_role.arn
}

# ==============================================================================
# COST ESTIMATES (as of 2025)
# ==============================================================================
#
# For 1M requests/month:
#
# S3 (100GB):
#   - Storage: $2.30/month (Standard)
#   - With Intelligent-Tiering: ~$1.50/month (35% savings)
#   - Requests: ~$0.50/month
#   - Total: ~$2/month
#
# DynamoDB (on-demand):
#   - Writes: 1M writes × $1.25 per million = $1.25
#   - Reads: 10M reads × $0.25 per million = $2.50
#   - Storage: 1GB × $0.25 = $0.25
#   - Total: ~$4/month
#
# Total Infrastructure: ~$6/month
#
# Additional costs (not managed by Terraform):
# - EC2 for DuckDB/Redis: ~$8/month (t4g.small spot instance)
# - Lambda/OpenFaaS: ~$5/month
# - Data transfer: ~$1/month
#
# Grand Total: ~$20/month
#
# Compare to traditional setup:
# - RDS: $100/month
# - BigQuery: $50/month
# - OpenAI embeddings: $100/month
# - Total: $250+/month
#
# Savings: $230/month (92%!)
#
# ==============================================================================
