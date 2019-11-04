#!/bin/bash


set -e

cluster=$1

echo "ansible-playbook -i config_manager/$cluster/inventory.ini bootstrap.yml"

echo "ansible-playbook -i config_manager/$cluster/inventory.ini deploy.yml"

echo "ansible-playbook -i config_manager/$cluster/inventory.ini start.yml"

echo "ansible-playbook -i config_manager/$cluster/inventory.ini stop.yml"

echo "ansible-playbook -i config_manager/$cluster/inventory.ini unsafe_cleanup.yml"

