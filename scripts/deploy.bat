@echo off
setlocal

echo === Deploying Image Enhance ===

cd /d "%~dp0..\infra"

echo [1/2] Terraform init...
terraform init -input=false

echo [2/2] Terraform apply (builds Docker, deploys everything)...
terraform apply -auto-approve

echo === Done! ===
terraform output api_url
