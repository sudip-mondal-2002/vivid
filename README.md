# CR2 Image Enhancer

Intelligent Canon CR2 RAW image enhancement using computer vision. Supports both local development and AWS Lambda deployment.

## Features

- **Intelligent RAW Processing**: Uses rawpy for high-quality demosaicing
- **Multiple Enhancement Presets**: Landscape, Portrait, Low Light, Architecture, General
- **Adaptive Enhancement**: Analyzes image characteristics and adjusts processing automatically
- **Side-by-Side Comparison**: View original vs enhanced images
- **AWS Lambda Ready**: Serverless deployment with S3 storage
- **High Quality Output**: Supports both JPG (95% quality) and PNG output

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│ API Gateway │────▶│  API Lambda │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌─────────────┐             │
                    │  Processor  │◀────────────┤
                    │   Lambda    │             │
                    └──────┬──────┘             │
                           │                   │
                    ┌──────▼──────┐             │
                    │     S3      │◀────────────┘
                    │   Bucket    │
                    └─────────────┘
```

## Quick Start (Local Development)

```bash
# Install dependencies
uv sync

# Run the local development server
uv run python local/local_server.py
```

Visit http://localhost:8000 to use the web interface.

## AWS Deployment

### Prerequisites

- [Terraform](https://terraform.io/downloads) >= 1.0
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- [Docker](https://docker.com) for building Lambda container

### Deploy

**Windows (PowerShell):**
```powershell
.\scripts\deploy.ps1
```

**Linux/macOS:**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Manual Deployment Steps

```bash
# 1. Initialize Terraform
cd infra
terraform init

# 2. Create ECR repository first
terraform apply -target=aws_ecr_repository.processor

# 3. Build and push Docker image
ECR_REPO=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
docker build -t image-enhance -f ../lambda/Dockerfile ..
docker tag image-enhance:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

# 4. Deploy remaining infrastructure
terraform apply

# 5. Update frontend config
terraform output frontend_config > ../frontend/config.js
```

### Cleanup

```bash
cd infra
terraform destroy
```

## Project Structure

```
image-enhance/
├── frontend/           # Static frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── config.js       # API endpoint configuration
├── lambda/             # AWS Lambda handlers
│   ├── handler.py      # S3 trigger processor
│   ├── api_handler.py  # API Gateway handler
│   ├── Dockerfile
│   └── requirements.txt
├── local/              # Local development
│   └── local_server.py # FastAPI server mimicking Lambda
├── infra/              # Terraform infrastructure
│   ├── main.tf
│   ├── lambda.tf
│   ├── api_gateway.tf
│   ├── variables.tf
│   └── outputs.tf
├── processors/         # Image enhancement strategies
│   ├── base.py
│   ├── LandscapeEnhancer.py
│   ├── PortraitEnhancer.py
│   ├── LowLightEnhancer.py
│   ├── ArchitectureEnhancer.py
│   └── GeneralEnhancer.py
├── scripts/            # Deployment scripts
│   ├── deploy.ps1      # Windows
│   └── deploy.sh       # Linux/macOS
└── enums.py            # Shared enums
```

## Cost Estimate (AWS Free Tier)

| Service | Free Tier | Expected Usage |
|---------|-----------|----------------|
| Lambda | 1M requests, 400K GB-sec | Covered |
| S3 | 5GB storage | Covered (auto-cleanup) |
| API Gateway | 1M calls | Covered |
| ECR | 500MB storage | Covered |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUCKET_NAME` | S3 bucket for storage | Set by Terraform |
| `AWS_REGION` | AWS region | us-east-1 |

## API

- `GET /` - Web interface
- `POST /enhance` - Process image with preset and format parameters
