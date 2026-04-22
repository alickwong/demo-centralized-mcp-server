output "ecr_repository_url" {
  description = "ECR repository URI for the CRM MCP server image"
  value       = aws_ecr_repository.crm_mcp.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.crm_mcp.name
}

output "security_group_id" {
  description = "Security group ID for the MCP server"
  value       = aws_security_group.ecs_mcp_server.id
}

output "ecs_task_role_arn" {
  description = "ECS task execution role ARN"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "policy_lookup_lambda_arn" {
  description = "Policy Lookup Lambda function ARN"
  value       = aws_lambda_function.policy_lookup.arn
}

output "policy_lookup_lambda_name" {
  description = "Policy Lookup Lambda function name"
  value       = aws_lambda_function.policy_lookup.function_name
}

output "claims_lambda_arn" {
  description = "Claims Lambda function ARN"
  value       = aws_lambda_function.claims.arn
}

output "claims_lambda_name" {
  description = "Claims Lambda function name"
  value       = aws_lambda_function.claims.function_name
}

output "lambda_role_name" {
  description = "Lambda execution IAM role name"
  value       = aws_iam_role.lambda_execution.name
}

output "gateway_role_arn" {
  description = "AgentCore Gateway IAM role ARN"
  value       = aws_iam_role.gateway.arn
}
