import logging
import json
from typing import List, Dict, Any, Optional
import pandas as pd
import time
import traceback
from api.agents.agent_executor import extract_analyses, execute_analysis
from api.agents.react_agent import get_advanced_recommendations, react_token_counter
from api.models import Analysis, AnalysisStatus, RecommendationResponse

# Adicionar contador de tokens dedicado para o serviço
from utils.token_counter import TokenCounter
analysis_service_token_counter = TokenCounter()

logger = logging.getLogger("lean-six-sigma-api.analysis-service")

def get_recommendations(formatted_data: str, dependent_vars: List[str], independent_vars: List[str], objective: str = "") -> str:
    """
    Obtém recomendações de análise utilizando o agente de IA.
    
    Args:
        formatted_data: Dados formatados em JSON string
        dependent_vars: Lista de variáveis dependentes
        independent_vars: Lista de variáveis independentes
        objective: Objetivo da análise
        
    Returns:
        String contendo as recomendações de análise no formato HTML/Markdown
    """
    try:
        logger.info("Iniciando geração de recomendações")
        
        # Usar o agente React para gerar recomendações
        recommendations = get_advanced_recommendations(
            formatted_data,
            dependent_vars,
            independent_vars,
            objective or "Recomendar um plano sequencial de análises para melhoria de processos usando Lean Six Sigma"
        )
        
        # Após gerar recomendações, registrar estatísticas de tokens do React Agent
        logger.info("===== CONTAGEM DE TOKENS REACT AGENT =====")
        token_summary = react_token_counter.get_summary()
        logger.info(f"Total de tokens: {token_summary['total_tokens']}")
        logger.info(f"Prompt tokens: {token_summary['prompt_tokens']}")
        logger.info(f"Completion tokens: {token_summary['completion_tokens']}")
        logger.info(f"Custo estimado: ${token_summary['estimated_cost_usd']:.6f}")
        
        logger.info(f"Recomendações geradas com sucesso: {len(recommendations)} caracteres")
        return recommendations
        
    except Exception as e:
        error_msg = f"Erro ao gerar recomendações: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        
        # Retornar uma mensagem de erro formatada
        return f"""
        <div class="error-message">
            <h3>Erro ao Gerar Recomendações</h3>
            <p>Ocorreu um erro ao tentar gerar recomendações de análise:</p>
            <pre>{str(e)}</pre>
        </div>
        """

def extract_analyses_from_recommendations(recommendations: str, 
                                         dependent_vars: List[str], 
                                         independent_vars: List[str]) -> List[Analysis]:
    """
    Extrai análises estruturadas a partir do texto de recomendações.
    
    Args:
        recommendations: Texto de recomendações
        dependent_vars: Lista de variáveis dependentes (fallback)
        independent_vars: Lista de variáveis independentes (fallback)
        
    Returns:
        Lista de objetos Analysis
    """
    try:
        # Usar o extrator de análises do agent_executor
        raw_analyses = extract_analyses(recommendations)
        
        # Converter para objetos Analysis do modelo Pydantic
        analyses = []
        for i, raw in enumerate(raw_analyses):
            # Garantir que variáveis dependentes e independentes existam
            if not raw.get("dependent_vars"):
                raw["dependent_vars"] = dependent_vars
            if not raw.get("independent_vars"):
                raw["independent_vars"] = independent_vars
                
            # Criar objeto Analysis
            analysis = Analysis(
                number=raw.get("number", i+1),
                name=raw.get("name", f"Análise {i+1}"),
                content=raw.get("content", ""),
                dependent_vars=raw.get("dependent_vars", []),
                independent_vars=raw.get("independent_vars", []),
                status=AnalysisStatus.PENDING
            )
            analyses.append(analysis)
        
        logger.info(f"Extraídas {len(analyses)} análises do texto de recomendações")
        return analyses
        
    except Exception as e:
        logger.error(f"Erro ao extrair análises: {str(e)}\n{traceback.format_exc()}")
        # Retornar lista vazia em caso de erro
        return []

def execute_analysis_from_model(df: pd.DataFrame, analysis: Any) -> Dict[str, Any]:
    """
    Executa uma análise específica usando o modelo Analysis.
    
    Args:
        df: DataFrame com os dados
        analysis: Objeto Analysis ou dicionário com detalhes da análise
        
    Returns:
        Resultados da execução da análise
    """
    try:
        # Debug
        logging.info(f"Executando análise, tipo de input: {type(analysis)}")
        
        # Verificar se já temos um dicionário ou se precisamos converter
        if not isinstance(analysis, dict) and hasattr(analysis, 'dict'):
            analysis_dict = analysis.dict()
        else:
            # Pode ser um dicionário ou um objeto que não tem método .dict()
            analysis_dict = analysis
        
        # Log para depurar
        logging.info(f"Análise para execução: {analysis_dict}")
        
        # Verificar se temos a estrutura mínima necessária
        required_keys = ["number", "name", "dependent_vars", "independent_vars"]
        for key in required_keys:
            if key not in analysis_dict and not hasattr(analysis, key):
                missing = key
                if hasattr(analysis, key):
                    # Se o objeto tem o atributo, usar ele
                    analysis_dict[key] = getattr(analysis, key)
                else:
                    logging.error(f"Chave obrigatória ausente: {key}")
                    return {
                        "success": False,
                        "number": analysis_dict.get("number", 0),
                        "name": analysis_dict.get("name", "Análise desconhecida"),
                        "error": f"Chave obrigatória ausente: {key}",
                        "plots": [],
                        "tables": [],
                        "text_output": f"Erro: chave obrigatória ausente: {key}"
                    }
        
        # Garantir que analysis_dict tenha os campos number e name
        if "number" not in analysis_dict:
            analysis_dict["number"] = 0
        if "name" not in analysis_dict:
            analysis_dict["name"] = "Análise desconhecida"
            
        # Usar o executor baseado em LangGraph se disponível
        try:
            # Primeiro tentar o executor tradicional como fallback seguro
            try:
                from api.agents.agent_executor import execute_analysis as agent_execute_analysis, agent_token_counter
                result = agent_execute_analysis(df, analysis_dict)
                logging.info("Análise executada com executor tradicional")
                
                # Registrar uso de tokens após execução
                logging.info("===== CONTAGEM DE TOKENS AGENT EXECUTOR =====")
                token_summary = agent_token_counter.get_summary()
                logging.info(f"Total de tokens: {token_summary['total_tokens']}")
                logging.info(f"Prompt tokens: {token_summary['prompt_tokens']}")
                logging.info(f"Completion tokens: {token_summary['completion_tokens']}")
                logging.info(f"Custo estimado: ${token_summary['estimated_cost_usd']:.6f}")
                
                # Adicionar informações de tokens ao resultado
                result["token_usage"] = token_summary
                
                # Garantir que o resultado tenha todos os campos obrigatórios
                if "number" not in result:
                    result["number"] = analysis_dict.get("number", 0)
                if "name" not in result:
                    result["name"] = analysis_dict.get("name", "Análise desconhecida")
                    
                return result
            except Exception as trad_error:
                logging.warning(f"Executor tradicional falhou: {str(trad_error)}, tentando LangGraph")
            
            # Tentar usar o executor LangGraph (experimental)
            try:
                from services.analysis_executor import execute_analysis_with_graph, token_counter as graph_token_counter
                result = execute_analysis_with_graph(df, analysis_dict)
                logging.info("Análise executada com LangGraph")
                
                # Registrar uso de tokens após execução
                logging.info("===== CONTAGEM DE TOKENS LANGGRAPH =====")
                token_summary = graph_token_counter.get_summary()
                logging.info(f"Total de tokens: {token_summary['total_tokens']}")
                logging.info(f"Prompt tokens: {token_summary['prompt_tokens']}")
                logging.info(f"Completion tokens: {token_summary['completion_tokens']}")
                logging.info(f"Custo estimado: ${token_summary['estimated_cost_usd']:.6f}")
                
                # Adicionar informações de tokens ao resultado
                result["token_usage"] = token_summary
                
                # Garantir que o resultado tenha todos os campos obrigatórios
                if "number" not in result:
                    result["number"] = analysis_dict.get("number", 0)
                if "name" not in result:
                    result["name"] = analysis_dict.get("name", "Análise desconhecida")
                    
                return result
            except Exception as langgraph_error:
                logging.error(f"Executor LangGraph falhou: {str(langgraph_error)}")
                raise # Re-lançar para usar o executor tradicional como fallback final
                
        except ImportError as imp_error:
            # Se não conseguir importar nenhum dos executores
            logging.warning(f"Nenhum executor disponível: {str(imp_error)}")
            raise ValueError("Nenhum executor de análise disponível")
        
    except Exception as e:
        logging.error(f"Erro ao executar análise: {str(e)}")
        # Retornar erro formatado com todos os campos obrigatórios
        analysis_number = getattr(analysis, "number", 0) if not isinstance(analysis, dict) else analysis.get("number", 0)
        analysis_name = getattr(analysis, "name", "Análise desconhecida") if not isinstance(analysis, dict) else analysis.get("name", "Análise desconhecida")
        
        return {
            "success": False,
            "number": analysis_number,
            "name": analysis_name,
            "plots": [],
            "tables": [],
            "text_output": f"Ocorreu um erro durante a execução: {str(e)}",
            "error": f"Erro ao executar análise: {str(e)}"
        }
