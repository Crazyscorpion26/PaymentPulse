output "application_url" {
  value = "http://${aws_lb.app.dns_name}"
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.app.name
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.app.name
}
