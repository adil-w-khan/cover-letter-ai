from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
from typing import List


class Settings(BaseSettings):
    ENV: str = "dev"
    DATABASE_URL: str

    JWT_SECRET: str
    JWT_ACCESS_EXPIRES_MIN: int = 15
    JWT_REFRESH_EXPIRES_DAYS: int = 14

    OPENAI_API_KEY: str

    CORS_ORIGINS: str = "http://localhost:5173"
    COOKIE_SECURE: bool = False  # set true in prod (https only)

    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
