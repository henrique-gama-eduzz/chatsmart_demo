from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Dict, Any
import logging
import time

from api.models import (
    AnalysisRequest, 
    RecommendationResponse, 
    ExecuteAnalysisRequest,
    ExecuteAnalysisResponse,
    Analysis,
    AnalysisStatus,
    AnalysisResult
)
from api.services.data_service import get_dataset, extract_data_info, format_data_for_agent
from api.services.analysis_service import (
    get_recommendations, 
    extract_analyses_from_recommendations,
    execute_analysis_from_model
)
from api.config import settings
import re 
from api.agents.react_agent import react_token_counter
from api.agents.agent_executor import agent_token_counter
from utils.token_counter import TokenCounter

# Criar contador de tokens para o router
router_token_counter = TokenCounter()

router = APIRouter()
logger = logging.getLogger("lean-six-sigma-api.analysis")

# Cache de recomendações e análises em memória
recommendations_cache = {}
analyses_cache = {}

@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_analyses(request: AnalysisRequest):
    """
    Gera recomendações de análises com base no dataset e variáveis selecionadas.
    """
    try:
        # Verificar se o dataset existe
        try:
            df = get_dataset(request.upload_id)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset com ID {request.upload_id} não encontrado"
            )
        
        # Validar variáveis selecionadas
        all_columns = df.columns.tolist()
        for var in request.variables.dependent_vars + request.variables.independent_vars:
            if var not in all_columns:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Variável '{var}' não encontrada no dataset"
                )
        
        # Iniciar timer
        start_time = time.time()
        
        # Extrair informações do dataset
        data_info = extract_data_info(
            df, 
            request.variables.dependent_vars, 
            request.variables.independent_vars
        )
        
        # Formatar dados para o agente
        formatted_data = format_data_for_agent(
            df,
            data_info,
            request.variables.dependent_vars,
            request.variables.independent_vars,
            request.variables.column_descriptions
        )
        
        # Extrair objetivo da análise
        objective = request.variables.objective if hasattr(request.variables, "objective") else ""
        
        # Gerar recomendações
        recommendations = get_recommendations(
            formatted_data,
            request.variables.dependent_vars,
            request.variables.independent_vars,
            objective  # Passar o objetivo para a função
        )
        
        # Extrair análises das recomendações
        analyses = extract_analyses_from_recommendations(
            recommendations,
            request.variables.dependent_vars,
            request.variables.independent_vars
        )
        
        # Calcular tempo de processamento
        processing_time = time.time() - start_time
        
        # Coletar estatísticas de tokens após execução
        token_stats = {
            "react_agent": react_token_counter.get_summary(),
            "total_tokens": react_token_counter.get_summary()["total_tokens"],
            "estimated_cost_usd": react_token_counter.get_summary()["estimated_cost_usd"]
        }
        
        # Registrar estatísticas no log
        logger.info("===== ESTATÍSTICAS DE TOKENS - RECOMENDAÇÃO =====")
        logger.info(f"Total de tokens: {token_stats['total_tokens']}")
        logger.info(f"Custo estimado: ${token_stats['estimated_cost_usd']:.6f}")
        logger.info("===============================================")
        
        # Quando armazenamos no cache, vamos garantir que os dados sejam serializáveis
        # Convertendo objetos Pydantic para dicionários para evitar problemas de serialização
        serializable_analyses = []
        for analysis in analyses:
            # Converter objeto Pydantic para dicionário
            if hasattr(analysis, 'dict'):
                analysis_dict = analysis.dict()
            else:
                # Se já for um dicionário, usar como está
                analysis_dict = analysis
            serializable_analyses.append(analysis_dict)
        
        recommendations_cache[request.upload_id] = recommendations
        analyses_cache[request.upload_id] = serializable_analyses
        
        # Logging para depurar
        logger.info(f"Armazenadas {len(serializable_analyses)} análises no cache para o ID {request.upload_id}")
        
        return RecommendationResponse(
            success=True,
            message=f"Recomendações geradas com sucesso: {len(serializable_analyses)} análises",
            recommendations=recommendations,
            analyses=analyses,
            processing_time=processing_time,
            token_usage=token_stats  # Adicionar estatísticas de tokens à resposta
        )
    
    except Exception as e:
        logger.error(f"Erro ao gerar recomendações: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar recomendações: {str(e)}"
        )

@router.get("/recommendations/{upload_id}", response_model=RecommendationResponse)
async def get_cached_recommendations(upload_id: str):
    """
    Recupera recomendações previamente geradas para um dataset.
    """
    if upload_id not in recommendations_cache:
        raise HTTPException(
            status_code=404, 
            detail="Nenhuma recomendação encontrada para este dataset. Execute '/recommend' primeiro."
        )
    
    return RecommendationResponse(
        success=True,
        message="Recomendações recuperadas do cache",
        recommendations=recommendations_cache[upload_id],
        analyses=analyses_cache.get(upload_id, []),
        processing_time=0.0  # Recuperação do cache
    )

@router.post("/execute", response_model=ExecuteAnalysisResponse)
async def execute_single_analysis(request: ExecuteAnalysisRequest):
    """
    Executa uma análise específica em um dataset.
    """
    try:
        # Log para debugging
        logger.info(f"Recebida requisição para análise: {request.upload_id}, análise #{request.analysis_number}")
        logger.info(f"Variáveis no request: dependent_vars={getattr(request, 'dependent_vars', None)}, independent_vars={getattr(request, 'independent_vars', None)}")
        
        # Validar as variáveis no request antes de qualquer processamento
        if hasattr(request, 'dependent_vars') and request.dependent_vars:
            # Limpar potenciais descritores longos que não são realmente variáveis
            clean_dep_vars = []
            for var in request.dependent_vars:
                # Filtrar textos longos ou com caracteres específicos (provavelmente explicativos)
                if isinstance(var, str) and len(var) <= 30 and '.' not in var and ':' not in var and ';' not in var and 'é' not in var.lower():
                    clean_dep_vars.append(var)
                else:
                    logger.warning(f"Removida variável dependente inválida: '{var[:50]}...'")
            
            # Atualizar variáveis dependentes limpas
            request.dependent_vars = clean_dep_vars
            logger.info(f"Variáveis dependentes limpas: {request.dependent_vars}")
        
        if hasattr(request, 'independent_vars') and request.independent_vars:
            # Limpar potenciais descritores longos que não são realmente variáveis
            clean_indep_vars = []
            for var in request.independent_vars:
                # Filtrar textos longos ou com caracteres específicos (provavelmente explicativos)
                if isinstance(var, str) and len(var) <= 30 and '.' not in var and ':' not in var and ';' not in var and 'é' not in var.lower():
                    clean_indep_vars.append(var)
                else:
                    logger.warning(f"Removida variável independente inválida: '{var[:50]}...'")
            
            # Atualizar variáveis independentes limpas
            request.independent_vars = clean_indep_vars
            logger.info(f"Variáveis independentes limpas: {request.independent_vars}")
            
        if hasattr(request, 'analysis_detail') and request.analysis_detail:
            logger.info(f"Detalhes adicionais recebidos: {len(request.analysis_detail)} caracteres")
        
        # Verificar se o dataset existe
        try:
            df = get_dataset(request.upload_id)
            logger.info(f"Dataset carregado: {df.shape}")
        except FileNotFoundError:
            logger.error(f"Dataset não encontrado: {request.upload_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset com ID {request.upload_id} não encontrado"
            )
        
        # Debug logging
        logger.info(f"IDs disponíveis no cache: {list(analyses_cache.keys())}")
        
        # Verificar se temos análises para este dataset
        if request.upload_id not in analyses_cache:
            # Inicializar o cache para este upload_id se necessário
            logger.info(f"Criando cache para upload_id: {request.upload_id}")
            analyses_cache[request.upload_id] = []
            
            # Tentar regenerar as análises a partir das recomendações
            if request.upload_id in recommendations_cache:
                logger.info("Tentando reconstruir análises a partir das recomendações")
                
                # Reconstruir análises a partir das recomendações
                dependent_vars = []
                independent_vars = []
                
                # Buscar informações do dataset para reconstruir as variáveis
                try:
                    temp_df = get_dataset(request.upload_id)
                    # Usar metade das colunas como variáveis dependentes e metade como independentes
                    columns = temp_df.columns.tolist()
                    dependent_vars = columns[:max(1, len(columns)//3)]  # Pelo menos uma variável dependente
                    independent_vars = columns[len(dependent_vars):]
                    
                    logger.info(f"Variáveis reconstruídas: Dependentes={dependent_vars}, Independentes={independent_vars}")
                except:
                    logger.error("Não foi possível reconstruir variáveis")
                
                # Extrair análises das recomendações
                recommendations = recommendations_cache[request.upload_id]
                logger.info(f"Recomendações encontradas: {len(recommendations)} caracteres")
                
                analyses = extract_analyses_from_recommendations(
                    recommendations,
                    dependent_vars,
                    independent_vars
                )
                
                # Se conseguimos extrair análises, armazená-las no cache
                if analyses:
                    # Converter para dicionários se forem objetos Pydantic
                    serializable_analyses = []
                    for analysis in analyses:
                        if hasattr(analysis, 'dict'):
                            analysis_dict = analysis.dict()
                        else:
                            analysis_dict = analysis
                        serializable_analyses.append(analysis_dict)
                    
                    analyses_cache[request.upload_id] = serializable_analyses
                    logger.info(f"Análises reconstruídas com sucesso: {len(serializable_analyses)} análises")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail="Não foi possível extrair análises das recomendações. Execute '/recommend' novamente."
                    )
            
            # Sempre criar uma análise a partir do analysis_detail se fornecido, 
            # mesmo que já existam recomendações 
            if request.analysis_detail:
                logger.info("Criando análise a partir do detail fornecido")
                
                # Extrair dependentes e independentes do texto se possível
                dep_vars = []
                indep_vars = []
                
                # Tentar extrair variáveis do texto usando regex melhorado
                dep_patterns = [
                    r'[Vv]ariáveis\s+(?:a\s+[Ss]erem\s+[Uu]tilizadas\s+)?\n?\s*[Vv]ariáveis\s+dependentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Vv]ariáveis\s+dependentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Dd]ependentes?\s*:?\s*"?([^"\n]+)"?'
                ]
                
                for pattern in dep_patterns:
                    dep_match = re.search(pattern, request.analysis_detail, re.MULTILINE | re.DOTALL)
                    if dep_match:
                        dep_vars = [v.strip() for v in dep_match.group(1).split(',')]
                        logger.info(f"Variáveis dependentes extraídas: {dep_vars}")
                        break
                
                indep_patterns = [
                    r'[Vv]ariáveis\s+(?:a\s+[Ss]erem\s+[Uu]tilizadas\s+)?\n?\s*[Vv]ariáveis\s+independentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Vv]ariáveis\s+independentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Ii]ndependentes?\s*:?\s*"?([^"\n]+)"?'
                ]
                
                for pattern in indep_patterns:
                    indep_match = re.search(pattern, request.analysis_detail, re.MULTILINE | re.DOTALL)
                    if indep_match:
                        indep_vars = [v.strip() for v in indep_match.group(1).split(',')]
                        logger.info(f"Variáveis independentes extraídas: {indep_vars}")
                        break
                
                # Se não conseguiu extrair, tente usar algumas colunas do DataFrame
                if not dep_vars and not indep_vars and df is not None:
                    cols = df.columns.tolist()
                    logger.info(f"Não foi possível extrair variáveis. Colunas disponíveis: {cols}")
                    dep_vars = cols[:1]  # Primeira coluna como dependente
                    indep_vars = cols[1:3] if len(cols) > 2 else cols[1:2] if len(cols) > 1 else []  # Próximas colunas como independentes
                    logger.info(f"Usando variáveis padrão: dep={dep_vars}, indep={indep_vars}")
                
                # Tentar extrair o nome da análise
                name_patterns = [
                    r'Analise:\s*([^\n]+)',
                    r'Análise\s+\d+\s*[-:]\s*([^\n]+)'
                ]
                
                analysis_name = f"Análise {request.analysis_number}"
                for pattern in name_patterns:
                    name_match = re.search(pattern, request.analysis_detail)
                    if name_match:
                        analysis_name = name_match.group(1).strip()
                        break
                
                # Criar uma análise simples a partir dos dados disponíveis
                new_analysis = {
                    "number": request.analysis_number,
                    "name": analysis_name,
                    "content": request.analysis_detail,
                    "dependent_vars": dep_vars,
                    "independent_vars": indep_vars,
                    "status": "pending"
                }
                
                # Verificar se já existe uma análise com esse número
                for idx, analysis in enumerate(analyses_cache[request.upload_id]):
                    if isinstance(analysis, dict) and analysis.get("number") == request.analysis_number:
                        analyses_cache[request.upload_id][idx] = new_analysis
                        logger.info(f"Análise #{request.analysis_number} atualizada no cache")
                        break
                else:
                    # Adicionar nova análise se não existir
                    analyses_cache[request.upload_id].append(new_analysis)
                    logger.info(f"Nova análise #{request.analysis_number} adicionada ao cache")
                
                # Adicionalmente, armazenar uma versão vazia de recomendações se não existir
                if request.upload_id not in recommendations_cache:
                    recommendations_cache[request.upload_id] = f"Análise {request.analysis_number}: {analysis_name}\n\n{request.analysis_detail}"
                    logger.info(f"Cache de recomendações criado para {request.upload_id}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="É necessário fornecer detalhes da análise (analysis_detail) quando não existem análises prévias"
                )
        
        # Garantir que variáveis do request tenham prioridade sobre o conteúdo markdown
        # Se existirem análises no cache e estas já tiverem variáveis definidas, use-as
        if request.upload_id in analyses_cache:
            for a in analyses_cache[request.upload_id]:
                current_number = a.get("number", None) if isinstance(a, dict) else getattr(a, "number", None)
                if current_number == request.analysis_number:
                    if isinstance(a, dict):
                        dep_vars = a.get("dependent_vars", [])
                        indep_vars = a.get("independent_vars", [])
                        
                        # Prepara a análise preservando as variáveis originais
                        if "analysis" not in locals():
                            analysis = {
                                "number": request.analysis_number,
                                "name": a.get("name", f"Análise {request.analysis_number}"),
                                "content": request.analysis_detail or a.get("content", ""),
                                "dependent_vars": dep_vars,
                                "independent_vars": indep_vars,
                                "status": "pending"
                            }
                    break
        
        # Encontrar a análise solicitada
        analysis = None
        for a in analyses_cache[request.upload_id]:
            # Verificar tanto pelo número como atributo quanto pela chave no dicionário
            if (isinstance(a, dict) and a.get("number") == request.analysis_number) or \
               (hasattr(a, "number") and a.number == request.analysis_number):
                analysis = a
                break
        
        if not analysis:
            # Se a análise não existe, mas temos analysis_detail, criar a análise agora
            if request.analysis_detail:
                logger.info(f"Análise {request.analysis_number} não encontrada, criando dinamicamente")
                
                # Criar análise sob demanda usando o mesmo código acima
                # (Aqui poderíamos refatorar para uma função, mas para simplicidade estou repetindo)
                dep_vars = []
                indep_vars = []
                
                # Extração de variáveis dependentes e independentes usando regex
                dep_patterns = [
                    r'[Vv]ariáveis\s+(?:a\s+[Ss]erem\s+[Uu]tilizadas\s+)?\n?\s*[Vv]ariáveis\s+dependentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Vv]ariáveis\s+dependentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Dd]ependentes?\s*:?\s*"?([^"\n]+)"?'
                ]
                
                for pattern in dep_patterns:
                    dep_match = re.search(pattern, request.analysis_detail, re.MULTILINE | re.DOTALL)
                    if dep_match:
                        dep_vars = [v.strip() for v in dep_match.group(1).split(',')]
                        logger.info(f"Variáveis dependentes extraídas: {dep_vars}")
                        break
                
                indep_patterns = [
                    r'[Vv]ariáveis\s+(?:a\s+[Ss]erem\s+[Uu]tilizadas\s+)?\n?\s*[Vv]ariáveis\s+independentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Vv]ariáveis\s+independentes\s*:?\s*"?([^"\n]+)"?',
                    r'[Ii]ndependentes?\s*:?\s*"?([^"\n]+)"?'
                ]
                
                for pattern in indep_patterns:
                    indep_match = re.search(pattern, request.analysis_detail, re.MULTILINE | re.DOTALL)
                    if indep_match:
                        indep_vars = [v.strip() for v in indep_match.group(1).split(',')]
                        logger.info(f"Variáveis independentes extraídas: {indep_vars}")
                        break
                
                # Se não conseguiu extrair, tente usar algumas colunas do DataFrame
                if not dep_vars and not indep_vars and df is not None:
                    cols = df.columns.tolist()
                    logger.info(f"Não foi possível extrair variáveis. Colunas disponíveis: {cols}")
                    dep_vars = cols[:1]  # Primeira coluna como dependente
                    indep_vars = cols[1:3] if len(cols) > 2 else cols[1:2] if len(cols) > 1 else []  # Próximas colunas como independentes
                    logger.info(f"Usando variáveis padrão: dep={dep_vars}, indep={indep_vars}")
                
                # Tentar extrair o nome da análise
                name_patterns = [
                    r'Analise:\s*([^\n]+)',
                    r'Análise\s+\d+\s*[-:]\s*([^\n]+)'
                ]
                
                analysis_name = f"Análise {request.analysis_number}"
                for pattern in name_patterns:
                    name_match = re.search(pattern, request.analysis_detail)
                    if name_match:
                        analysis_name = name_match.group(1).strip()
                        break
                
                # Criar análise on-the-fly
                analysis = {
                    "number": request.analysis_number,
                    "name": analysis_name,
                    "content": request.analysis_detail,
                    "dependent_vars": dep_vars,
                    "independent_vars": indep_vars,
                    "status": "pending"
                }
                
                # Adicionar ao cache
                analyses_cache[request.upload_id].append(analysis)
                logger.info(f"Análise #{request.analysis_number} criada dinamicamente")
            else:
                # Log detalhado para depuração caso nada funcione
                logger.error(f"Análise {request.analysis_number} não encontrada entre {len(analyses_cache[request.upload_id])} análises")
                
                # Listar números de análise disponíveis para depuração
                available_numbers = []
                for a in analyses_cache[request.upload_id]:
                    if isinstance(a, dict):
                        available_numbers.append(a.get("number"))
                    else:
                        available_numbers.append(getattr(a, "number", None))
                
                logger.error(f"Análises disponíveis: {available_numbers}")
                
                raise HTTPException(
                    status_code=404, 
                    detail=f"Análise número {request.analysis_number} não encontrada. Análises disponíveis: {available_numbers}"
                )
        
        # Garantir que a análise esteja em formato de dicionário para o executor
        if not isinstance(analysis, dict) and hasattr(analysis, 'dict'):
            analysis_dict = analysis.dict()
        else:
            # Se já for dicionário ou não tiver método dict()
            analysis_dict = analysis
        
        # IMPORTANTE: Certificar-se de que as variáveis explícitas do request tenham precedência
        # mas também que elas sejam válidas
        if hasattr(request, 'dependent_vars') and request.dependent_vars:
            logger.info(f"Usando variáveis dependentes do request: {request.dependent_vars}")
            analysis_dict['dependent_vars'] = request.dependent_vars
        
        if hasattr(request, 'independent_vars') and request.independent_vars:
            logger.info(f"Usando variáveis independentes do request: {request.independent_vars}")
            analysis_dict['independent_vars'] = request.independent_vars
            
        # Executar análise
        logger.info(f"Executando análise com variáveis: dep={analysis_dict.get('dependent_vars', [])}, indep={analysis_dict.get('independent_vars', [])}")
        result = execute_analysis_from_model(df, analysis_dict)
        
        # Coletar estatísticas de tokens após execução
        combined_tokens = agent_token_counter.get_summary()["total_tokens"]
        combined_cost = agent_token_counter.get_summary()["estimated_cost_usd"]
        
        # Registrar estatísticas no log
        logger.info("===== ESTATÍSTICAS DE TOKENS - EXECUÇÃO DE ANÁLISE =====")
        logger.info(f"Total de tokens: {combined_tokens}")
        logger.info(f"Custo estimado: ${combined_cost:.6f}")
        logger.info("==================================================")
        
        if "token_usage" not in result:
            result["token_usage"] = {
                "total_tokens": combined_tokens,
                "estimated_cost_usd": combined_cost
            }
        
        # Atualizar o cache
        for i, a in enumerate(analyses_cache[request.upload_id]):
            current_number = a.get("number", None) if isinstance(a, dict) else getattr(a, "number", None)
            if current_number == request.analysis_number:
                if isinstance(a, dict):
                    analyses_cache[request.upload_id][i]["status"] = "completed" if result.get("success", False) else "error"
                    analyses_cache[request.upload_id][i]["results"] = result
                else:
                    analyses_cache[request.upload_id][i].status = "completed" if result.get("success", False) else "error"
                    analyses_cache[request.upload_id][i].results = result
                break
        
        # Garantir que o resultado tenha todos os campos obrigatórios
        if not isinstance(result, dict):
            result = {}
        
        # Adicionar campos obrigatórios se estiverem faltando
        if "number" not in result:
            result["number"] = request.analysis_number
        if "name" not in result:
            result["name"] = analysis_dict.get("name", f"Análise {request.analysis_number}")
        if "success" not in result:
            result["success"] = False
        
        return ExecuteAnalysisResponse(
            success=True,
            message=f"Análise {request.analysis_number} executada com sucesso",
            result=result,
            token_usage={
                "total_tokens": combined_tokens,
                "estimated_cost_usd": combined_cost
            }
        )
    
    except HTTPException:
        # Re-lançar HTTPExceptions já formatadas
        raise
    except Exception as e:
        logger.error(f"Erro ao executar análise: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Criar um objeto de resultado de erro completo com todos os campos obrigatórios
        error_result = {
            "success": False,
            "number": request.analysis_number,
            "name": "Análise com erro",
            "plots": [],
            "tables": [],
            "text_output": f"Erro durante a execução: {str(e)}",
            "error": f"Erro ao executar análise: {str(e)}"
        }
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao executar análise: {str(e)}",
            headers={"X-Error": "analysis_execution_error"}
        ) from e

@router.post("/execute-all/{upload_id}")
async def execute_all_analyses(upload_id: str, background_tasks: BackgroundTasks):
    """
    Executa todas as análises recomendadas para um dataset.
    """
    try:
        # Verificar se o dataset existe
        try:
            df = get_dataset(upload_id)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset com ID {upload_id} não encontrado"
            )
        
        # Verificar se temos análises para este dataset
        if upload_id not in analyses_cache:
            raise HTTPException(
                status_code=404, 
                detail="Nenhuma análise encontrada para este dataset. Execute '/recommend' primeiro."
            )
        
        # Executar análise em background para não bloquear a API
        background_tasks.add_task(
            _execute_analyses_background,
            df,
            analyses_cache[upload_id],
            upload_id
        )
        
        return {
            "success": True,
            "message": f"Execução de {len(analyses_cache[upload_id])} análises iniciada em background",
            "status": "running"
        }
        
    except Exception as e:
        logger.error(f"Erro ao executar análises: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao executar análises: {str(e)}"
        )

@router.get("/status/{upload_id}")
async def get_analyses_status(upload_id: str):
    """
    Retorna o status atual das análises para um dataset.
    """
    if upload_id not in analyses_cache:
        raise HTTPException(
            status_code=404, 
            detail="Nenhuma análise encontrada para este dataset"
        )
    
    analyses = analyses_cache[upload_id]
    status_counts = {
        "total": len(analyses),
        "pending": sum(1 for a in analyses if a.status == AnalysisStatus.PENDING),
        "running": sum(1 for a in analyses if a.status == AnalysisStatus.RUNNING),
        "completed": sum(1 for a in analyses if a.status == AnalysisStatus.COMPLETED),
        "error": sum(1 for a in analyses if a.status == AnalysisStatus.ERROR)
    }
    
    return {
        "upload_id": upload_id,
        "status": status_counts,
        "analyses": [
            {
                "number": a.number,
                "name": a.name,
                "status": a.status
            }
            for a in analyses
        ]
    }

@router.get("/status/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """
    Returns the current status of a specific analysis by ID.
    Used by the frontend to check if an analysis has completed after being launched.
    """
    try:
        # First, check if the analysis exists in our cache
        for upload_id, analyses_list in analyses_cache.items():
            for analysis in analyses_list:
                # Check if this is the analysis we're looking for
                analysis_number = analysis.get("number", None) if isinstance(analysis, dict) else getattr(analysis, "number", None)
                if str(analysis_id) == str(analysis_number):
                    # Get the status
                    status = analysis.get("status", "pending") if isinstance(analysis, dict) else getattr(analysis, "status", "pending")
                    
                    # Get any error message
                    error = None
                    if isinstance(analysis, dict) and "results" in analysis and analysis["results"]:
                        error = analysis["results"].get("error", None)
                    elif hasattr(analysis, "results") and analysis.results:
                        error = getattr(analysis.results, "error", None)
                    
                    # Return status information
                    return {
                        "id": analysis_id,
                        "status": status,
                        "error": error,
                        "completed": status == "completed",
                        "timestamp": str(time.time())
                    }
        
        # If we get here, the analysis wasn't found
        logger.warning(f"Analysis ID {analysis_id} not found in status check")
        raise HTTPException(
            status_code=404,
            detail=f"Analysis with ID {analysis_id} not found"
        )
    except Exception as e:
        logger.error(f"Error checking analysis status: {str(e)}")
        return {
            "id": analysis_id,
            "status": "error",
            "error": str(e),
            "completed": False,
            "timestamp": str(time.time())
        }

# Função auxiliar para execução em background
async def _execute_analyses_background(df, analyses, upload_id):
    """Executa todas as análises em background e atualiza o cache."""
    for i, analysis in enumerate(analyses):
        try:
            # Atualizar status para running
            analyses_cache[upload_id][i].status = AnalysisStatus.RUNNING
            
            # Executar análise
            result = execute_analysis_from_model(df, analysis)
            
            # Atualizar cache com resultados
            analyses_cache[upload_id][i].status = AnalysisStatus.COMPLETED if result["success"] else AnalysisStatus.ERROR
            analyses_cache[upload_id][i].results = result
            
        except Exception as e:
            logger.error(f"Erro ao executar análise {analysis.number}: {str(e)}")
            analyses_cache[upload_id][i].status = AnalysisStatus.ERROR
            analyses_cache[upload_id][i].results = AnalysisResult(
                success=False,
                number=analysis.number,
                name=analysis.name,
                error=str(e)
            )
