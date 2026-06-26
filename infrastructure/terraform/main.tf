terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-south-1"
}

resource "aws_security_group" "tally_sg" {
  name = "tally-sg"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
     cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "tally" {
  ami           = "ami-0f58b397bc5c1f2e8" # Amazon Linux 2023 (Mumbai, verify latest)
  instance_type = "t2.micro"

  vpc_security_group_ids = [aws_security_group.tally_sg.id]

  user_data = <<-EOF
              #!/bin/bash
              dnf update -y

              dnf install -y docker

              systemctl start docker
              systemctl enable docker

              docker pull dubeyrishabh108/tally-frontend:v1

              docker run -d \
                --name tally \
                -p 80:3000 \
                dubeyrishabh108/tally-frontend:v1
              EOF

  tags = {
    Name = "tally-frontend"
  }
}