from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, BackgroundTasks
from typing import List
import pandas as pd
import os
import uuid
import logging
from io import BytesIO

from api.models import DataUploadResponse
from api.services.data_service import process_data_file, get_dataset, clean_for_json
from api.config import settings

router = APIRouter()
logger = logging.getLogger("lean-six-sigma-api.data")

@router.post("/upload", response_model=DataUploadResponse)
async def upload_data(file: UploadFile = File(...)):
    """
    Upload de arquivo CSV ou Excel para análise.
    """
    if not file:
        raise HTTPException(status_code=400, detail="Nenhum arquivo foi enviado")
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ['.csv', '.xlsx', '.xls']:
        raise HTTPException(
            status_code=400, 
            detail="Formato de arquivo não suportado. Use CSV ou Excel (xlsx/xls)"
        )
    
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo muito grande. O tamanho máximo é {settings.MAX_UPLOAD_SIZE / (1024*1024)}MB"
        )
    
    try:
        # Gerar ID único para este upload
        upload_id = str(uuid.uuid4())
        
        # Processar o arquivo
        result = process_data_file(BytesIO(contents), file.filename, file_extension, upload_id)
        return result
    
    except Exception as e:
        logger.error(f"Erro ao processar arquivo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar arquivo: {str(e)}"
        )

@router.get("/datasets", response_model=List[str])
async def list_datasets():
    """
    Lista os IDs dos datasets disponíveis.
    """
    try:
        # Listar arquivos salvos no diretório de upload
        files = [f for f in os.listdir(settings.UPLOAD_DIR) if os.path.isfile(os.path.join(settings.UPLOAD_DIR, f))]
        dataset_ids = [os.path.splitext(f)[0] for f in files]
        return dataset_ids
    except Exception as e:
        logger.error(f"Erro ao listar datasets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar datasets: {str(e)}"
        )

@router.get("/columns/{upload_id}")
async def get_columns(upload_id: str):
    """
    Recupera as colunas de um dataset específico.
    """
    try:
        df = get_dataset(upload_id)
        return {"columns": df.columns.tolist()}
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset com ID {upload_id} não encontrado"
        )
    except Exception as e:
        logger.error(f"Erro ao recuperar colunas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao recuperar colunas: {str(e)}"
        )

@router.get("/preview/{upload_id}")
async def get_preview(
    upload_id: str,
    rows: int = Query(10, ge=1, le=100)
):
    """
    Recupera uma prévia dos dados.
    """
    try:
        df = get_dataset(upload_id)
        preview_data = clean_for_json(df.head(rows).to_dict(orient="records"))
        
        return {
            "rows": df.shape[0],
            "columns": df.shape[1],
            "preview": preview_data,
            "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()}
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset com ID {upload_id} não encontrado"
        )
    except Exception as e:
        logger.error(f"Erro ao recuperar prévia: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao recuperar prévia: {str(e)}"
        )

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
from io import BytesIO

from api.services.data_service import process_data_file, get_dataset
from api.config import settings

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Carrega um arquivo CSV ou Excel e retorna metadados sobre o conjunto de dados.
    """
    # Verificar extensão do arquivo
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")
    
    # Verificar se é um tipo de arquivo permitido
    allowed_extensions = ['.csv', '.xlsx', '.xls']
    file_extension = '.' + filename.split('.')[-1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo não suportado. Use {', '.join(allowed_extensions)}"
        )
    
    # Ler conteúdo do arquivo
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo muito grande. Tamanho máximo: {settings.MAX_UPLOAD_SIZE / (1024 * 1024)}MB"
        )
    
    # Gerar ID único para este upload
    upload_id = str(uuid.uuid4())
    
    # Processar o arquivo
    result = process_data_file(
        BytesIO(content), 
        filename, 
        file_extension, 
        upload_id
    )
    
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.message
        )
    
    return result

@router.get("/preview/{upload_id}")
async def get_data_preview(upload_id: str, rows: int = 10):
    """
    Retorna uma prévia dos dados.
    """
    try:
        df = get_dataset(upload_id)
        preview_data = clean_for_json(df.head(rows).to_dict(orient="records"))
        
        return {
            "success": True,
            "preview": preview_data,
            "rows": len(df),
            "columns": df.columns.tolist()
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset com ID {upload_id} não encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter prévia: {str(e)}"
        )

@router.get("/columns/{upload_id}")
async def get_columns(upload_id: str):
    """
    Retorna uma lista de colunas do dataset.
    """
    try:
        df = get_dataset(upload_id)
        
        # Classificar colunas por tipo
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = df.select_dtypes(include=['datetime']).columns.tolist()
        other_cols = [col for col in df.columns if col not in numeric_cols + categorical_cols + datetime_cols]
        
        return {
            "success": True,
            "columns": {
                "all": df.columns.tolist(),
                "numeric": numeric_cols,
                "categorical": categorical_cols,
                "datetime": datetime_cols,
                "other": other_cols
            },
            "rows": len(df)
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset com ID {upload_id} não encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter colunas: {str(e)}"
        )
