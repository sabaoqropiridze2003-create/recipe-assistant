from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    google_api_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    chat_model: str = "gemini-3.8-flash"
    generation_model: str = "gemini-3.8-flash"

    environment: str = "development"
    chat_messages_per_hour: int = 30

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "recipe-assistant"
      
    @property
    def vector_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")

    @property
    def checkpoint_database_url(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")

settings = Settings()