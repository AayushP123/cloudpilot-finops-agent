terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "dev_api_worker" {
  ami           = "ami-1234567890abcdef0"
  instance_type = "m5.2xlarge"

  tags = {
    Name    = "dev-api-worker"
    env     = "dev"
    owner   = "platform"
    service = "api"
  }
}

resource "aws_db_instance" "analytics" {
  identifier        = "analytics-postgres"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.m6g.2xlarge"
  allocated_storage = 200
  skip_final_snapshot = false

  tags = {
    env     = "staging"
    owner   = "data"
    service = "analytics"
  }
}

resource "aws_lb" "old_marketing" {
  name               = "old-marketing-lb"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-111111", "subnet-222222"]

  tags = {
    env     = "prod"
    owner   = "growth"
    service = "legacy-marketing"
  }
}

resource "aws_ebs_volume" "unused_build_cache" {
  availability_zone = "us-east-1a"
  size              = 800
  type              = "gp3"

  tags = {
    Name    = "unused-build-cache"
    env     = "dev"
    owner   = "build"
    service = "ci"
  }
}

resource "aws_instance" "prod_checkout_api" {
  ami           = "ami-1234567890abcdef0"
  instance_type = "m5.xlarge"

  tags = {
    Name    = "prod-checkout-api"
    env     = "prod"
    owner   = "payments"
    service = "checkout"
  }
}

