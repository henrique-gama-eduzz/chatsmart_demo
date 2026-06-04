import pandas as pd
import numpy as np
import json
import os
import uuid
from io import BytesIO
from typing import List, Dict, Any, Optional
import logging

from api.config import settings
from api.models import DataUploadResponse

logger = logging.getLogger("lean-six-sigma-api.data-service")

def clean_for_json(obj):
    """
    Limpa valores problemáticos para serialização JSON.
    """
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        if np.isnan(obj):
            return None
        elif np.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        else:
            return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj

def process_data_file(file_content: BytesIO, filename: str, file_extension: str, upload_id: str) -> DataUploadResponse:
    """
    Processa um arquivo de dados (CSV ou Excel) e salva no armazenamento.
    """
    try:
        # Carregar o arquivo no pandas
        if file_extension == '.csv':
            df = pd.read_csv(file_content)
        else:
            df = pd.read_excel(file_content)
        
        # Salvar o DataFrame para uso posterior
        save_path = os.path.join(settings.UPLOAD_DIR, f"{upload_id}.pkl")
        df.to_pickle(save_path)
        
        # Criar resposta com dados limpos para JSON
        preview_data = clean_for_json(df.head(5).to_dict(orient="records"))
        
        response = DataUploadResponse(
            success=True,
            columns=df.columns.tolist(),
            rows=len(df),
            preview=preview_data,
            message=f"Arquivo {filename} carregado com sucesso",
            upload_id=upload_id
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao processar arquivo {filename}: {str(e)}")
        return DataUploadResponse(
            success=False,
            message=f"Erro ao processar arquivo: {str(e)}",
        )

def get_dataset(upload_id: str) -> pd.DataFrame:
    """
    Recupera um dataset com base no ID de upload.
    """
    file_path = os.path.join(settings.UPLOAD_DIR, f"{upload_id}.pkl")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset não encontrado: {upload_id}")
    
    try:
        df = pd.read_pickle(file_path)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar dataset {upload_id}: {str(e)}")
        raise

def extract_data_info(df: pd.DataFrame, dependent_vars: List[str], independent_vars: List[str]) -> Dict[str, Any]:
    """
    Extrai informações relevantes do dataset.
    """
    info = {
        "dataset_shape": df.shape,
        "variables": {
            "dependent": [],
            "independent": []
        },
        "correlations": {}
    }
    
    # Get info for each dependent variable
    for var in dependent_vars:
        dep_var_info = {
            "name": var,
            "data_type": str(df[var].dtype),
            "missing_values": int(df[var].isna().sum()),
            "unique_values": int(df[var].nunique()),
            "is_numeric": pd.api.types.is_numeric_dtype(df[var])
        }
        
        if dep_var_info["is_numeric"]:
            dep_var_info["min"] = float(df[var].min())
            dep_var_info["max"] = float(df[var].max())
            dep_var_info["mean"] = float(df[var].mean())
            dep_var_info["std"] = float(df[var].std())
            
        info["variables"]["dependent"].append(dep_var_info)
    
    # Get info for each independent variable
    for var in independent_vars:
        var_info = {
            "name": var,
            "data_type": str(df[var].dtype),
            "missing_values": int(df[var].isna().sum()),
            "unique_values": int(df[var].nunique()),
            "is_numeric": pd.api.types.is_numeric_dtype(df[var])
        }
        
        if var_info["is_numeric"]:
            var_info["min"] = float(df[var].min())
            var_info["max"] = float(df[var].max())
            var_info["mean"] = float(df[var].mean())
            var_info["std"] = float(df[var].std())
            
        info["variables"]["independent"].append(var_info)
    
    # Calculate correlations between numeric variables
    all_vars = dependent_vars + independent_vars
    numeric_cols = [col for col in all_vars if pd.api.types.is_numeric_dtype(df[col])]
    
    if len(numeric_cols) > 1:
        corr_matrix = df[numeric_cols].corr().round(3)
        for col1 in numeric_cols:
            info["correlations"][col1] = {}
            for col2 in numeric_cols:
                if col1 != col2:
                    info["correlations"][col1][col2] = float(corr_matrix.loc[col1, col2])
    
    return info

def format_data_for_agent(df: pd.DataFrame, data_info: Dict[str, Any], 
                         independent_vars: List[str], dependent_vars: List[str], 
                         column_descriptions: Optional[Dict[str, str]] = None,
                         objective: Optional[str] = None) -> str:
    """
    Formata os dados para o agente de IA.
    
    Args:
        df: DataFrame com os dados
        data_info: Informações extraídas dos dados
        dependent_vars: Lista de variáveis dependentes
        independent_vars: Lista de variáveis independentes
        column_descriptions: Descrições das colunas (opcional)
        objective: Objetivo da análise (opcional)
        
    Returns:
        String JSON com dados formatados
    """
    try:
        # Create a completely clean dictionary with only native Python types
        formatted_data = {
            "dataset_overview": {
                "rows": int(data_info["dataset_shape"][0]),
                "columns": int(data_info["dataset_shape"][1]),
                "dependent_variables": list(dependent_vars),
                "independent_variables": list(independent_vars)
            },
            "variable_details": {
                "dependent": [],
                "independent": []
            },
            "correlations": {}
        }
        
        # Adicionar objetivo se fornecido
        if objective:
            formatted_data["dataset_overview"]["objective"] = objective
        
        # Adicionar estatísticas gerais se disponíveis
        if "summary_stats" in data_info:
            for key, value in data_info["summary_stats"].items():
                formatted_data["dataset_overview"][key] = value
        
        # Manually copy dependent variable details with explicit type conversion
        for var_info in data_info["variables"]["dependent"]:
            clean_var_info = {k: v for k, v in var_info.items() if k != "value_distribution"}
            
            # Adicionar distribuição de valores resumida para variáveis categóricas
            if not var_info["is_numeric"] and "value_distribution" in var_info:
                # Limitar a 10 valores mais frequentes
                top_values = sorted(var_info["value_distribution"].items(), 
                                   key=lambda x: x[1], reverse=True)[:10]
                clean_var_info["top_values"] = dict(top_values)
                
            formatted_data["variable_details"]["dependent"].append(clean_var_info)
        
        # Manually copy independent variable details with explicit type conversion
        for var_info in data_info["variables"]["independent"]:
            clean_var_info = {k: v for k, v in var_info.items() if k != "value_distribution"}
            
            # Adicionar distribuição de valores resumida para variáveis categóricas
            if not var_info["is_numeric"] and "value_distribution" in var_info:
                # Limitar a 10 valores mais frequentes
                top_values = sorted(var_info["value_distribution"].items(), 
                                   key=lambda x: x[1], reverse=True)[:10]
                clean_var_info["top_values"] = dict(top_values)
                
            formatted_data["variable_details"]["independent"].append(clean_var_info)
        
        # Copy correlation data with explicit type conversion
        for var1, correlations in data_info["correlations"].items():
            formatted_data["correlations"][var1] = {}
            for var2, corr_value in correlations.items():
                formatted_data["correlations"][var1][var2] = float(corr_value)
        
        # Add column descriptions if provided
        if column_descriptions:
            formatted_data["column_descriptions"] = {}
            for col, desc in column_descriptions.items():
                if desc:  # Only add non-empty descriptions
                    formatted_data["column_descriptions"][col] = str(desc)
        
        # Return as JSON string
        return json.dumps(formatted_data, ensure_ascii=False, default=str)
    
    except Exception as e:
        logger.error(f"Erro ao formatar dados para o agente: {str(e)}")
        # Return simplified data in case of error
        return json.dumps({
            "dataset_overview": {
                "rows": df.shape[0],
                "columns": df.shape[1],
                "dependent_variables": dependent_vars,
                "independent_variables": independent_vars
            }
        }, ensure_ascii=False)

def save_treated_dataset(upload_id: str, treated_df: pd.DataFrame, keep_backup: bool = True) -> bool:
    """
    Salva o dataset tratado substituindo o original.
    
    Args:
        upload_id: ID do upload
        treated_df: DataFrame com os dados tratados
        keep_backup: Se True, cria um backup do arquivo original antes de substituir
        
    Returns:
        bool: True se salvou com sucesso, False caso contrário
    """
    try:
        file_path = os.path.join(settings.UPLOAD_DIR, f"{upload_id}.pkl")
        
        # Criar backup do arquivo original se solicitado
        if keep_backup:
            backup_path = os.path.join(settings.UPLOAD_DIR, f"{upload_id}_backup.pkl")
            if os.path.exists(file_path):
                import shutil
                shutil.copy2(file_path, backup_path)
                logger.info(f"Backup do dataset original criado: {backup_path}")
        
        # Salvar o dataset tratado, substituindo o original
        treated_df.to_pickle(file_path)
        
        logger.info(f"Dataset tratado salvo com sucesso: {upload_id}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar dataset tratado {upload_id}: {str(e)}")
        return False

def get_dataset_preview(upload_id: str, num_rows: int = 10) -> Dict[str, Any]:
    """
    Obtém uma prévia do dataset.
    
    Args:
        upload_id: ID do upload
        num_rows: Número de linhas para a prévia
        
    Returns:
        Dict com informações da prévia
    """
    try:
        df = get_dataset(upload_id)
        
        # Limpar dados para serialização JSON
        preview_data = clean_for_json(df.head(num_rows).to_dict(orient="records"))
        
        return {
            "success": True,
            "preview": preview_data,
            "columns": df.columns.tolist(),
            "rows": len(df),
            "message": "Prévia obtida com sucesso"
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter prévia do dataset {upload_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Erro ao obter prévia: {str(e)}"
        }