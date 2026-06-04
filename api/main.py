from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
import os

# Módulos internos
from api.routers import data_router, analysis_router, data_treatment_router
from api.config import settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("lean-six-sigma-api")

# Lifespan para gerenciar recursos na inicialização/encerramento
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização
    logger.info("API iniciando")
    
    try:
        # Inicializar recursos aqui (conexões DB etc)
        logger.info("Recursos inicializados com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar recursos: {e}")
        raise
        
    yield  # Aplicação sendo executada
    
    # Limpeza ao encerrar
    logger.info("API encerrando")

# Criar aplicação FastAPI com metadados aprimorados
app = FastAPI(
    title="ChatSmart API",
    description="API para recomendação e execução de análises Lean Six Sigma utilizando técnicas avançadas de inteligência artificial",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Desativamos os docs padrão para personalizar
    redoc_url=None  # Desativamos o redoc padrão para personalizar
)

# Adicionar middleware CORS para permitir chamadas do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(data_router.router, prefix=f"{settings.API_V1_STR}/data", tags=["data"])
app.include_router(analysis_router.router, prefix=f"{settings.API_V1_STR}/analysis", tags=["analysis"])
app.include_router(data_treatment_router.router, prefix=f"{settings.API_V1_STR}/data-treatment", tags=["data treatment"])

# Criar diretório de estáticos se não existir
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Montar arquivos estáticos
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Personalizar a documentação OpenAPI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="ChatSmart API Docs")

@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    return get_redoc_html(openapi_url="/openapi.json", title="ChatSmart API Redoc")

@app.get("/openapi.json", include_in_schema=False)
async def custom_openapi():
    return get_openapi(title="ChatSmart API", version="1.0.0", description="API para recomendação e execução de análises Lean Six Sigma utilizando técnicas avançadas de inteligência artificial", routes=app.routes)

# Endpoint raiz
@app.get("/")
async def root():
    return {
        "name": "ChatSmart API",
        "version": "1.0.0",
        "status": "online"
    }

# Verificação de saúde
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Execução direta para desenvolvimento
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
