from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, pathlib, aiofiles, json, asyncio, requests, time, re
from .system_prompt import build_system_prompt
from .memory import MemoryStore

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

memory = MemoryStore(DATA_DIR / "memory.json")

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://api.openai.com/v1/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_NAME = os.getenv("AI_NAME", "Genz")

app = FastAPI(title="Genz AI (Python)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

CLIENT_DIR = BASE_DIR.parent / "client"

@app.get("/api/info")
async def info():
    return {"name": AI_NAME, "dev": "You"}

def call_ai_sync(messages):
    if not AI_API_KEY:
        return "AI key not set on server."
    body = {"model": AI_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 1000}
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type":"application/json"}
    resp = requests.post(AI_API_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content") or data.get("choices", [{}])[0].get("text", "")
    return content or ""

@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    userId = body.get("userId", "guest")
    message = body.get("message", "")
    if not message:
        return JSONResponse({"error":"Missing message"}, status_code=400)
    user_mem = memory.get_user_memory(userId)
    system = build_system_prompt({"assistantName": AI_NAME})
    messages = [
        {"role":"system","content":system},
        {"role":"system","content":f"User memory: {json.dumps(user_mem)}"},
        {"role":"user","content":message},
    ]
    loop = asyncio.get_event_loop()
    ai_reply = await loop.run_in_executor(None, call_ai_sync, messages)
    m = re.search(r"\\bmy name is ([a-zA-Z0-9_ ]{1,40})\\b", message, re.I) or re.search(r"\\bi am ([A-Z][a-z]{1,30})\\b", message)
    if m:
        memory.save_user_memory(userId, {"name": m.group(1).strip()})
    memory.append_user_history(userId, {"user": message, "assistant": ai_reply, "ts": int(time.time())})
    return {"reply": ai_reply}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    dest = DATA_DIR / "uploads"
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / file.filename
    async with aiofiles.open(out_path, "wb") as f:
        content = await file.read()
        await f.write(content)
    return {"ok":True, "filename": file.filename, "path": str(out_path)}

@app.post("/api/video")
async def upload_video(video: UploadFile = File(...)):
    dest = DATA_DIR / "uploads"
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / video.filename
    async with aiofiles.open(out_path, "wb") as f:
        content = await video.read()
        await f.write(content)
    return {"ok":True, "file": {"original": video.filename, "size": len(content)}, "message":"Uploaded. For deeper analysis use a multimodal API."}

@app.get("/", response_class=HTMLResponse)
async def root():
    index = CLIENT_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h3>Genz AI backend running</h3>")
