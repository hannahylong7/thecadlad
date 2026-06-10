from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    workspace_dir: str = "./workspace"
    model: str = "gpt-5.4"
    database_url: str = "sqlite:///data/cad_agent.db"
    executor_timeout: int = 30
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


    class Config:
        env_file = ".env"


settings = Settings()
