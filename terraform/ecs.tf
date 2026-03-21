resource "aws_cloudwatch_log_group" "crm_mcp" {
  name              = "/ecs/${var.demo_prefix}-crm"
  retention_in_days = 7
}

resource "aws_ecs_cluster" "main" {
  name = "${var.demo_prefix}-cluster"
}

resource "aws_ecs_task_definition" "crm_mcp" {
  family                   = "${var.demo_prefix}-crm-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([
    {
      name      = "crm-mcp-server"
      image     = var.container_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.crm_mcp.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "crm_mcp" {
  name            = "${var.demo_prefix}-crm-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.crm_mcp.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.ecs_mcp_server.id]
    assign_public_ip = true
  }
}
