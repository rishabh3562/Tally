#!/bin/bash
set -e

dnf update -y

dnf install -y docker

systemctl start docker
systemctl enable docker

docker pull ${docker_image}

docker run -d \
  --name tally \
  -p 80:3000 \
  ${docker_image}
