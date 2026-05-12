#!/bin/bash
# Setup script for Data Engineering II - Assignment 3
# Prerequisites: Ubuntu 22.04+, Python3 (preinstalled)
# Run as: bash setup_vm.sh
sudo apt update
sudo apt upgrade
sudo apt install python3-openstackclient
sudo apt install python3-novaclient
sudo apt install python3-keystoneclient
sudo apt install git
sudo apt-add-repository ppa:ansible/ansible
sudo apt update
sudo apt install ansible

git clone https://bdtiger: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@github.com/bdtiger/data-engineering-II.git
source UPPMAX_2026_1-24_openrc.sh