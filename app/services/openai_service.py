from aiogram.types import Message
from openai import OpenAI
from app.config import config
from app.services import db_service
import os
from openai.types.beta.threads import Run
import logging
import httpx
from app.services.constants import CHECK_SYSTEM_PROMPT

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Выбираем ассистента
ASSISTANT_ID = config.assistant_id

# Setting up proxy configuration if provided
client_kwargs = {"api_key": config.openai_key}

# Add proxy configuration if it's set in config
if config.proxy_url:
    proxy_url = config.proxy_url
    
    # Parse proxy settings
    if '@' in proxy_url:
        # Format: user:password@ip:port
        auth, address = proxy_url.split('@')
        if ':' in auth:
            username, password = auth.split(':')
            # Set proxy with authentication included in the URL
            full_proxy_url = f"http://{username}:{password}@{address}"
        else:
            full_proxy_url = f"http://{auth}@{address}"
        
        # Create httpx client with proxy
        http_client = httpx.Client(proxy=full_proxy_url)
        client_kwargs["http_client"] = http_client
        logger.info(f"OpenAI client initialized with authenticated proxy")
    else:
        # Simple proxy without auth
        http_client = httpx.Client(proxy=f"http://{proxy_url}")
        client_kwargs["http_client"] = http_client
        logger.info(f"OpenAI client initialized with proxy: {proxy_url}")
else:
    logger.info("OpenAI client initialized without proxy")

# Initialize the client with the prepared arguments
client = OpenAI(**client_kwargs)
def get_or_create_thread(tg_user_id: int) -> str:
    thread_id = db_service.get_thread(tg_user_id)
    if thread_id:
        return thread_id

    thread = client.beta.threads.create()
    db_service.save_thread(tg_user_id, thread.id)
    return thread.id

# app/services/openai_service.py
async def ask_openai(prompt: str, tg_user_id: int) -> str:

    thread_id = get_or_create_thread(tg_user_id)

    # 1) добавляем сообщение пользователя
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt,
    )

    # 2) запускаем ран ассистента
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
    )

    if run.status != "completed":
        return f"⚠️ OpenAI: run finished with status {run.status}"

    # 3) берём последний ответ ассистента
    last_msg = client.beta.threads.messages.list(
        thread_id=thread_id,
        limit=1
    ).data[0]

    parts = [
        block.text.value
        for block in last_msg.content
        if block.type == "text"
    ]
    return "\n".join(parts).strip() or "⚠️ Ответ без текста"



async def ask_deepseek(prompt: str, message: Message) -> str:
    deepseek_client = OpenAI(
        api_key=config.deepseek_key,
        base_url="https://api.deepseek.com"
    )
    # deepseek_client = OpenAI(
    #     api_key=config.openai_key
    # )

    # Form system prompt
    system = CHECK_SYSTEM_PROMPT

    logger.debug(f"Prompt: {prompt}")
    print(f"Prompt: {prompt}")

    resp = deepseek_client.chat.completions.create(
        model=config.deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=1.2,
        max_tokens=8000,
        stream=False
    )

    return resp.choices[0].message.content