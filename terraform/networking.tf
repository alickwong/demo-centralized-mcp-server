resource "aws_security_group" "ecs_mcp_server" {
  name        = "${var.demo_prefix}-mcp-sg"
  description = "Allow ${var.container_port} for MCP server"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = var.container_port
    to_port     = var.container_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.demo_prefix}-mcp-sg"
  }
}
