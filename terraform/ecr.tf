resource "aws_ecr_repository" "crm_mcp" {
  name                 = "${var.demo_prefix}-crm-mcp"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}
