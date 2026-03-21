variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC ID to deploy into"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ECS Fargate tasks"
  type        = list(string)
}

variable "demo_prefix" {
  description = "Naming prefix for all resources"
  type        = string
  default     = "agentcore-mcp-demo"
}

variable "container_image" {
  description = "Full ECR image URI (set after docker push)"
  type        = string
}

variable "container_port" {
  description = "Port the MCP server listens on"
  type        = number
  default     = 8080
}
