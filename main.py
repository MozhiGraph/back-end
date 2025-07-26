from fastapi import FastAPI
from pydantic import BaseModel
from requests import post
from dotenv import load_dotenv
import os

load_dotenv()
cloudflare_api_token = os.getenv("CLOUDFLARE_API_TOKEN")
cloudflare_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")

app = FastAPI()

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
        return {"error": str(e)}