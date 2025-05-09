from pydantic_settings import BaseSettings
from typing import List


class Config(BaseSettings):
    # API keys for different services
    bot_token: str
    openai_key: str
    deepseek_key: str
    assistant_id: str
    mistral_key: str = ""  # API key for Mistral AI
    mistral_key_backup: str = ""  # Backup API key for Mistral AI
    
    # Proxy settings
    proxy_url: str = None 
    
    admin_ids_str: str = "1110163898"  # Comma-separated string of admin IDs in .env
    
    # Models for different tasks
    openai_model: str = "gpt-4o-mini"  # Model for ChatGPT
    deepseek_model: str = "deepseek-chat"  # Model for Deepseek - updated from "deepseek-chat" to "deepseek-reasoner"
    
    # OCR settings
    use_mistral_ocr: bool = False  # Flag to switch between OCR methods
    
    # Database settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "stud_startup"
    db_user: str = "studuser"
    db_password: str = "studpass"

    class Config:
        env_file = ".env"
    
    @property
    def admin_ids(self) -> List[int]:
        """Converts the admin IDs string to a list of integers"""
        if not self.admin_ids_str:
            return []
        return [int(id_str.strip()) for id_str in self.admin_ids_str.split(",") if id_str.strip()]
    
    @property
    def mistral_api_keys(self) -> List[str]:
        """Returns a list of available Mistral API keys"""
        keys = []
        if self.mistral_key:
            keys.append(self.mistral_key)
        if self.mistral_key_backup:
            keys.append(self.mistral_key_backup)
        return keys


config = Config()  # Load configuration
