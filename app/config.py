from pydantic import BaseSettings

class Config(BaseSettings):
    bot_token: str
    openai_key: str
    openai_model: str = "gpt-3.5-turbo"

    class Config:
        env_file = ".env"

config = Config()
