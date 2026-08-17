from typing import Annotated, Any

from pydantic import AnyUrl, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(value: Any) -> list[str] | str:
    if isinstance(value, str) and not value.startswith("["):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    if isinstance(value, list | str):
        return value
    raise ValueError(value)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    FRONTEND_HOST: str = "http://localhost:5173"
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @property
    def all_cors_origins(self) -> list[str]:
        configured_origins = (
            [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]
            if isinstance(self.BACKEND_CORS_ORIGINS, list)
            else []
        )
        return [*configured_origins, self.FRONTEND_HOST.rstrip("/")]


settings = Settings()  # type: ignore[call-arg]
