"""
NVIDIA Audio2Face-3D REST Bridge
Proxies HTTP REST requests to NVIDIA A2F-3D REST API
"""
import os
import base64
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

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
A2F_REST_ENDPOINT = "https://api.nvcf.nvidia.com/v2/nvcf"
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

def parse_a2f_response(response_data: Dict[str, Any]) -> List[BlendshapeFrame]:
    """Parse NVIDIA A2F-3D REST response into blendshape frames"""
    frames = []
    
    # Extract blendshape data from REST response
    blendshapes_data = response_data.get("blendshapes", [])
    
    for i, frame_data in enumerate(blendshapes_data):
        timestamp = i / A2F_OUTPUT_FPS
        
        # Map blendshape values
        blendshapes = {}
        if isinstance(frame_data, dict):
            blendshapes = {k: float(v) for k, v in frame_data.items()}
        elif isinstance(frame_data, list):
            # If array format, map to ARKit blendshape names
            for j, value in enumerate(frame_data):
                blendshape_name = f"blendshape_{j}"
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
    """Process audio through NVIDIA A2F-3D REST API and return blendshapes"""
    try:
        # Verify token
        verify_token(authorization)
        
        if not NVIDIA_API_KEY:
            raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured")
        
        function_id = request.function_id or A2F_FUNCTION_ID
        
        # Prepare REST API request
        url = f"{A2F_REST_ENDPOINT}/functions/{function_id}/invoke"
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "audio": request.audio,
            "format": request.format,
            "output_fps": A2F_OUTPUT_FPS,
        }
        
        # Call NVIDIA A2F-3D REST API
        print(f"🎙️ Calling NVIDIA A2F-3D REST API (function_id: {function_id})")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                error_text = response.text
                print(f"❌ NVIDIA API Error [{response.status_code}]: {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"NVIDIA A2F-3D Error: {error_text}"
                )
            
            response_data = response.json()
        
        # Parse response
        frames = parse_a2f_response(response_data)
        duration = len(frames) / A2F_OUTPUT_FPS if frames else 0
        
        print(f"✅ Generated {len(frames)} frames at {A2F_OUTPUT_FPS} FPS")
        
        return AudioResponse(
            success=True,
            frames=frames,
            fps=A2F_OUTPUT_FPS,
            duration=duration
        )
        
    except httpx.HTTPError as e:
        print(f"❌ HTTP Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"NVIDIA A2F-3D Connection Error: {str(e)}"
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
