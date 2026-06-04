import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API configs
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "ChatSmart API"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
      # Azure OpenAI
    AZURE_URL: str = os.environ.get("AZURE_URL", "")
    AZURE_KEY: str = os.environ.get("AZURE_KEY", "")
    
    # OpenAI (para compatibilidade com LangChain)
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    
    # Azure OpenAI API config (adicionados os campos que faltavam)
    DEPLOYMENT_NAME: str = os.environ.get("DEPLOYMENT_NAME", "gpt-4o-mini")
    AZURE_OPENAI_API_VERSION: str = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01")
    
    # Storage
    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", "/tmp/lean-six-sigma-uploads")
    
    # Application settings
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 10024  # 20MB
    DEFAULT_MODEL: str = "gpt-4o-mini"
    ANALYSIS_TIMEOUT: int = 60  # Segundos
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Permite campos extras sem gerar erro
    }

settings = Settings()

# Criar diretório de upload se não existir
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
