from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import pandas as pd
import io
from api.services.data_service import get_dataset, get_dataset_preview, clean_for_json
from api.agents.code_execution_agent import code_execution_agent
import logging

router = APIRouter()
logger = logging.getLogger("lean-six-sigma-api.data-treatment")

@router.post("/process")
async def process_rule(request: Dict[str, Any]):
    """
    Processa uma regra em linguagem natural e aplica ao dataset usando o agente LangChain/LangGraph.
    """
    try:
        upload_id = request.get('upload_id')
        rule_text = request.get('rule_text')
        
        if not upload_id or not rule_text:
            raise HTTPException(
                status_code=400,
                detail="upload_id e rule_text são obrigatórios"
            )
            
        # Carregar o dataset atual (com possíveis tratamentos anteriores) para obter informações das colunas
        df = get_dataset(upload_id)
        
        # Usar o agente LangChain/LangGraph para processar a regra
        # O resultado substituirá o dataset original
        result = await code_execution_agent.process_rule(
            rule_text=rule_text,
            columns=df.columns.tolist(),
            upload_id=upload_id
        )
        
        if result["success"]:
            # Log para debug
            logger.info(f"Regra aplicada com sucesso para upload_id: {upload_id}")
            
            # Verificar se final_result existe e tem preview
            final_result = result.get("final_result")
            preview = []
            if final_result and isinstance(final_result, dict):
                preview = final_result.get("preview", [])
            
            # Obter informações adicionais do resultado
            structure_info = {
                "structure_changed": False,
                "columns_added": [],
                "columns_removed": []
            }
            
            # Verificar se houve mudanças estruturais comparando colunas originais e finais
            if final_result and isinstance(final_result, dict):
                try:
                    # Tentar carregar dataset original para comparar colunas
                    original_df = get_dataset(upload_id)
                    original_columns = set(original_df.columns.tolist())
                    
                    # Obter colunas atuais
                    current_columns = set(final_result.get("columns", []))
                    
                    # Identificar mudanças
                    columns_added = current_columns - original_columns
                    columns_removed = original_columns - current_columns
                    
                    structure_info = {
                        "structure_changed": len(columns_added) > 0 or len(columns_removed) > 0,
                        "columns_added": list(columns_added),
                        "columns_removed": list(columns_removed)
                    }
                except Exception as e:
                    logger.error(f"Erro ao detectar mudanças estruturais: {str(e)}")
            
            response_data = {
                "success": True,
                "message": "Regra aplicada com sucesso",
                "preview": preview,
                "generated_code": result["generated_code"],
                "execution_output": result["execution_output"],
                "attempt_count": result["attempt_count"],
                # Incluir informações estruturais no resultado
                "final_result": {
                    **(final_result or {}),
                    **structure_info
                }
            }
            
            return clean_for_json(response_data)
        else:
            return {
                "success": False,
                "message": f"Erro ao aplicar regra: {result.get('execution_error', 'Erro desconhecido')}",
                "generated_code": result["generated_code"],
                "execution_error": result["execution_error"],
                "attempt_count": result["attempt_count"]
            }
            
    except Exception as e:
        logger.error(f"Erro ao processar regra: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar regra: {str(e)}"
        )

@router.get("/preview/{upload_id}")
async def get_data_preview(upload_id: str):
    """
    Obtém a prévia atual dos dados (incluindo tratamentos aplicados).
    """
    try:
        result = get_dataset_preview(upload_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(
                status_code=404,
                detail=result.get("message", "Dataset não encontrado")
            )
            
    except Exception as e:
        logger.error(f"Erro ao obter prévia do dataset: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter prévia: {str(e)}"
        )

@router.get("/download/{upload_id}")
async def download_treated_data(upload_id: str, format: str = "csv"):
    """
    Baixa os dados tratados em formato CSV ou XLSX.
    """
    try:
        # Verificar formato suportado
        if format not in ["csv", "xlsx"]:
            raise HTTPException(
                status_code=400,
                detail="Formato não suportado. Use 'csv' ou 'xlsx'"
            )
        
        # Carregar o dataset (incluindo tratamentos aplicados)
        df = get_dataset(upload_id)
        
        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail="Dataset não encontrado ou vazio"
            )
        
        # Criar buffer em memória
        output = io.BytesIO()
        
        if format == "csv":
            # Converter para CSV
            csv_data = df.to_csv(index=False, encoding='utf-8')
            output.write(csv_data.encode('utf-8'))
            content_type = "text/csv"
            filename = f"dados_tratados_{upload_id}.csv"
        else:  # xlsx
            # Converter para Excel
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Dados Tratados')
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"dados_tratados_{upload_id}.xlsx"
        
        # Resetar posição do buffer
        output.seek(0)
        
        # Retornar como resposta de streaming
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Erro ao baixar dados tratados: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao baixar dados: {str(e)}"
        )

@router.get("/columns/{upload_id}")
async def get_dataset_columns(upload_id: str):
    """
    Obtém apenas as colunas atuais do dataset (para atualização assíncrona).
    """
    try:
        result = get_dataset_preview(upload_id)
        
        if result.get("success"):
            return {
                "success": True,
                "columns": result.get("columns", []),
                "rows": result.get("rows", 0),
                "message": "Colunas obtidas com sucesso"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result.get("message", "Dataset não encontrado")
            )
            
    except Exception as e:
        logger.error(f"Erro ao obter colunas do dataset: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter colunas: {str(e)}"
        )