from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    workspace_dir: str = "/workspace"
    model: str = "gpt-5.4"

    class Config:
        env_file = ".env"


settings = Settings()
