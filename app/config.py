from pydantic_settings import BaseSettings
from typing import List


class Config(BaseSettings):
    # Ключи API для разных сервисов
    bot_token: str
    openai_key: str
    deepseek_key: str
    assistant_id: str
    mistral_key: str = ""  # API ключ для Mistral AI
    mistral_key_backup: str = ""  # Резервный API ключ для Mistral AI
    proxy_url: str = None  # Added proxy_url field
    admin_ids_str: str = "1110163898"  # Строка с ID администраторов через запятую в .env
    
    # Модели для разных задач
    openai_model: str = "gpt-4o-mini"  # Модель для ChatGPT
    deepseek_model: str = "deepseek-v3"  # Модель для Deepseek
    
    # Настройки OCR
    use_mistral_ocr: bool = False  # Флаг для переключения между OCR методами

    class Config:
        env_file = ".env"
    
    @property
    def admin_ids(self) -> List[int]:
        """Преобразует строку с ID администраторов в список целых чисел"""
        if not self.admin_ids_str:
            return []
        return [int(id_str.strip()) for id_str in self.admin_ids_str.split(",") if id_str.strip()]
    
    @property
    def mistral_api_keys(self) -> List[str]:
        """Возвращает список доступных API ключей Mistral"""
        keys = []
        if self.mistral_key:
            keys.append(self.mistral_key)
        if self.mistral_key_backup:
            keys.append(self.mistral_key_backup)
        return keys


config = Config()  # Загружаем конфигурацию



