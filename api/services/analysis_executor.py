"""
Módulo para executar análises estatísticas usando LangGraph para geração de código.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List, Optional
import logging
import io
import sys
import base64
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import traceback
import re
import json
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
from pydantic import BaseModel, Field
import os
import sys
# Add the project root to Python path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.token_counter import TokenCounter
from utils.llm_utils import initialize_llm  # Importar a função centralizada

# Configurar logging
logger = logging.getLogger("lean-six-sigma-api.analysis-executor")

# Atualizar a criação do contador de tokens
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

# Criar um contador de tokens global para o módulo
token_counter = TokenCounter(model=DEFAULT_MODEL)

# Configurar matplotlib para não mostrar janelas interativas - ADICIONAR ISTO
plt.ioff()  # Desativa o modo interativo
plt.switch_backend('Agg')  # Usa o backend que não exibe janelas

# Atualizar a classe AnalysisState para incluir o campo should_retry
class AnalysisState(BaseModel):
    """Estado da execução de uma análise"""
    analysis_details: Dict[str, Any] = Field(..., description="Detalhes da análise a ser executada")
    df: Any = Field(..., description="DataFrame com os dados")
    generated_code: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    should_retry: bool = False  # Novo campo para controle de fluxo

def analisar_requisito(state: AnalysisState) -> AnalysisState:
    """
    Analisa os detalhes da requisição de análise e melhora a compreensão.
    """
    try:
        # Criar um resumo estruturado da análise
        llm = initialize_llm()
        
        # Extrair informações relevantes
        analysis_details = state.analysis_details
        analysis_detail_text = analysis_details.get("analysis_detail", "")
        
        # Verificar tipos de dados no DataFrame
        df = state.df
        column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # Extrair variáveis dependentes e independentes
        dependent_vars = []
        independent_vars = []
        
        # Extrair das informações de análise
        if isinstance(analysis_detail_text, str):
            dep_match = re.search(r'[Vv]ariáveis\s+dependentes[:\s]+"?([^"\n]+)"?', analysis_detail_text)
            if dep_match:
                dependent_vars = [v.strip() for v in dep_match.group(1).split(',')]
                
            indep_match = re.search(r'[Vv]ariáveis\s+independentes[:\s]+"?([^"\n]+)"?', analysis_detail_text)
            if indep_match:
                independent_vars = [v.strip() for v in indep_match.group(1).split(',')]
        
        # Se não encontrou no texto, tente do payload
        if not dependent_vars and "dependent_vars" in analysis_details:
            dependent_vars = analysis_details["dependent_vars"]
            
        if not independent_vars and "independent_vars" in analysis_details:
            independent_vars = analysis_details["independent_vars"]
        
        # Validar variáveis contra o DataFrame
        valid_dependent_vars = [var for var in dependent_vars if var in df.columns]
        valid_independent_vars = [var for var in independent_vars if var in df.columns]
        
        # Atualizar o estado com os detalhes processados
        analysis_details["processed_dependent_vars"] = valid_dependent_vars
        analysis_details["processed_independent_vars"] = valid_independent_vars
        analysis_details["column_types"] = column_types
        analysis_details["df_shape"] = df.shape
        
        logger.info(f"Análise processada: {len(valid_dependent_vars)} vars dependentes, {len(valid_independent_vars)} vars independentes")
        return AnalysisState(
            analysis_details=analysis_details,
            df=state.df,
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts
        )
    except Exception as e:
        logger.error(f"Erro ao analisar requisito: {e}")
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            error_message=f"Erro ao analisar requisito: {str(e)}",
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts
        )

def gerar_codigo(state: AnalysisState) -> AnalysisState:
    """
    Gera código Python para executar a análise solicitada.
    """
    try:
        llm = initialize_llm()
        analysis_details = state.analysis_details
        analysis_detail_text = analysis_details.get("analysis_detail", "")
        analysis_name = analysis_details.get("analysis_number", "desconhecida")
        
        # Obter variáveis processadas
        dependent_vars = analysis_details.get("processed_dependent_vars", [])
        independent_vars = analysis_details.get("processed_independent_vars", [])
        column_types = analysis_details.get("column_types", {})
        
        # Informações sobre o DataFrame
        df = state.df
        df_shape = df.shape
        df_sample = df.head(3).to_dict() if len(df) > 0 else {}
        
        # Preparar o prompt para geração de código
        prompt_template = """
        # TAREFA: GERAÇÃO DE CÓDIGO PYTHON PARA ANÁLISE ESTATÍSTICA
        
        Você é um especialista em análise de dados estatística com foco em Lean Six Sigma.
        Sua tarefa é gerar código Python para realizar a seguinte análise:
        
        ## Detalhes da Análise
        {analysis_detail}
        
        ## Variáveis Disponíveis
        - Dependentes: {dependent_vars}
        - Independentes: {independent_vars}
        
        ## Estrutura do DataFrame (df)
        - Linhas: {rows}
        - Colunas: {cols}
        - Tipos das colunas: {column_types}
        
        ## Requisitos do Código
        1. O código deve usar pandas, numpy, matplotlib e seaborn
        2. Armazenar tabelas resultantes na lista 'result_tables'
        3. Usar print() para exibir conclusões claras
        4. Garantir que os gráficos sejam salvos corretamente
        5. Adicionar tratamento de erros básico
        
        {error_context}
        
        ## Resultado Esperado
        O código deve realizar a análise solicitada e gerar visualizações e tabelas apropriadas.
        
        ## Formato do Código
        Gere apenas código Python pronto para execução sem comentários explicativos.
        """
        
        # Se é uma tentativa após erro, adicionar contexto do erro
        error_context = ""
        if state.error_message and state.attempt_count > 0:
            error_context = f"""
            ## Erro na tentativa anterior (tente corrigir):
            ```
            {state.error_message}
            ```
            
            Evite esse erro gerando um código mais robusto. Adicione mais verificações e tratamento de erros.
            """
        
        # Formatar o prompt
        prompt = ChatPromptTemplate.from_template(prompt_template).format(
            analysis_detail=analysis_detail_text,
            dependent_vars=", ".join(dependent_vars) if dependent_vars else "Nenhuma",
            independent_vars=", ".join(independent_vars) if independent_vars else "Nenhuma",
            rows=df_shape[0],
            cols=df_shape[1],
            column_types=column_types,
            error_context=error_context
        )
        
        # Contar tokens do prompt
        prompt_str = prompt.format() if hasattr(prompt, "format") else str(prompt)
        token_counter.count_prompt(prompt_str, f"gerar_codigo_{state.attempt_count}")
        
        # Gerar o código
        response = llm.invoke(prompt)
        code = response.content
        
        # Contar tokens da resposta
        token_counter.count_completion(code, f"gerar_codigo_{state.attempt_count}")
        
        # Registrar estatísticas
        if state.attempt_count == 0:  # Apenas na primeira tentativa
            logger.info(f"Estatísticas de tokens para geração de código inicial:")
            token_counter.log_summary()
        
        # Verificar se há imports necessários
        required_imports = [
            "import pandas as pd",
            "import numpy as np",
            "import matplotlib.pyplot as plt",
            "import seaborn as sns"
        ]
        
        for imp in required_imports:
            if imp not in code:
                code = imp + "\n" + code
        
        # Garantir que o tratamento de figuras esteja correto
        figure_setup = """
# Configurar figura
plt.figure(figsize=(10, 6))
"""
        
        if "plt.figure" not in code:
            code = code.replace("import seaborn as sns", "import seaborn as sns\n" + figure_setup)
        
        # Adicionar código para lidar com valores ausentes
        if "result_tables" not in code:
            code += "\n# Armazenar resultados\nresult_tables = []"
        
        logger.info(f"Código gerado para análise {analysis_name}, {len(code)} caracteres")
        
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            generated_code=code,
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts
        )
    except Exception as e:
        logger.error(f"Erro ao gerar código: {e}")
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            error_message=f"Erro ao gerar código: {str(e)}",
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts
        )

def executar_codigo(state: AnalysisState) -> AnalysisState:
    """
    Executa o código Python gerado e captura os resultados.
    """
    if not state.generated_code:
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            error_message="Nenhum código foi gerado para execução",
            attempt_count=state.attempt_count + 1,
            max_attempts=state.max_attempts
        )
    
    try:
        # Preparar ambiente de execução
        df = state.df  # Disponibilizar o DataFrame para o código
        code = state.generated_code
        result_tables = []  # Lista para armazenar tabelas resultantes
        plots = []  # Lista para armazenar gráficos
        
        # Capturar saída texto
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Capturar figuras do matplotlib
        original_figure = plt.figure
        figures = []
        
        def custom_figure(*args, **kwargs):
            fig = original_figure(*args, **kwargs)
            figures.append(fig)
            return fig
        
        plt.figure = custom_figure
        plt.close('all')  # Fechar figuras existentes
        
        # Modificar o código para substituir qualquer plt.show() por pass
        code = state.generated_code
        code = code.replace('plt.show()', 'pass')
        
        # Executar o código
        exec_globals = {
            'pd': pd,
            'np': np,
            'plt': plt,
            'sns': sns,
            'df': df,
            'result_tables': result_tables
        }
        
        exec(code, exec_globals)
        
        # Recuperar saída de texto
        text_output = captured_output.getvalue()
        
        # Processar figuras geradas
        processed_plots = []
        for i, fig in enumerate(figures):
            try:
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                plot_data = base64.b64encode(buf.read()).decode('utf-8')
                
                processed_plots.append({
                    "id": f"plot_{i+1}",
                    "data": plot_data
                })
                buf.close()
            except Exception as e:
                logger.error(f"Erro ao salvar figura {i}: {e}")
        
        # Processar tabelas geradas
        processed_tables = []
        for i, table in enumerate(result_tables):
            try:
                if isinstance(table, pd.DataFrame):
                    processed_tables.append({
                        "id": f"table_{i+1}",
                        "html": table.head(20).to_html(classes="table table-striped"),
                        "description": f"Tabela {i+1}"
                    })
            except Exception as e:
                logger.error(f"Erro ao processar tabela {i}: {e}")
        
        # Verificar se tabelas foram produzidas pelo código diretamente
        for var_name, var_value in exec_globals.items():
            if isinstance(var_value, pd.DataFrame) and var_name not in ['df', 'result_tables']:
                try:
                    processed_tables.append({
                        "id": f"table_{var_name}",
                        "html": var_value.head(20).to_html(classes="table table-striped"),
                        "description": f"Tabela: {var_name}"
                    })
                except Exception as e:
                    logger.error(f"Erro ao processar DataFrame {var_name}: {e}")
        
        # Limpar recursos
        sys.stdout = old_stdout
        plt.figure = original_figure
        plt.close('all')
        
        # Preparar resultados
        execution_result = {
            "success": True,
            "number": state.analysis_details.get("analysis_number", 1),
            "name": state.analysis_details.get("analysis_name", "Análise Estatística"),
            "plots": processed_plots,
            "tables": processed_tables,
            "text_output": text_output,
            "error": None
        }
        
        logger.info(f"Execução bem-sucedida: {len(processed_plots)} gráficos, {len(processed_tables)} tabelas")
        
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            generated_code=state.generated_code,
            execution_result=execution_result,
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Erro ao executar código: {e}\n{error_trace}")
        
        # Limpar recursos em caso de erro
        sys.stdout = old_stdout if 'old_stdout' in locals() else sys.stdout
        if 'original_figure' in locals():
            plt.figure = original_figure
        plt.close('all')
        
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            generated_code=state.generated_code,
            error_message=f"Erro ao executar código: {str(e)}\n{error_trace}",
            attempt_count=state.attempt_count + 1,
            max_attempts=state.max_attempts
        )

def processar_erros(state: AnalysisState) -> AnalysisState:
    """
    Processa erros e decide se tenta novamente ou termina.
    Modificado para retornar o estado atualizado com should_retry em vez de dict.
    """
    if not state.error_message:
        return state
    
    # Verificar se ainda pode tentar novamente
    should_retry = state.attempt_count < state.max_attempts
    if should_retry:
        logger.info(f"Tentativa {state.attempt_count + 1}/{state.max_attempts}: tentando novamente após erro")
        
        # Update the state directly instead of returning a dict
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            generated_code=state.generated_code,
            error_message=state.error_message,
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts,
            should_retry=True
        )
    else:
        logger.warning(f"Número máximo de tentativas atingido ({state.max_attempts}). Finalizando com erro.")
        return AnalysisState(
            analysis_details=state.analysis_details,
            df=state.df,
            generated_code=state.generated_code,
            error_message=state.error_message,
            attempt_count=state.attempt_count,
            max_attempts=state.max_attempts,
            should_retry=False
        )

def formatar_resultado_final(state: AnalysisState) -> Dict[str, Any]:
    """
    Formata o resultado final da análise.
    """
    if state.execution_result:
        # Execução bem-sucedida, retornar os resultados
        return state.execution_result
    else:
        # Falha na execução, gerar um resultado de erro
        analysis_number = state.analysis_details.get("analysis_number", 1)
        analysis_name = state.analysis_details.get("analysis_name", "Análise")
        
        return {
            "success": False,
            "number": analysis_number,
            "name": analysis_name,
            "plots": [],
            "tables": [],
            "text_output": f"Falha após {state.attempt_count} tentativas.",
            "error": state.error_message
        }

def build_analysis_graph():
    """
    Constrói o grafo de execução de análise usando LangGraph.
    """
    try:
        # Criar o grafo de estado
        workflow = StateGraph(AnalysisState)
        
        # Adicionar nós
        workflow.add_node("analisar_requisito", analisar_requisito)
        workflow.add_node("gerar_codigo", gerar_codigo)
        workflow.add_node("executar_codigo", executar_codigo)
        workflow.add_node("processar_erros", processar_erros)
        workflow.add_node("formatar_resultado", formatar_resultado_final)
        
        # Definir o nó inicial explicitamente
        workflow.set_entry_point("analisar_requisito")
        
        # Definir fluxo
        workflow.add_edge("analisar_requisito", "gerar_codigo")
        workflow.add_edge("gerar_codigo", "executar_codigo")
        
        # Modificar as condicionais para usar strings simples em vez de lambdas
        workflow.add_conditional_edges(
            "executar_codigo",
            lambda x: "processar_erros" if x.error_message else "formatar_resultado"
        )
        
        # Corrigir a definição da edge condicional para evitar problemas com '__start__'
        workflow.add_conditional_edges(
            "processar_erros",
            lambda x: "gerar_codigo" if x.get("should_retry", False) else "formatar_resultado"
        )
        
        workflow.add_edge("formatar_resultado", END)
        
        # Compilar o grafo
        return workflow.compile()
    except Exception as e:
        logger.error(f"Erro ao construir grafo: {str(e)}")
        raise

def execute_analysis_graph(analysis_details: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Executa o grafo de análise com os detalhes fornecidos.
    """
    try:
        # Criar estado inicial
        initial_state = AnalysisState(
            analysis_details=analysis_details,
            df=df,
            attempt_count=0,
            max_attempts=3
        )
        
        # Obter grafo compilado
        graph = build_analysis_graph()
        
        # Executar o grafo com tratamento de erro aprimorado
        try:
            result = graph.invoke(initial_state)
            logger.info("Execução do grafo concluída com sucesso")
            return result
        except Exception as graph_error:
            logger.error(f"Erro na execução do grafo: {str(graph_error)}")
            # Ainda tentar gerar um resultado de fallback em caso de erro do grafo
            return formatar_resultado_final(initial_state)
    except Exception as e:
        logger.error(f"Erro ao executar grafo de análise: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Retornar um resultado de fallback para não quebrar o fluxo
        return {
            "success": False,
            "number": analysis_details.get("analysis_number", 1),
            "name": analysis_details.get("analysis_name", "Análise"),
            "plots": [],
            "tables": [],
            "text_output": f"Erro ao executar análise: {str(e)}",
            "error": f"Erro ao executar análise usando LangGraph: {str(e)}"
        }

# Função de API para uso pelo router
def execute_analysis_with_graph(df: pd.DataFrame, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Função principal para executar uma análise usando o grafo LangGraph.
    """
    try:
        # Preparar detalhes da análise
        analysis_details = {
            "analysis_number": analysis.get("number", 1),
            "analysis_name": analysis.get("name", "Análise"),
            "analysis_detail": analysis.get("content", ""),
            "dependent_vars": analysis.get("dependent_vars", []),
            "independent_vars": analysis.get("independent_vars", [])
        }
        
        # Se houver detalhes adicionais fornecidos, incluir
        if "analysis_detail" in analysis and analysis["analysis_detail"]:
            analysis_details["analysis_detail"] = analysis["analysis_detail"]
        
        logger.info(f"Iniciando execução da análise {analysis_details['analysis_number']}: {analysis_details['analysis_name']}")
        
        # Executar o grafo
        result = execute_analysis_graph(analysis_details, df)
        
        # Registrar estatísticas de tokens no final da execução
        logger.info("===== Uso de Tokens da Análise =====")
        token_counter.log_summary()
        
        # Adicionar informações de tokens ao resultado
        token_summary = token_counter.get_summary()
        result["token_usage"] = {
            "total_tokens": token_summary["total_tokens"],
            "prompt_tokens": token_summary["prompt_tokens"],
            "completion_tokens": token_summary["completion_tokens"],
            "estimated_cost_usd": token_summary["estimated_cost_usd"]
        }
        
        return result
    except Exception as e:
        logger.error(f"Erro na execução da análise: {e}")
        return {
            "success": False,
            "number": analysis.get("number", 0),
            "name": analysis.get("name", "Análise desconhecida"),
            "plots": [],
            "tables": [],
            "text_output": "",
            "error": f"Erro ao executar análise: {str(e)}"
        }
