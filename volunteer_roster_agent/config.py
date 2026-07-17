import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    model_config = {"populate_by_name": True}


@lru_cache
def get_settings() -> Settings:
    return Settings(
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
    )


@lru_cache
def get_llm() -> ChatOpenAI:
    """Return a shared, cached chat model configured from settings."""
    settings = get_settings()
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
