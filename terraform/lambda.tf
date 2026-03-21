data "archive_file" "weather_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/weather.py"
  output_path = "${path.module}/.build/weather.zip"
}

data "archive_file" "finance_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/finance.py"
  output_path = "${path.module}/.build/finance.zip"
}

resource "aws_lambda_function" "weather" {
  function_name    = "${var.demo_prefix}-weather"
  description      = "Weather tool for AgentCore Gateway demo"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "weather.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.weather_lambda.output_path
  source_code_hash = data.archive_file.weather_lambda.output_base64sha256
}

resource "aws_lambda_function" "finance" {
  function_name    = "${var.demo_prefix}-finance"
  description      = "Finance tool for AgentCore Gateway demo (RESTRICTED)"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "finance.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.finance_lambda.output_path
  source_code_hash = data.archive_file.finance_lambda.output_base64sha256
}
