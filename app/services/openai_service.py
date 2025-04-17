import openai
from app.config import config

openai.api_key = config.openai_key

async def ask_openai(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": "Ты помощник по Студенческому Стартапу."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"⚠️ Ошибка OpenAI: {e}"
