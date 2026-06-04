from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
import pandas as pd
from io import BytesIO
import base64

# Atualizado para ser compatível com Pydantic v2.x
class DataUploadResponse(BaseModel):
    success: bool
    columns: List[str] = []
    rows: int = 0
    preview: List[Dict[str, Any]] = []
    message: str = ""
    upload_id: Optional[str] = None

class AnalysisVariables(BaseModel):
    dependent_vars: List[str] = Field(..., description="Lista de variáveis dependentes")
    independent_vars: List[str] = Field(..., description="Lista de variáveis independentes")
    column_descriptions: Dict[str, str] = Field(default_factory=dict, description="Descrições das colunas")
    objective: Optional[str] = Field(default="", description="Objetivo da análise")

class AnalysisRequest(BaseModel):
    upload_id: str = Field(..., description="ID do arquivo de dados carregado")
    variables: AnalysisVariables

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class AnalysisResult(BaseModel):
    success: bool
    number: int
    name: str
    plots: List[Dict[str, str]] = []
    tables: List[Dict[str, str]] = []
    text_output: str = ""
    interpretation: Optional[str] = None  # Novo campo para interpretação dos resultados
    error: Optional[str] = None

class Analysis(BaseModel):
    number: int
    name: str
    content: str
    dependent_vars: List[str]
    independent_vars: List[str]
    status: AnalysisStatus = AnalysisStatus.PENDING
    results: Optional[AnalysisResult] = None

class RecommendationResponse(BaseModel):
    success: bool
    message: str
    recommendations: str
    analyses: List[Analysis] = []
    processing_time: float

class ExecuteAnalysisRequest(BaseModel):
    upload_id: str = Field(..., description="ID do upload do arquivo de dados")
    analysis_number: int = Field(..., description="Número da análise a ser executada")
    analysis_detail: Optional[str] = Field(None, description="Detalhes adicionais sobre a análise")
    dependent_vars: Optional[List[str]] = Field(None, description="Lista de variáveis dependentes")
    independent_vars: Optional[List[str]] = Field(None, description="Lista de variáveis independentes")

class ExecuteAnalysisResponse(BaseModel):
    success: bool
    message: str
    result: Optional[AnalysisResult] = None
