# VIVID — Canon CR2 RAW Image Enhancer

Serverless image enhancement pipeline for Canon CR2 RAW files. 18 ISP-tuned presets for travel photography — upload a `.CR2`, pick a preset, get an Instagram-ready JPG/PNG back.

![Architecture](https://img.shields.io/badge/AWS-Lambda%20%2B%20S3-orange) ![Terraform](https://img.shields.io/badge/IaC-Terraform-purple) ![Python](https://img.shields.io/badge/Python-3.11%2B-blue)

## Features

- **Canon CR2 RAW processing** via rawpy with high-quality demosaicing
- **18 enhancement presets** across 3 categories (Subjects, Scenes, Vibes)
- **Adaptive ISP pipeline** — analyzes brightness, noise, saturation, sharpness per-image
- **Side-by-side preview** — original vs enhanced in the web UI
- **Fully serverless** — Terraform deploys everything including Docker build
- **JPG / PNG output** at high quality

## Presets

| Category | Presets |
|----------|---------|
| **Subjects** | Portrait, Pets, Food |
| **Scenes** | Landscape, Architecture, City, Ocean, Underwater, Jungle, Snow, Indoor |
| **Vibes** | Standard, Sunset, Night, Bright, Cinematic, Retro, B&W |

## Architecture

```
  Browser                  AWS
 ┌──────┐            ┌────────────┐
 │  UI  │───POST────▶│ API Lambda │──presigned URL──▶ S3 (uploads/)
 └──┬───┘            └────────────┘                      │
    │                                              S3 trigger
    │                                                    ▼
    │                                          ┌──────────────────┐
    │◀──poll /status─────────────────────────  │ Processor Lambda │
    │                                          │  (Docker / ECR)  │
    │                                          └────────┬─────────┘
    │                                                   │
    │◀──GET presigned URL───────────────────── S3 (results/)
 ┌──▼───┐
 │ Done │
 └──────┘
```

## Deploy

### Prerequisites

- [Terraform](https://terraform.io/downloads) ≥ 1.4
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- [Docker](https://docker.com) running

### One command

```bash
cd infra
terraform init
terraform apply
```

That's it. Terraform handles:
1. Provisioning S3, ECR, IAM, Lambda, Function URL
2. Building the processor Docker image and pushing to ECR
3. Zipping and deploying the API Lambda (frontend + handler)

The app URL is printed as `api_url` in the Terraform output.

### Quick deploy script (Windows)

```cmd
scripts\deploy.bat
```

### Tear down

```bash
cd infra
terraform destroy
```

## Project Structure

```
image-enhance/
├── lambda/
│   ├── api/
│   │   ├── handler.py          # API Lambda — serves UI, upload, status, result
│   │   └── frontend/
│   │       ├── index.html      # Tailwind CSS mobile-first UI
│   │       ├── app.js          # Upload flow, progress polling, blob download
│   │       └── style.css
│   ├── processor.py            # Processor Lambda — S3 trigger, orchestrates enhancement
│   └── Dockerfile              # Processor container (Python 3.12 + opencv + rawpy)
├── processors/
│   ├── base.py                 # BaseEnhancer — analysis, CLAHE, denoise, saturation, etc.
│   ├── factory.py              # Maps PresetType → Enhancer class
│   ├── enums.py                # PresetType, OutputFormat enums
│   ├── PortraitEnhancer.py     # Skin softening, eye sharpening
│   ├── PetsEnhancer.py         # Fur texture, neutral WB
│   ├── FoodEnhancer.py         # Warm temp, vibrance boost
│   ├── LandscapeEnhancer.py    # Shadow lift, highlight recovery
│   ├── ArchitectureEnhancer.py # High-pass clarity, neutral WB
│   ├── CityEnhancer.py         # Bleach bypass, structure
│   ├── SeascapeEnhancer.py     # Cyan tint, blue sat boost
│   ├── UnderwaterEnhancer.py   # Red channel restore, magenta tint
│   ├── JungleEnhancer.py       # Green→emerald hue shift
│   ├── SnowEnhancer.py         # Overexpose, warm blue shadows
│   ├── IndoorEnhancer.py       # Auto-WB, shadow lift
│   ├── GeneralEnhancer.py      # Minimal true-to-life adjustments
│   ├── GoldenHourEnhancer.py   # Warm temp, magenta tint, vibrance
│   ├── LowLightEnhancer.py     # Denoise, crush blacks, desat
│   ├── HighKeyEnhancer.py      # High exposure, flat contrast
│   ├── MoodyEnhancer.py        # Teal/orange grade, vignette
│   ├── RetroEnhancer.py        # Faded blacks, grain, green/yellow
│   └── BAndWEnhancer.py        # Red filter B&W, S-curve
├── infra/
│   └── main.tf                 # All AWS infra + Docker build/push
├── scripts/
│   └── deploy.bat              # One-click deploy (Windows)
└── pyproject.toml
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/upload` | Create task, get S3 presigned upload URL |
| `GET` | `/status/:id` | Poll processing progress |
| `GET` | `/result/:id` | Get presigned download + original URLs |

## Cost (AWS Free Tier)

| Service | Free Tier | Typical Usage |
|---------|-----------|---------------|
| Lambda | 1M req, 400K GB-s | Well within |
| S3 | 5 GB | Auto-expires after 1 day |
| ECR | 500 MB | ~350 MB image |
| Function URL | Free | — |

## License

MIT
