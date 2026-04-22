#!/bin/bash
# Setup script for Data Engineering II - Assignment 2
# Prerequisites: Ubuntu 22.04+, Python3 (preinstalled)
# Run as: bash setup_vm.sh

set -e

echo "=========================================="
echo " DE2 A2 - VM Setup Script"
echo "=========================================="

# System update
echo "[1/4] Updating system packages..."
sudo apt update -y && sudo apt upgrade -y

# Java Runtime Environment
echo "[2/4] Installing Java Runtime Environment..."
sudo apt install -y default-jre
java -version

# Set JAVA_HOME
JAVA_BIN=$(which java)
JAVA_RESOLVED=$(readlink -f "$JAVA_BIN")
JAVA_HOME_PATH=$(dirname "$(dirname "$JAVA_RESOLVED")")
echo "export JAVA_HOME=${JAVA_HOME_PATH}" | sudo tee -a /etc/environment
echo "export JAVA_HOME=${JAVA_HOME_PATH}" >> ~/.bashrc
export JAVA_HOME=${JAVA_HOME_PATH}
echo "JAVA_HOME set to: $JAVA_HOME"

# Docker
echo "[3/4] Installing Docker..."

# Remove old/conflicting versions if any
sudo apt remove -y $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc 2>/dev/null | cut -f1) 2>/dev/null || true

sudo apt install -y ca-certificates curl

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker apt repository (DEB822 format)
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update -y
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Ensure Docker service is running
sudo systemctl start docker
sudo systemctl enable docker

# Allow current user to run docker without sudo
sudo usermod -aG docker "$USER"

docker --version

# Python pulsar-client
echo "[4/4] Installing pulsar-client..."
sudo apt install -y python3-pip
pip3 install pulsar-client==2.9.4

echo ""
echo "=========================================="
echo " Setup Complete!"
echo "=========================================="
echo ""
