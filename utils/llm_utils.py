"""
Utilidades para interação com modelos de linguagem (LLMs)
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Configurar logging
logger = logging.getLogger("lean-six-sigma-api.llm-utils")

# Carregar variáveis de ambiente
load_dotenv()

def initialize_llm():
    """Initialize the language model based on environment settings."""
    #api_base = os.getenv("AZURE_URL")
    api_key = os.getenv("AZURE_KEY")
    
    if api_key:
        return ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0
        )
    else:
        raise ValueError("Azure OpenAI credentials not found in environment variables")

def get_model_details() -> dict:
    """
    Retorna os detalhes do modelo configurado no ambiente.
    
    Returns:
        Dict com informações sobre os modelos configurados
    """
    return {
        "default_model": os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        "endpoint": os.getenv("AZURE_URL", "").split("/")[-1] if os.getenv("AZURE_URL") else None
    }
