#!/bin/bash
# Setup script for Data Engineering II - Assignment 3
# Prerequisites: Ubuntu 22.04+, Python3 (preinstalled)
# Run as: bash setup_vm.sh

sudo apt install python3-openstackclient
sudo apt install python3-novaclient
sudo apt install python3-keystoneclient

source UPPMAX_2026_1-24_openrc.sh