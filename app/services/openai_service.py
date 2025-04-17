from app.config import config
from openai import OpenAI
from app.services import db_service


# Устанавливаем ключ API для OpenAI
# один экземпляр клиента на весь модуль
client = OpenAI(api_key=config.openai_key)
ASSISTANT_ID = "asst_pvRWcceePsuxNShCSeKg66hM"

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



async def ask_deepseek(prompt: str) -> str:
    client = OpenAI(api_key=config.deepseek_key,
                    base_url="https://api.deepseek.com")

    system = (
        "Ты — эксперт по оценке грантовых заявок. "
        "Верни ответ ТОЛЬКО в HTML: <b>, <i>, <blockquote>, <br>. "
        "Без markdown, без LaTeX. "
        "Всегда отвечай на русском.\n\n"
        "Проанализируй текст ниже. Укажи логические, стилистические, "
        "структурные ошибки и дай рекомендации по улучшению каждого раздела. "
        "Оцени по 10‑балльной шкале критерии «Технологичность проекта» "
        "и «Перспективы коммерциализации» (таблица в положении)."
    )

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
    )

    return resp.choices[0].message.content
