from pydantic_settings import BaseSettings


class Config(BaseSettings):
    # Ключи API для разных сервисов
    bot_token: str
    openai_key: str
    deepseek_key: str
    assistant_id: str

    # Модели для разных задач
    openai_model: str = "gpt-4o-mini"  # Модель для ChatGPT
    deepseek_model: str = "deepseek-v3"  # Модель для Deepseek

    class Config:
        env_file = ".env"


config = Config()  # Загружаем конфигурацию



