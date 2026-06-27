variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-south-1"
}

variable "ami_id" {
  description = "AMI ID for Amazon Linux 2023 in ap-south-1"
  type        = string
  default     = "ami-0f58b397bc5c1f2e8"
}

variable "instance_type" {
  description = "EC2 instance type (t3.micro is free-tier eligible)"
  type        = string
  default     = "t3.micro"
}

variable "instance_name" {
  description = "Name tag for the EC2 instance"
  type        = string
  default     = "tally-frontend"
}

variable "docker_image" {
  description = "Docker image to run on the instance"
  type        = string
  default     = "dubeyrishabh108/tally-frontend:v1"
}
