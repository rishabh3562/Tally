output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.tally.id
}

output "public_ip" {
  description = "Public IP address of the Tally frontend instance"
  value       = aws_instance.tally.public_ip
}

output "security_group_id" {
  description = "Security group ID for the Tally instance"
  value       = aws_security_group.tally_sg.id
}

output "instance_public_url" {
  description = "Public URL to access the Tally frontend"
  value       = "http://${aws_instance.tally.public_ip}"
}