import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="pie.ai pre-inference engine", version="0.1.0")

# Point upstream to local Ollama OpenAI-compatible endpoint
UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", "http://localhost:11434/v1")

def run_pre_inference_checks(payload: dict) -> tuple[bool, str]:
    messages = payload.get("messages", [])
    tools = payload.get("tools", [])
    
    total_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str))
    
    # Check 1: Context Bloat / Runaway Loop Guard
    if total_chars > 50000:
        return False, f"Blocked by pie.ai: Context window too large ({total_chars} chars). Potential runaway loop detected."
    
    # Check 2: Prompt Injection Guard
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and "ignore previous instructions" in content.lower():
            return False, "Blocked by pie.ai: Potential prompt injection signature identified."

    # Check 3: MCP / Tool-Call Schema & Safety Guard
    for tool in tools:
        func = tool.get("function", {})
        func_name = func.get("name", "unknown")
        
        # Example guard: Block dangerous or forbidden tool namespaces pre-inference
        forbidden_tools = ["execute_shell", "drop_database", "rm_rf"]
        if func_name in forbidden_tools:
            return False, f"Blocked by pie.ai: Tool '{func_name}' violates security policy (forbidden execution namespace)."

        # Check parameter schemas for structural soundness
        parameters = func.get("parameters", {})
        if parameters and not isinstance(parameters, dict):
            return False, f"Blocked by pie.ai: Tool '{func_name}' has malformed parameter schema."

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

    # 2. Forward clean request upstream to local Ollama
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            upstream_response = await client.post(
                f"{UPSTREAM_BASE_URL}/chat/completions",
                json=body,
                headers=headers
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
