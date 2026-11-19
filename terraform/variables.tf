variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "project_name" {
  type    = string
  default = "paymentpulse"
}

variable "container_image" {
  type        = string
  description = "ECR image URI including tag"
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "At least two public subnet IDs in different AZs"
}

variable "allowed_ingress_cidr" {
  type        = string
  description = "Your public IP in CIDR notation (for example, 203.0.113.10/32); avoid 0.0.0.0/0"
}
