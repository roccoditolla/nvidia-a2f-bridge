"""
NVIDIA Audio2Face-3D gRPC Bridge
Converts HTTP REST requests to gRPC calls for NVIDIA A2F-3D API
"""
import os
import base64
import io
import wave
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import grpc
from nvidia_ace.a2f.v1 import audio2face_pb2, audio2face_pb2_grpc

app = FastAPI(title="NVIDIA A2F-3D Bridge")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
A2F_FUNCTION_ID = os.getenv("A2F_FUNCTION_ID", "0961a6da-fb9e-4f2e-8491-247e5fd7bf8d")  # Claire default
A2F_ENDPOINT = "grpc.nvcf.nvidia.com:443"
A2F_OUTPUT_FPS = int(os.getenv("A2F_OUTPUT_FPS", "60"))
BRIDGE_TOKEN = os.getenv("A2F_BRIDGE_TOKEN")

class AudioRequest(BaseModel):
    audio: str  # base64 encoded audio
    format: str = "webm"
    function_id: str | None = None

class BlendshapeFrame(BaseModel):
    timestamp: float
    blendshapes: Dict[str, float]

class AudioResponse(BaseModel):
    success: bool
    frames: List[BlendshapeFrame] | None = None
    fps: int | None = None
    duration: float | None = None
    error: str | None = None

def verify_token(authorization: str = Header(None)):
    """Verify bearer token"""
    if not BRIDGE_TOKEN:
        return  # No auth required if token not set
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    if token != BRIDGE_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

def convert_to_pcm16(audio_data: bytes, input_format: str) -> bytes:
    """Convert audio to PCM 16-bit format required by NVIDIA"""
    # For now, assume input is already compatible
    # In production, use pydub or similar for conversion
    return audio_data

def create_grpc_metadata() -> List[tuple]:
    """Create gRPC metadata with auth"""
    return [
        ("authorization", f"Bearer {NVIDIA_API_KEY}"),
        ("function-id", A2F_FUNCTION_ID),
    ]

def parse_a2f_response(response) -> List[BlendshapeFrame]:
    """Parse NVIDIA A2F-3D response into blendshape frames"""
    frames = []
    
    # Extract blendshape data from response
    # This depends on NVIDIA's protobuf structure
    for i, frame_data in enumerate(response.blendshapes):
        timestamp = i / A2F_OUTPUT_FPS  # Calculate timestamp based on FPS
        
        # Convert NVIDIA blendshapes to dict
        blendshapes = {}
        for j, value in enumerate(frame_data.values):
            # Map ARKit blendshape names (NVIDIA uses ARKit standard)
            blendshape_name = f"blendshape_{j}"  # Placeholder, will be replaced with actual names
            blendshapes[blendshape_name] = float(value)
        
        frames.append(BlendshapeFrame(
            timestamp=timestamp,
            blendshapes=blendshapes
        ))
    
    return frames

@app.post("/a2f/process", response_model=AudioResponse)
async def process_audio(
    request: AudioRequest,
    authorization: str = Header(None)
):
    """Process audio through NVIDIA A2F-3D and return blendshapes"""
    try:
        # Verify token
        verify_token(authorization)
        
        if not NVIDIA_API_KEY:
            raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured")
        
        # Decode audio
        audio_bytes = base64.b64decode(request.audio)
        
        # Convert to PCM16 if needed
        pcm_audio = convert_to_pcm16(audio_bytes, request.format)
        
        # Create gRPC channel
        credentials = grpc.ssl_channel_credentials()
        channel = grpc.secure_channel(A2F_ENDPOINT, credentials)
        stub = audio2face_pb2_grpc.Audio2FaceStub(channel)
        
        # Prepare request
        function_id = request.function_id or A2F_FUNCTION_ID
        metadata = create_grpc_metadata()
        
        # Create A2F request
        a2f_request = audio2face_pb2.ProcessAudioRequest(
            audio_data=pcm_audio,
            output_fps=A2F_OUTPUT_FPS,
        )
        
        # Call NVIDIA A2F-3D
        print(f"🎙️ Calling NVIDIA A2F-3D (function_id: {function_id})")
        response = stub.ProcessAudio(a2f_request, metadata=metadata)
        
        # Parse response
        frames = parse_a2f_response(response)
        duration = len(frames) / A2F_OUTPUT_FPS if frames else 0
        
        print(f"✅ Generated {len(frames)} frames at {A2F_OUTPUT_FPS} FPS")
        
        return AudioResponse(
            success=True,
            frames=frames,
            fps=A2F_OUTPUT_FPS,
            duration=duration
        )
        
    except grpc.RpcError as e:
        print(f"❌ gRPC Error: {e.code()}: {e.details()}")
        raise HTTPException(
            status_code=500,
            detail=f"NVIDIA A2F-3D Error: {e.details()}"
        )
    except Exception as e:
        print(f"❌ Bridge Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "nvidia_api_configured": bool(NVIDIA_API_KEY),
        "function_id": A2F_FUNCTION_ID,
        "output_fps": A2F_OUTPUT_FPS
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
