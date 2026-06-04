"""
Funções utilitárias para processamento e análise de dados.
"""
import pandas as pd
import numpy as np
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("lean-six-sigma-api.utils")

def extract_data_info(df: pd.DataFrame, dependent_vars: List[str], independent_vars: List[str]) -> Dict[str, Any]:
    """
    Extrai informações estatísticas e descritivas dos dados.
    
    Args:
        df: DataFrame com os dados
        dependent_vars: Lista de nomes de variáveis dependentes
        independent_vars: Lista de nomes de variáveis independentes
        
    Returns:
        Dicionário com informações estatísticas dos dados
    """
    info = {
        "dataset_shape": df.shape,
        "variables": {
            "dependent": [],
            "independent": []
        },
        "correlations": {},
        "summary_stats": {}
    }
    
    # Estatísticas gerais do dataset
    info["summary_stats"]["missing_values_total"] = int(df.isna().sum().sum())
    info["summary_stats"]["missing_percent"] = float(df.isna().sum().sum() / (df.shape[0] * df.shape[1]) * 100)
    info["summary_stats"]["duplicate_rows"] = int(df.duplicated().sum())
    
    # Para cada variável dependente
    for var in dependent_vars:
        var_info = {
            "name": var,
            "data_type": str(df[var].dtype),
            "missing_values": int(df[var].isna().sum()),
            "missing_percent": float(df[var].isna().sum() / len(df) * 100),
            "unique_values": int(df[var].nunique()),
            "is_numeric": pd.api.types.is_numeric_dtype(df[var])
        }
        
        # Para variáveis numéricas, adicionar estatísticas descritivas
        if var_info["is_numeric"]:
            var_info["min"] = float(df[var].min())
            var_info["max"] = float(df[var].max())
            var_info["mean"] = float(df[var].mean())
            var_info["median"] = float(df[var].median())
            var_info["std"] = float(df[var].std())
            var_info["skew"] = float(df[var].skew())
            var_info["kurtosis"] = float(df[var].kurtosis())
            var_info["q1"] = float(df[var].quantile(0.25))
            var_info["q3"] = float(df[var].quantile(0.75))
        # Para variáveis categóricas, adicionar distribuição de valores
        else:
            value_counts = df[var].value_counts().to_dict()
            var_info["value_distribution"] = {str(k): int(v) for k, v in value_counts.items()}
            
        info["variables"]["dependent"].append(var_info)
    
    # Para cada variável independente
    for var in independent_vars:
        var_info = {
            "name": var,
            "data_type": str(df[var].dtype),
            "missing_values": int(df[var].isna().sum()),
            "missing_percent": float(df[var].isna().sum() / len(df) * 100),
            "unique_values": int(df[var].nunique()),
            "is_numeric": pd.api.types.is_numeric_dtype(df[var])
        }
        
        # Para variáveis numéricas, adicionar estatísticas descritivas
        if var_info["is_numeric"]:
            var_info["min"] = float(df[var].min())
            var_info["max"] = float(df[var].max())
            var_info["mean"] = float(df[var].mean())
            var_info["median"] = float(df[var].median())
            var_info["std"] = float(df[var].std())
            var_info["skew"] = float(df[var].skew())
            var_info["kurtosis"] = float(df[var].kurtosis())
            var_info["q1"] = float(df[var].quantile(0.25))
            var_info["q3"] = float(df[var].quantile(0.75))
        # Para variáveis categóricas, adicionar distribuição de valores
        else:
            value_counts = df[var].value_counts().to_dict()
            var_info["value_distribution"] = {str(k): int(v) for k, v in value_counts.items()}
            
        info["variables"]["independent"].append(var_info)
    
    # Calcular correlações entre variáveis numéricas
    numeric_vars = [var for var in dependent_vars + independent_vars if pd.api.types.is_numeric_dtype(df[var])]
    if len(numeric_vars) > 1:
        corr_matrix = df[numeric_vars].corr().round(3)
        for var1 in numeric_vars:
            info["correlations"][var1] = {}
            for var2 in numeric_vars:
                if var1 != var2:
                    info["correlations"][var1][var2] = float(corr_matrix.loc[var1, var2])
    
    return info

def format_data_for_agent(df: pd.DataFrame, data_info: Dict[str, Any], 
                          dependent_vars: List[str], independent_vars: List[str], 
                          column_descriptions: Optional[Dict[str, str]] = None) -> str:
    """
    Formata os dados para o agente de IA.
    
    Args:
        df: DataFrame com os dados
        data_info: Informações extraídas dos dados
        dependent_vars: Lista de variáveis dependentes
        independent_vars: Lista de variáveis independentes
        column_descriptions: Descrições das colunas (opcional)
        
    Returns:
        String JSON com dados formatados
    """
    formatted_data = {
        "dataset_overview": {
            "rows": int(data_info["dataset_shape"][0]),
            "columns": int(data_info["dataset_shape"][1]),
            "dependent_variables": list(dependent_vars),
            "independent_variables": list(independent_vars),
            "missing_values_total": data_info["summary_stats"]["missing_values_total"],
            "duplicate_rows": data_info["summary_stats"]["duplicate_rows"]
        },
        "variable_details": {
            "dependent": [],
            "independent": []
        },
        "correlations": {}
    }
    
    # Adicionar detalhes das variáveis dependentes
    for var_info in data_info["variables"]["dependent"]:
        clean_var_info = {k: v for k, v in var_info.items() if k != "value_distribution"}
        
        # Adicionar distribuição de valores resumida para variáveis categóricas
        if not var_info["is_numeric"] and "value_distribution" in var_info:
            # Limitar a 10 valores mais frequentes
            top_values = sorted(var_info["value_distribution"].items(), 
                               key=lambda x: x[1], reverse=True)[:10]
            clean_var_info["top_values"] = dict(top_values)
            
        formatted_data["variable_details"]["dependent"].append(clean_var_info)
    
    # Adicionar detalhes das variáveis independentes
    for var_info in data_info["variables"]["independent"]:
        clean_var_info = {k: v for k, v in var_info.items() if k != "value_distribution"}
        
        # Adicionar distribuição de valores resumida para variáveis categóricas
        if not var_info["is_numeric"] and "value_distribution" in var_info:
            # Limitar a 10 valores mais frequentes
            top_values = sorted(var_info["value_distribution"].items(), 
                               key=lambda x: x[1], reverse=True)[:10]
            clean_var_info["top_values"] = dict(top_values)
            
        formatted_data["variable_details"]["independent"].append(clean_var_info)
    
    # Adicionar correlações
    for var1, correlations in data_info["correlations"].items():
        formatted_data["correlations"][var1] = {}
        for var2, corr_value in correlations.items():
            formatted_data["correlations"][var1][var2] = float(corr_value)
    
    # Adicionar descrições das colunas se fornecidas
    if column_descriptions:
        formatted_data["column_descriptions"] = {}
        for col, desc in column_descriptions.items():
            if desc:  # Adicionar apenas descrições não vazias
                formatted_data["column_descriptions"][col] = str(desc)
    
    # Converter para JSON
    return json.dumps(formatted_data, ensure_ascii=False)

def detect_data_quality_issues(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detecta problemas de qualidade nos dados.
    
    Args:
        df: DataFrame com os dados
        
    Returns:
        Dicionário com problemas de qualidade detectados
    """
    issues = {
        "missing_values": {},
        "outliers": {},
        "imbalanced_categories": {},
        "data_type_issues": [],
        "recommendations": []
    }
    
    # Detectar valores faltantes
    missing_counts = df.isna().sum()
    missing_percent = (missing_counts / len(df) * 100).round(2)
    
    for col in df.columns:
        if missing_counts[col] > 0:
            issues["missing_values"][col] = {
                "count": int(missing_counts[col]),
                "percent": float(missing_percent[col])
            }
            
            # Adicionar recomendação se mais de 5% dos valores estiverem faltando
            if missing_percent[col] > 5:
                issues["recommendations"].append(f"Considere tratar valores faltantes em '{col}' ({missing_percent[col]}%)")
    
    # Detectar outliers em variáveis numéricas
    for col in df.select_dtypes(include=['number']):
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
        
        if not outliers.empty:
            issues["outliers"][col] = {
                "count": int(outliers.shape[0]),
                "percent": float(outliers.shape[0] / len(df) * 100),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound)
            }
            
            # Adicionar recomendação
            issues["recommendations"].append(f"Considere tratar outliers em '{col}' ({outliers.shape[0]} valores)")
    
    # Detectar categorias desbalanceadas
    for col in df.select_dtypes(include=['object', 'category']):
        value_counts = df[col].value_counts(normalize=True)
        if value_counts.iloc[0] > 0.9:
            issues["imbalanced_categories"][col] = {
                "most_frequent_value": value_counts.index[0],
                "frequency": float(value_counts.iloc[0] * 100)
            }
            
            # Adicionar recomendação
            issues["recommendations"].append(f"Considere tratar desbalanceamento em '{col}' (valor mais frequente: {value_counts.index[0]} - {value_counts.iloc[0] * 100}%)")
    
    # Detectar problemas de tipo de dados
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                pd.to_numeric(df[col])
                issues["data_type_issues"].append(f"Coluna '{col}' pode ser convertida para numérica")
            except ValueError:
                pass
    
    return issues
