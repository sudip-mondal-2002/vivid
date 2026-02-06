terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  name            = "image-enhance"
  processor_files = fileset("${path.module}/../processors", "**/*.py")
  processor_hash = sha256(join(",", concat(
    [filemd5("${path.module}/../lambda/Dockerfile")],
    [filemd5("${path.module}/../lambda/processor.py")],
    [for f in local.processor_files : filemd5("${path.module}/../processors/${f}")]
  )))
}

# S3 Bucket for uploads and results
resource "aws_s3_bucket" "main" {
  bucket_prefix = "${local.name}-"
  force_destroy = true
}

resource "aws_s3_bucket_cors_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["*"]
    max_age_seconds = 3600
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "cleanup"
    status = "Enabled"

    expiration {
      days = 1
    }
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${local.name}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "${local.name}-s3"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.main.arn, "${aws_s3_bucket.main.arn}/*"]
    }]
  })
}

# ECR for processor Lambda container
resource "aws_ecr_repository" "processor" {
  name         = "${local.name}-processor"
  force_delete = true
}

# Build and push Docker image when processor code changes
resource "null_resource" "docker_build" {
  triggers = {
    code_hash = local.processor_hash
  }

  provisioner "local-exec" {
    working_dir = "${path.module}/.."
    command     = "aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${aws_ecr_repository.processor.repository_url} && docker build --platform linux/amd64 --provenance=false -t ${aws_ecr_repository.processor.repository_url}:latest -f lambda/Dockerfile . && docker push ${aws_ecr_repository.processor.repository_url}:latest"
  }

  depends_on = [aws_ecr_repository.processor]
}

# Processor Lambda (container - handles image processing)
resource "aws_lambda_function" "processor" {
  function_name = "${local.name}-processor"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.processor.repository_url}:latest"
  memory_size   = 2048
  timeout       = 300

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.main.bucket
      CODE_HASH   = local.processor_hash
    }
  }

  depends_on = [aws_iam_role_policy.lambda_s3, null_resource.docker_build]
}

# S3 trigger for processor
resource "aws_lambda_permission" "s3" {
  statement_id  = "AllowS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.main.arn
}

resource "aws_s3_bucket_notification" "main" {
  bucket = aws_s3_bucket.main.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
  }

  depends_on = [aws_lambda_permission.s3]
}

# API Lambda (zip - serves frontend and API)
data "archive_file" "api" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/api"
  output_path = "${path.module}/.terraform/api.zip"
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.main.bucket
    }
  }

  depends_on = [aws_iam_role_policy.lambda_s3]
}

# Function URL for API Lambda
resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
  }
}

resource "aws_lambda_permission" "url" {
  statement_id           = "AllowPublicAccessUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke" {
  statement_id  = "AllowPublicAccessInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "*"
}

# Outputs
output "api_url" {
  value = aws_lambda_function_url.api.function_url
}

output "bucket" {
  value = aws_s3_bucket.main.bucket
}

output "ecr_url" {
  value = aws_ecr_repository.processor.repository_url
}
