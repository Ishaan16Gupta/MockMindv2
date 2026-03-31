import os
import requests
import json

from fastapi import FastAPI, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from groq import Groq

app = FastAPI()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("easebot2_0.html",{"request":request})

# @app.get("/chat")
def generate(prompt:str):
    response = requests.post("http://localhost:11434/api/generate",json={"model":"llama3.2","prompt":prompt,"stream":True},stream=True)
    
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if "response" in data:
                yield data["response"]
    
    # data = response.json()
    # return data["response"]
    # models : llama3.2, gemma

# @app.get("/chat_stream")
# def chat_stream(prompt: str):
#     return StreamingResponse(generate(prompt), media_type="text/event-stream")

@app.post("/chat_stream")
def chat_stream_form(prompt: str = Form(...)):
    return StreamingResponse(generate(prompt), media_type="text/plain")

# @app.get("/chat_groq")
# def chat_groq(prompt:str):
#     chat_completion = client.chat.completions.create(
#         messages=[{"role": "user","content": prompt}],
#         model="llama-3.1-8b-instant"
#     )
#     response = chat_completion.choices[0].message.content

#     return response

# models : llama-3.1-8b-instant ; llama-3.3-70b-versatile ; openai/gpt-oss-120b ; openai/gpt-oss-20b

# @app.post("/submit")
# def submit(prompt: str = Form(...)):
#     return StreamingResponse(generate(prompt), media_type="text/plain")

# print(f"\nReasoning: {reasoning}\n\n")
# print(f"Response: {response}")
# print(chat_completion)