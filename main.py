from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from requests import post
from dotenv import load_dotenv
import os
from telethon import TelegramClient
from contextlib import asynccontextmanager
import json

for f in ["logos", ".users"]:
    if not os.path.exists(f):
        os.makedirs(f)
if not os.path.exists("config.json"):
    with open("default-config.json") as f:
        config = f.read()
    with open("config.json", "w") as f:
        f.write(config)
with open("config.json") as f:
    config = f.read()
    config = json.loads(config)
load_dotenv()
cloudflare_api_token = os.getenv("CLOUDFLARE_API_TOKEN")
cloudflare_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
telegram_api_id = os.getenv("TELEGRAM_API_ID")
telegram_api_hash = os.getenv("TELEGRAM_API_HASH")

tg_client = TelegramClient(".users/u0", telegram_api_id, telegram_api_hash)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await tg_client.connect()
    if not await tg_client.is_user_authorized():
        phone = input("Enter your phone number: ")
        await tg_client.send_code_request(phone)
        code = input("Enter the code: ")
        await tg_client.sign_in(phone, code)
        print("Logged in successfully.")
    else:
        print("Already logged in.")
    dialogs = await tg_client.get_dialogs()
    for dialog in dialogs:
        path = f"logos/{dialog.id}.jpg"
        if not os.path.exists(path):
            await tg_client.download_profile_photo(dialog, file=f"logos/{dialog.id}.jpg")
    yield

app = FastAPI(lifespan=lifespan)
if config.get("dev"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/dialogs")
async def get_dialogs():
    dialogs = await tg_client.get_dialogs()
    for dialog in dialogs:
        path = f"logos/{dialog.id}.jpg"
        if not os.path.exists(path):
            await tg_client.download_profile_photo(dialog, file=f"logos/{dialog.id}.jpg")
    return [{"id": dialog.id, "name": dialog.name} for dialog in dialogs]

@app.get("/logos/{dialog_id}.jpg")
async def get_logo(dialog_id: str):
    path = f"logos/{dialog_id}.jpg"
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    return {"error": "Logo not found"}, 404

@app.get("/chat/{dialog_id}")
async def get_chat(dialog_id: str):
    try:
        chat = await tg_client.get_entity(int(dialog_id))
        msgs = await tg_client.get_messages(chat, limit=30)
        return [
                {
                    "id": msg.id,
                    "senderId": msg.sender_id,
                    "senderName": msg.sender.first_name + " " + (msg.sender.last_name or "") if msg.sender else "Unknown",
                    "text": msg.message,
                    "date": msg.date.isoformat()
                } for msg in msgs
            ]
    except Exception as e:
        return {"error": str(e)}, 404

class TranslationRequest(BaseModel):
    text: str

with open("to-eng-prompt.txt") as f:
    to_eng_prompt = f.read()

@app.post("/translate")
def translate_text(request: TranslationRequest) -> str:
    try:
        r = post(
            f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_account_id}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            headers={
                "Authorization": f"Bearer {cloudflare_api_token}",
                "Content-Type": "application/json"
            },
            json={
            "messages": [
                {
                    "role": "system",
                    "content": to_eng_prompt
                },
                {
                    "role": "user",
                    "content": request.text
                }
            ]}
        )
        r.raise_for_status()
        j = r.json()
        assert j["success"], f"Error: got {j} as response"
        return j["result"]["response"]
    except Exception as e:
        return {"error": str(e)}, 500