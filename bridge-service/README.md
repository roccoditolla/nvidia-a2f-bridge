# NVIDIA Audio2Face-3D gRPC Bridge

HTTP REST bridge for NVIDIA Audio2Face-3D gRPC API.

## Prerequisites

1. **NVIDIA API Key**: Get from https://build.nvidia.com/nvidia/audio2face-3d
2. **NVIDIA ACE Protobuf**: Download from https://github.com/NVIDIA/Audio2Face-3D-Samples

## Setup

### 1. Install NVIDIA Protobuf

```bash
# Clone NVIDIA samples
git clone https://github.com/NVIDIA/Audio2Face-3D-Samples.git
cd Audio2Face-3D-Samples

# Install the protobuf wheel
pip install proto/sample_wheel/nvidia_ace-1.2.0-py3-none-any.whl
```

### 2. Install Dependencies

```bash
cd bridge-service
pip install -r requirements.txt
```

### 3. Configure Environment

Create `.env` file:

```bash
NVIDIA_API_KEY=nvapi-xxx
A2F_FUNCTION_ID=0961a6da-fb9e-4f2e-8491-247e5fd7bf8d  # Claire (default)
A2F_OUTPUT_FPS=60
A2F_BRIDGE_TOKEN=your-secret-token  # Optional: for auth
```

**Available Function IDs:**
- **Claire**: `0961a6da-fb9e-4f2e-8491-247e5fd7bf8d`
- **Mark**: `8efc55f5-6f00-424e-afe9-26212cd2c630`
- **James**: `9327c39f-a361-4e02-bd72-e11b4c9b7b5e`

### 4. Run Locally

```bash
python main.py
```

Server starts at `http://localhost:8000`

## Deployment

### Option A: Google Cloud Run

```bash
# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT/a2f-bridge

# Deploy
gcloud run deploy a2f-bridge \
  --image gcr.io/YOUR_PROJECT/a2f-bridge \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars NVIDIA_API_KEY=nvapi-xxx,A2F_FUNCTION_ID=0961a6da-fb9e-4f2e-8491-247e5fd7bf8d,A2F_BRIDGE_TOKEN=your-token
```

### Option B: Render.com

1. Create new Web Service
2. Connect this repo
3. Set environment variables
4. Deploy

### Option C: Docker

```bash
# Build
docker build -t a2f-bridge .

# Run
docker run -p 8000:8000 \
  -e NVIDIA_API_KEY=nvapi-xxx \
  -e A2F_FUNCTION_ID=0961a6da-fb9e-4f2e-8491-247e5fd7bf8d \
  -e A2F_BRIDGE_TOKEN=your-token \
  a2f-bridge
```

## API Usage

### Health Check

```bash
curl http://localhost:8000/health
```

### Process Audio

```bash
curl -X POST http://localhost:8000/a2f/process \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "audio": "base64_encoded_audio_data",
    "format": "webm"
  }'
```

Response:
```json
{
  "success": true,
  "frames": [
    {
      "timestamp": 0.0,
      "blendshapes": {
        "jawOpen": 0.5,
        "mouthSmileLeft": 0.3,
        ...
      }
    }
  ],
  "fps": 60,
  "duration": 2.5
}
```

## Supabase Integration

After deploying, configure Supabase secrets:

```bash
# In Supabase Dashboard -> Project Settings -> Edge Functions
A2F_BRIDGE_URL=https://your-bridge-url.com
A2F_BRIDGE_TOKEN=your-secret-token
```

## Troubleshooting

### gRPC Connection Issues

- Verify `NVIDIA_API_KEY` is valid
- Check `A2F_FUNCTION_ID` matches one of the available models
- Ensure network allows outbound gRPC to `grpc.nvcf.nvidia.com:443`

### Protobuf Errors

- Make sure `nvidia_ace` wheel is installed correctly
- Check NVIDIA samples repo for latest version

### Performance

- Default FPS is 60 (recommended for smooth animation)
- Adjust `A2F_OUTPUT_FPS` if needed (30-120 range)

## Architecture

```
┌─────────────┐     HTTP      ┌─────────────┐     gRPC      ┌─────────────┐
│   Supabase  │──────────────▶│   Bridge    │──────────────▶│   NVIDIA    │
│Edge Function│               │  FastAPI    │               │   A2F-3D    │
└─────────────┘               └─────────────┘               └─────────────┘
      │                              │                              │
      │                              │                              │
      ▼                              ▼                              ▼
  audio base64              gRPC conversion              52 ARKit blendshapes
                                                              @ 60 FPS
```

## License

MIT