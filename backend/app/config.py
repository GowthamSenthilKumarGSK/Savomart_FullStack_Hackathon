from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://sitescout:sitescout@localhost:5432/sitescout"

    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    savomart_api_url: str = "https://internal-service.savomart.in/bridge/api/store/list?is_operational=True"
    savomart_api_token: str = ""

    backend_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
