import os
import sys
from typing import Dict, List, Any, TypedDict, Optional, Callable, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import json

# Carregar variáveis de ambiente
load_dotenv()

# Definir a estrutura do estado para o agente comparador
class ComparatorState(TypedDict):
    analysis1: Dict[str, Any]  # Dados da primeira análise
    analysis2: Dict[str, Any]  # Dados da segunda análise
    same_dataset: bool         # Se as análises são do mesmo dataset
    comparisons: Dict[str, Any]  # Resultados de comparações intermediárias
    insights: Optional[str]    # Insights finais gerados
    improvement_suggestions: Optional[str]  # Sugestões de melhoria

# Prompts para o agente comparador
PROMPTS = {
    "analyze_variables": """
    # Análise de Variáveis para Comparação
    
    Você está analisando duas análises estatísticas para compará-las:
    
    ## Análise 1: {analysis1_name}
    - Variáveis Dependentes: {dep_vars1}
    - Variáveis Independentes: {indep_vars1}
    - Status: {status1}
    
    ## Análise 2: {analysis2_name}
    - Variáveis Dependentes: {dep_vars2}
    - Variáveis Independentes: {indep_vars2}
    - Status: {status2}
    
    ## Sobre o Dataset
    As análises {dataset_relation}.
    
    # Sua Tarefa
    Analise as variáveis de ambas as análises e identifique:
    1. Diferenças chave na abordagem de análise
    2. Potenciais impactos dessas diferenças nos resultados
    3. Como as escolhas de variáveis afetam as conclusões
    
    Responda em português do Brasil, com linguagem técnica mas acessível.
    """,
    
    "analyze_results": """
    # Análise Comparativa de Resultados Estatísticos
    
    Você está comparando os resultados de duas análises estatísticas:
    
    ## Análise 1: {analysis1_name}
    ```
    {results1}
    ```
    
    ## Análise 2: {analysis2_name}
    ```
    {results2}
    ```
    
    ## Análise Prévia de Variáveis
    {variable_analysis}
    
    # Sua Tarefa
    Compare os resultados estatísticos e identifique:
    1. Diferenças significativas nos resultados
    2. Possíveis razões para essas diferenças
    3. Qual análise produziu resultados mais robustos ou relevantes e por quê
    
    Responda em português do Brasil, com foco em insights estatisticamente válidos.
    """,
    
    "generate_insights": """
    # Geração de Insights e Recomendações para Melhoria de Análises
    
    Com base nas análises comparativas realizadas:
    
    ## Análise de Variáveis
    {variable_analysis}
    
    ## Análise de Resultados
    {results_analysis}
    
    # Sua Tarefa
    Gere insights aprofundados e recomendações práticas:
    
    ## 1. Insights Chave
    Identifique 3-5 insights principais derivados da comparação das análises.
    
    ## 2. Recomendações de Melhoria
    Sugira melhorias específicas para:
    - Escolha de variáveis
    - Metodologia estatística
    - Interpretação dos resultados
    - Possíveis análises complementares
    
    ## 3. Próximos Passos Recomendados
    Recomende ações concretas para o usuário avançar em sua análise.
    
    Responda em português do Brasil, com linguagem técnica mas acessível. Priorize recomendações práticas e acionáveis.
    """
}

def initialize_llm(model_name="gpt-4o-mini"):
    """Inicializa o modelo de linguagem."""
    return ChatOpenAI(
        model=model_name,
        temperature=0.1,
    )

def analyze_variables(state: ComparatorState) -> ComparatorState:
    """Analisa as diferenças nas variáveis entre as duas análises."""
    llm = initialize_llm()
    
    dataset_relation = "são do mesmo dataset" if state["same_dataset"] else "pertencem a datasets diferentes"
    
    analysis1 = state["analysis1"]
    analysis2 = state["analysis2"]
    
    prompt = ChatPromptTemplate.from_template(PROMPTS["analyze_variables"])
    
    chain = prompt | llm | StrOutputParser()
    
    variable_analysis = chain.invoke({
        "analysis1_name": analysis1["name"],
        "dep_vars1": ", ".join(analysis1["dependent_vars"]),
        "indep_vars1": ", ".join(analysis1["independent_vars"]),
        "status1": analysis1["status"],
        "analysis2_name": analysis2["name"],
        "dep_vars2": ", ".join(analysis2["dependent_vars"]),
        "indep_vars2": ", ".join(analysis2["independent_vars"]),
        "status2": analysis2["status"],
        "dataset_relation": dataset_relation
    })
    
    return {
        **state,
        "comparisons": {
            **state.get("comparisons", {}),
            "variable_analysis": variable_analysis
        }
    }

def analyze_results(state: ComparatorState) -> ComparatorState:
    """Analisa as diferenças nos resultados entre as duas análises."""
    llm = initialize_llm()
    
    analysis1 = state["analysis1"]
    analysis2 = state["analysis2"]
    
    # Obter análise prévia de variáveis
    variable_analysis = state.get("comparisons", {}).get("variable_analysis", "Não disponível")
    
    # Verificar se ambas as análises têm resultados para comparar
    if not (analysis1.get("results") and analysis2.get("results")):
        return {
            **state,
            "comparisons": {
                **state.get("comparisons", {}),
                "results_analysis": "Não foi possível comparar resultados pois uma ou ambas as análises não têm resultados disponíveis."
            }
        }
    
    prompt = ChatPromptTemplate.from_template(PROMPTS["analyze_results"])
    
    chain = prompt | llm | StrOutputParser()
    
    # Preparar strings de resultados com informações relevantes
    results1 = json.dumps(analysis1.get("results", {}), indent=2, ensure_ascii=False)
    results2 = json.dumps(analysis2.get("results", {}), indent=2, ensure_ascii=False)
    
    results_analysis = chain.invoke({
        "analysis1_name": analysis1["name"],
        "results1": results1,
        "analysis2_name": analysis2["name"],
        "results2": results2,
        "variable_analysis": variable_analysis
    })
    
    return {
        **state,
        "comparisons": {
            **state.get("comparisons", {}),
            "results_analysis": results_analysis
        }
    }

def generate_insights(state: ComparatorState) -> ComparatorState:
    """Gera insights e recomendações de melhoria com base nas análises comparativas."""
    llm = initialize_llm(model_name="gpt-4o")  # Usando um modelo mais avançado para insights finais
    
    comparisons = state.get("comparisons", {})
    variable_analysis = comparisons.get("variable_analysis", "Não disponível")
    results_analysis = comparisons.get("results_analysis", "Não disponível")
    
    prompt = ChatPromptTemplate.from_template(PROMPTS["generate_insights"])
    
    chain = prompt | llm | StrOutputParser()
    
    insights_text = chain.invoke({
        "variable_analysis": variable_analysis,
        "results_analysis": results_analysis
    })
    
    # Extrair seções específicas do texto gerado
    sections = insights_text.split("##")
    
    insights = None
    improvement_suggestions = None
    
    for section in sections:
        if "Insights Chave" in section:
            insights = "## " + section.strip()
        elif "Recomendações de Melhoria" in section or "Próximos Passos" in section:
            if improvement_suggestions:
                improvement_suggestions += "\n\n## " + section.strip()
            else:
                improvement_suggestions = "## " + section.strip()
    
    return {
        **state,
        "insights": insights,
        "improvement_suggestions": improvement_suggestions
    }

def create_comparator_agent() -> Callable:
    """Cria um agente de comparação usando LangGraph."""
    workflow = StateGraph(ComparatorState)
    
    # Adicionar nós ao grafo
    workflow.add_node("analyze_variables", analyze_variables)
    workflow.add_node("analyze_results", analyze_results)
    workflow.add_node("generate_insights", generate_insights)
    
    # Definir ponto de entrada
    workflow.set_entry_point("analyze_variables")
    
    # Definir arestas entre os nós
    workflow.add_edge("analyze_variables", "analyze_results")
    workflow.add_edge("analyze_results", "generate_insights")
    workflow.add_edge("generate_insights", END)
    
    # Compilar o grafo
    return workflow.compile()

def compare_analyses(analysis1: Dict[str, Any], analysis2: Dict[str, Any], same_dataset: bool) -> Dict[str, str]:
    """
    Função principal para comparar duas análises e gerar insights.
    
    Args:
        analysis1: Dicionário com dados da primeira análise
        analysis2: Dicionário com dados da segunda análise
        same_dataset: Boolean indicando se as análises são do mesmo dataset
        
    Returns:
        Dicionário com insights e sugestões de melhoria
    """
    # Inicializar estado
    initial_state = {
        "analysis1": analysis1,
        "analysis2": analysis2,
        "same_dataset": same_dataset,
        "comparisons": {},
        "insights": None,
        "improvement_suggestions": None
    }
    
    # Criar e executar o agente
    try:
        comparator_agent = create_comparator_agent()
        final_state = comparator_agent.invoke(initial_state)
        
        return {
            "insights": final_state.get("insights", "Não foi possível gerar insights."),
            "improvement_suggestions": final_state.get("improvement_suggestions", "Não foi possível gerar sugestões de melhoria.")
        }
    except Exception as e:
        print(f"Erro ao executar o agente comparador: {e}")
        return {
            "insights": f"Erro ao gerar insights: {str(e)}",
            "improvement_suggestions": "Não foi possível gerar sugestões devido a um erro no processamento."
        }
