resource "aws_ecr_repository" "crm_mcp" {
  name                 = "${var.demo_prefix}-crm-mcp"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}
