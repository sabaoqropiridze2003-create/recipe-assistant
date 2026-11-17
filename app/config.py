from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    google_api_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    chat_model: str = "gemini-3.8-flash"
      
    @property
    def vector_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")

settings = Settings()