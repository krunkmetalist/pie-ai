import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="pie.ai pre-inference engine", version="0.1.0")

# Configuration for upstream provider (OpenAI, Ollama, etc.)
UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", "https://api.openai.com/v1")

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict]
    temperature: float | None = 0.7
    max_tokens: int | None = None

def run_pre_inference_checks(payload: dict) -> tuple[bool, str]:
    """
    Core pie.ai evaluation logic running pre-inference.
    Inspects messages for context bloat, prompt injection, or loop patterns.
    """
    messages = payload.get("messages", [])
    
    total_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str))
    
    # Check 1: Context Bloat / Runaway Loop Guard (e.g., arbitrarily blocking payloads > 50,000 chars for MVP)
    if total_chars > 50000:
        return False, f"Blocked by pie.ai: Context window too large ({total_chars} chars). Potential runaway loop detected."
    
    # Check 2: Simple Prompt Injection / Safety Signature Check
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and "ignore previous instructions" in content.lower():
            return False, "Blocked by pie.ai: Potential prompt injection signature identified."

    return True, "Passed"

@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 1. Execute Pre-Inference Checks
    is_safe, reason = run_pre_inference_checks(body)
    
    if not is_safe:
        # Fail fast: Save money, skip upstream API call entirely
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": reason,
                    "type": "pie_ai_pre_inference_block",
                    "code": "pre_inference_validation_failed"
                }
            }
        )

    # 2. If passed, forward request cleanly to upstream LLM provider
    headers = dict(request.headers)
    headers.pop("host", None) # Clean up host header for proxy forwarding
    
    async with httpx.AsyncClient() as client:
        try:
            upstream_response = await client.post(
                f"{UPSTREAM_BASE_URL}/chat/completions",
                json=body,
                headers=headers,
                timeout=30.0
            )
            return JSONResponse(
                status_code=upstream_response.status_code,
                content=upstream_response.json()
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"pie.ai proxy upstream error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
