from pydantic_settings import BaseSettings
from typing import List


class Config(BaseSettings):
    # Ключи API для разных сервисов
    bot_token: str
    openai_key: str
    deepseek_key: str
    assistant_id: str
    proxy_url: str = None  # Added proxy_url field
    admin_ids_str: str = "1110163898"  # Строка с ID администраторов через запятую в .env
    
    # Модели для разных задач
    openai_model: str = "gpt-4o-mini"  # Модель для ChatGPT
    deepseek_model: str = "deepseek-v3"  # Модель для Deepseek

    class Config:
        env_file = ".env"
    
    @property
    def admin_ids(self) -> List[int]:
        """Преобразует строку с ID администраторов в список целых чисел"""
        if not self.admin_ids_str:
            return []
        return [int(id_str.strip()) for id_str in self.admin_ids_str.split(",") if id_str.strip()]


config = Config()  # Загружаем конфигурацию



