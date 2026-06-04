import os
import sys
# Add the project root to Python path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from typing import Dict, Any, List, TypedDict, Annotated, Optional, Callable, Tuple, Set
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import yaml
import json
import pandas as pd
import re
from utils.token_counter import TokenCounter
from utils.llm_utils import initialize_llm

# Load environment variables
load_dotenv()

# Load prompts from YAML file
def load_prompts():
    try:
        yaml_path = os.path.join(os.path.dirname(__file__), "../prompts.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao carregar prompts: {str(e)}")
        return {}

# Global dictionary of prompts for use throughout the module
PROMPTS = load_prompts()

# Define the state schema for the ReAct agent
class ReActAgentState(TypedDict):
    dataset_info: str  # JSON string with dataset information
    dependent_variables: List[str]  # List of dependent variable names
    independent_variables: List[str]  # List of independent variable names
    objective: str  # The objective for the analysis
    iteration: int  # Current iteration count for refinement
    enriched_data: Optional[str]  # Enriched data information
    analysis_suggestions: Optional[str]  # Suggested analyses in priority order
    feasibility_check: Optional[str]  # Feasibility assessment
    output: Optional[str]  # Final output

# Atualizar a criação do contador de tokens para React Agent
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
react_token_counter = TokenCounter(model=DEFAULT_MODEL)

def enrich_inputs(state: ReActAgentState, custom_print=print) -> ReActAgentState:
    """Step 1: Enrich and detail the input data."""
    custom_print("\n" + "="*80)
    custom_print("ETAPA 1: ENRIQUECIMENTO DOS DADOS")
    custom_print("="*80)
    custom_print("Analisando e enriquecendo dados para fornecer contexto adicional...")
    sys.stdout.flush()  # Ensure print is immediately visible
    
    llm = initialize_llm()
    
    # Use prompt from YAML file
    prompt = ChatPromptTemplate.from_template(PROMPTS.get("enrich_inputs", "Prompt não encontrado"))
    
    # Contar tokens do prompt
    prompt_str = PROMPTS.get("enrich_inputs", "Prompt não encontrado").format(
        dataset_info=state["dataset_info"],
        dependent_variables=", ".join(state["dependent_variables"]),
        independent_variables=", ".join(state["independent_variables"]),
        objective=state["objective"]
    )
    react_token_counter.count_prompt(prompt_str, "enrich_inputs")
    
    chain = prompt | llm | StrOutputParser()
    
    enriched_data = chain.invoke({
        "dataset_info": state["dataset_info"],
        "dependent_variables": ", ".join(state["dependent_variables"]),
        "independent_variables": ", ".join(state["independent_variables"]),
        "objective": state["objective"]
    })
    
    # Contar tokens da resposta
    react_token_counter.count_completion(enriched_data, "enrich_inputs")
    
    custom_print("✓ Enriquecimento de dados concluído!")
    custom_print(f"  - Dados originais enriquecidos com {len(enriched_data.split())} palavras de contexto adicional")
    custom_print(f"  - Tokens utilizados: {react_token_counter.get_summary()['total_tokens']} tokens")
    sys.stdout.flush()
    
    return {
        **state,
        "enriched_data": enriched_data,
        "iteration": 1  # Initialize iteration count
    }

# Update the suggest_analyses function to focus on the Analyze phase
def suggest_analyses(state: ReActAgentState, custom_print=print) -> ReActAgentState:
    """Step 2: Recommend analyses in priority order with detailed column usage."""
    custom_print("\n" + "="*80)
    custom_print("ETAPA 2: SUGESTÃO DE ANÁLISES FOCADAS NA FASE 'ANALYZE'")
    custom_print("="*80)
    custom_print("Determinando as melhores técnicas de análise estatística para identificação de causas raiz...")
    sys.stdout.flush()
    
    llm = initialize_llm()
    
    # Use prompt from YAML file
    prompt = ChatPromptTemplate.from_template(PROMPTS.get("suggest_analyses", "Prompt não encontrado"))
    
    # Contar tokens do prompt
    prompt_str = PROMPTS.get("suggest_analyses", "Prompt não encontrado").format(
        dataset_info=state["dataset_info"],
        enriched_data=state["enriched_data"],
        dependent_variables=", ".join(state["dependent_variables"]),
        independent_variables=", ".join(state["independent_variables"]),
        objective=state["objective"]
    )
    react_token_counter.count_prompt(prompt_str, "suggest_analyses")
    
    chain = prompt | llm | StrOutputParser()
    
    analysis_suggestions = chain.invoke({
        "dataset_info": state["dataset_info"],
        "enriched_data": state["enriched_data"],
        "dependent_variables": ", ".join(state["dependent_variables"]),
        "independent_variables": ", ".join(state["independent_variables"]),
        "objective": state["objective"]
    })
    
    # Contar tokens da resposta
    react_token_counter.count_completion(analysis_suggestions, "suggest_analyses")
    
    # Count how many analyses were suggested (approximation by looking for numbered items)
    analysis_count = 0
    for line in analysis_suggestions.split('\n'):
        if line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.')):
            analysis_count += 1
    
    custom_print(f"✓ Sugestão de análises concluída!")
    custom_print(f"  - {analysis_count} análises sugeridas em ordem de prioridade")
    custom_print(f"  - Tokens utilizados até agora: {react_token_counter.get_summary()['total_tokens']} tokens")
    sys.stdout.flush()
    
    return {
        **state,
        "analysis_suggestions": analysis_suggestions
    }

# Update the verify_feasibility function to be clearer about checking column availability
def verify_feasibility(state: ReActAgentState, custom_print=print) -> Dict:
    """Step 3: Verify if suggested analyses are feasible."""
    custom_print("\n" + "="*80)
    custom_print(f"ETAPA 3: VERIFICAÇÃO DE VIABILIDADE (Iteração {state['iteration']} de 3)")
    custom_print("="*80)
    custom_print("Avaliando se as análises sugeridas são viáveis com os dados disponíveis...")
    sys.stdout.flush()
    
    llm = initialize_llm()
    
    # Use prompt from YAML file
    prompt = ChatPromptTemplate.from_template(PROMPTS.get("verify_feasibility", "Prompt não encontrado"))
    
    # Contar tokens do prompt
    prompt_str = PROMPTS.get("verify_feasibility", "Prompt não encontrado").format(
        dataset_info=state["dataset_info"],
        analysis_suggestions=state["analysis_suggestions"],
        dependent_variables=", ".join(state["dependent_variables"]),
        independent_variables=", ".join(state["independent_variables"])
    )
    react_token_counter.count_prompt(prompt_str, "verify_feasibility")
    
    chain = prompt | llm | StrOutputParser()
    
    feasibility_check = chain.invoke({
        "dataset_info": state["dataset_info"],
        "analysis_suggestions": state["analysis_suggestions"],
        "dependent_variables": ", ".join(state["dependent_variables"]),
        "independent_variables": ", ".join(state["independent_variables"])
    })
    
    # Contar tokens da resposta
    react_token_counter.count_completion(feasibility_check, "verify_feasibility")
    
    # Check feasibility result
    if "VIÁVEL" in feasibility_check and "NÃO" not in feasibility_check[:50]:
        custom_print("✓ Verificação de viabilidade concluída: TODAS AS ANÁLISES SÃO VIÁVEIS!")
        custom_print("  - Preparando output final com as recomendações validadas")
        
        custom_print(f"  - Tokens utilizados até agora: {react_token_counter.get_summary()['total_tokens']} tokens")
        
        return {
            **state,
            "feasibility_check": feasibility_check,
            "output": prepare_final_output(state, feasibility_check)
        }
    elif state["iteration"] >= 3:
        custom_print("⚠ Limite máximo de iterações atingido (3).")
        custom_print("  - Gerando melhor output possível com as limitações atuais")
        
        custom_print(f"  - Tokens utilizados até agora: {react_token_counter.get_summary()['total_tokens']} tokens")
        
        return {
            **state,
            "feasibility_check": feasibility_check,
            "output": prepare_final_output(state, feasibility_check, is_best_effort=True)
        }
    else:
        custom_print("⚠ Algumas análises não são viáveis. Refinamento necessário.")
        custom_print(f"  - Iniciando iteração de refinamento {state['iteration'] + 1}")
        sys.stdout.flush()
        
        custom_print(f"  - Tokens utilizados até agora: {react_token_counter.get_summary()['total_tokens']} tokens")
        
        return {
            **state,
            "feasibility_check": feasibility_check
        }

# Fix the should_refine function to handle state correctly
def should_refine(state: ReActAgentState) -> str:
    """Determine if we need to refine recommendations or end."""
    # Check if there is an output already or we've reached max iterations
    if "output" in state and state["output"] is not None:
        return "end"
    elif state["iteration"] >= 3:
        return "end"
    else:
        return "refine"

# Update the refine_recommendations function to be clearer about removing non-feasible analyses
def refine_recommendations(state: ReActAgentState, custom_print=print) -> ReActAgentState:
    """Refine the analysis recommendations based on feasibility feedback."""
    custom_print("\n" + "="*80)
    custom_print(f"ETAPA 4: REFINAMENTO DE RECOMENDAÇÕES (Iteração {state['iteration']} de 3)")
    custom_print("="*80)
    custom_print("Removendo análises não viáveis e refinando recomendações...")
    sys.stdout.flush()
    
    llm = initialize_llm()
    
    # Use prompt from YAML file
    prompt = ChatPromptTemplate.from_template(PROMPTS.get("refine_recommendations", "Prompt não encontrado"))
    
    # Contar tokens do prompt
    prompt_str = PROMPTS.get("refine_recommendations", "Prompt não encontrado").format(
        dataset_info=state["dataset_info"],
        analysis_suggestions=state["analysis_suggestions"],
        feasibility_check=state["feasibility_check"],
        dependent_variables=", ".join(state["dependent_variables"]),
        independent_variables=", ".join(state["independent_variables"]),
        iteration=state["iteration"]
    )
    react_token_counter.count_prompt(prompt_str, "refine_recommendations")
    
    chain = prompt | llm | StrOutputParser()
    
    revised_suggestions = chain.invoke({
        "dataset_info": state["dataset_info"],
        "analysis_suggestions": state["analysis_suggestions"],
        "feasibility_check": state["feasibility_check"],
        "dependent_variables": ", ".join(state["dependent_variables"]),
        "independent_variables": ", ".join(state["independent_variables"]),
        "iteration": state["iteration"]
    })
    
    # Contar tokens da resposta
    react_token_counter.count_completion(revised_suggestions, "refine_recommendations")
    
    # Track what's changed between iterations
    added, removed, modified = track_analysis_changes(state["analysis_suggestions"], revised_suggestions)
    
    custom_print(f"✓ Refinamento #{state['iteration']} concluído!")
    custom_print(f"  - Análises revisadas para atender aos requisitos de viabilidade")
    custom_print(f"  - Tokens utilizados até agora: {react_token_counter.get_summary()['total_tokens']} tokens")
    
    # Print detailed refinement results
    custom_print("\n" + "-"*40)
    custom_print("RESULTADO DO REFINAMENTO:")
    custom_print("-"*40)
    
    if len(removed) > 0:
        custom_print(f"⛔ ANÁLISES REMOVIDAS: {len(removed)}")
        for i, item in enumerate(removed):
            custom_print(f"   - {i+1}. {item}")
    
    if len(added) > 0:
        custom_print(f"✅ ANÁLISES ADICIONADAS: {len(added)}")
        for i, item in enumerate(added):
            custom_print(f"   - {i+1}. {item}")
    
    if len(modified) > 0:
        custom_print(f"🔄 ANÁLISES MODIFICADAS: {len(modified)}")
        for i, item in enumerate(modified):
            custom_print(f"   - {i+1}. {item}")
    
    # Extract and print the current list of analyses
    current_analyses = extract_current_analyses(revised_suggestions)
    if current_analyses:
        custom_print("\n📋 LISTA ATUAL DE ANÁLISES (EM ORDEM DE RELEVÂNCIA):")
        for i, analysis in enumerate(current_analyses):
            custom_print(f"   {i+1}. {analysis}")
    
    custom_print("-"*40)
    
    if state["iteration"] == 3:
        custom_print("  - Este foi o último refinamento permitido")
    sys.stdout.flush()
    
    return {
        **state,
        "analysis_suggestions": revised_suggestions,
        "iteration": state["iteration"] + 1
    }

# Add a new function to track analysis changes between iterations
def track_analysis_changes(original: str, revised: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Track which analyses have been added, removed, or modified between iterations.
    
    Args:
        original: Original analysis suggestions text
        revised: Revised analysis suggestions text
        
    Returns:
        Tuple containing sets of (added, removed, modified) analysis names
    """
    # Extract analysis names from text using regex pattern matching
    def extract_analyses(text):
        analyses = {}
        # Look for patterns like "1. Análise de Pareto" or "Análise #1: Gráfico de Controle"
        patterns = [
            r'(\d+)\.\s+([\w\s]+?)(?=\n|:)',
            r'Análise\s+#(\d+):\s+([\w\s]+?)(?=\n|-)',
            r'(\d+)\.\s*(?:Realizar\s+)?((?:Análise|Teste|Gráfico|Diagrama)[\w\s]+?)(?=\n|:)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 2:
                    num = match[0].strip()
                    name = match[1].strip()
                    analyses[num] = name.lower()
        
        return analyses
    
    original_analyses = extract_analyses(original)
    revised_analyses = extract_analyses(revised)
    
    # Identify changes
    original_set = set(original_analyses.values())
    revised_set = set(revised_analyses.values())
    
    added = revised_set - original_set
    removed = original_set - revised_set
    
    # Try to identify modified analyses (similar names)
    modified = set()
    for orig in original_set:
        if orig not in revised_set:
            for rev in revised_set:
                # Check if there's significant overlap in the names
                if orig not in removed or rev not in added:
                    continue
                    
                orig_words = set(orig.lower().split())
                rev_words = set(rev.lower().split())
                
                # If analyses share 50% or more words, consider it modified
                common_words = orig_words.intersection(rev_words)
                if len(common_words) / max(len(orig_words), len(rev_words)) > 0.5:
                    modified.add(orig)
                    if orig in removed:
                        removed.remove(orig)
                    if rev in added:
                        added.remove(rev)
                    break
    
    return added, removed, modified

# Nova função para extrair a lista atual de análises
def extract_current_analyses(text: str) -> List[str]:
    """Extract the current list of analyses from the text."""
    analyses = []
    
    # Look for numbered analyses using regex
    pattern = re.compile(r'^\s*(\d+)\.\s+(.+?)(?=\n|$)', re.MULTILINE)
    matches = pattern.findall(text)
    
    for match in matches:
        analyses.append(match[1].strip())
    
    return analyses

# Update the prepare_final_output function to focus on the Analyze phase
def prepare_final_output(state: ReActAgentState, feasibility_check: str, is_best_effort: bool = False, custom_print=print) -> str:
    """Prepare the final output combining all insights."""
    custom_print("\n" + "="*80)
    custom_print("ETAPA FINAL: PREPARAÇÃO DO DOCUMENTO DE RECOMENDAÇÕES DE ANÁLISE")
    custom_print("="*80)
    custom_print("Finalizando documento de recomendações de técnicas de análise para o usuário...")
    sys.stdout.flush()
    
    llm = initialize_llm()
    
    status = "melhor possível (com algumas limitações)" if is_best_effort else "verificado como viável"
    
    # Use prompt from YAML file
    prompt = ChatPromptTemplate.from_template(PROMPTS.get("prepare_final_output", "Prompt não encontrado"))
    
    # Contar tokens do prompt
    prompt_str = PROMPTS.get("prepare_final_output", "Prompt não encontrado").format(
        status=status,
        enriched_data=state["enriched_data"],
        analysis_suggestions=state["analysis_suggestions"],
        feasibility_check=feasibility_check
    )
    react_token_counter.count_prompt(prompt_str, "prepare_final_output")
    
    chain = prompt | llm | StrOutputParser()
    
    final_output = chain.invoke({
        "enriched_data": state["enriched_data"],
        "analysis_suggestions": state["analysis_suggestions"],
        "feasibility_check": feasibility_check,
        "status": status
    })
    print(final_output)
    custom_print("✓ Documento de recomendações finalizado com sucesso!")
    custom_print(f"  - Status das recomendações: {status}")
    custom_print("  - Entregando recomendações ao usuário")
    
    # Print final list of analyses in order of relevance
    analyses = extract_current_analyses(final_output)
    if analyses:
        custom_print("\n" + "="*80)
        custom_print("ANÁLISES RECOMENDADAS EM ORDEM DE RELEVÂNCIA E EXECUÇÃO:")
        custom_print("="*80)
        for i, analysis in enumerate(analyses):
            custom_print(f"Análise {i+1} - {analysis}")
        custom_print("="*80)
    
    sys.stdout.flush()
    
    # Após gerar resultado final, mostrar contagem total
    custom_print("\n===== UTILIZAÇÃO TOTAL DE TOKENS =====")
    summary = react_token_counter.get_summary()
    custom_print(f"Total de tokens: {summary['total_tokens']}")
    custom_print(f"Tokens de prompt: {summary['prompt_tokens']}")
    custom_print(f"Tokens de completion: {summary['completion_tokens']}")
    custom_print(f"Custo estimado: ${summary['estimated_cost_usd']:.6f}")
    custom_print("=====================================")
    
    return final_output

# Fix the create_react_agent function to properly handle the '__start__' node
def create_react_agent(custom_print=print):
    """Create the ReAct agent for advanced Lean Six Sigma analysis planning."""
    # Initialize the graph
    workflow = StateGraph(ReActAgentState)
    
    # Add nodes with custom print function
    workflow.add_node("enrich_inputs", lambda state: enrich_inputs(state, custom_print))
    workflow.add_node("suggest_analyses", lambda state: suggest_analyses(state, custom_print))
    workflow.add_node("verify_feasibility", lambda state: verify_feasibility(state, custom_print))
    workflow.add_node("refine_recommendations", lambda state: refine_recommendations(state, custom_print))
    
    # Define the graph structure - Entry point must come first
    # THIS IS IMPORTANT: Set entry point BEFORE adding other edges
    workflow.set_entry_point("enrich_inputs")
    
    workflow.add_edge("enrich_inputs", "suggest_analyses")
    workflow.add_edge("suggest_analyses", "verify_feasibility")
    
    # Conditional branching based on verification result
    workflow.add_conditional_edges(
        "verify_feasibility",
        should_refine,
        {
            "refine": "refine_recommendations",
            "end": END
        }
    )
    
    # Complete the loop
    workflow.add_edge("refine_recommendations", "verify_feasibility")
    
    return workflow.compile()

# Atualizar a criação do contador de tokens
# Criar contador de tokens para React Agent
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
react_token_counter = TokenCounter(model=DEFAULT_MODEL)

# Fix the get_advanced_recommendations function to handle the LangGraph initialization properly

def get_advanced_recommendations(dataset_info: str, dependent_vars: List[str], 
                               independent_vars: List[str], 
                               objective: str = "Recomendar técnicas de análise para identificação de causas raiz usando Lean Six Sigma",
                               print_callback: Callable = None):
    """Implementação do agente ReAct para gerar recomendações avançadas de análise"""
    try:
        # Try sequential implementation since LangGraph has issues
        result = get_advanced_recommendations_sequential(
            dataset_info,
            dependent_vars,
            independent_vars,
            objective,
            print_callback
        )
        
        # Ao final da execução, adicionar resumo de tokens
        custom_print = print_callback or print
        custom_print("\n===== RESUMO DE UTILIZAÇÃO DE TOKENS =====")
        summary = react_token_counter.get_summary()
        custom_print(f"Total de tokens consumidos: {summary['total_tokens']}")
        custom_print(f"Prompt tokens: {summary['prompt_tokens']}")
        custom_print(f"Completion tokens: {summary['completion_tokens']}")
        custom_print(f"Custo estimado: ${summary['estimated_cost_usd']:.6f}")
        custom_print("========================================")
        
        return result
    except Exception as e:
        # Fall back to a super simple implementation if everything else fails
        custom_print = print_callback if print_callback else print
        error_message = f"Erro fatal na análise: {str(e)}"
        custom_print(f"ERRO: {error_message}")
        import traceback
        traceback.print_exc()
        return f"## Erro na Análise Avançada\n\n{error_message}\n\nPor favor, tente novamente ou use a abordagem de análise padrão."

# Add a fallback implementation function at the bottom of the file

def get_advanced_recommendations_sequential(dataset_info: str, dependent_vars: List[str], 
                               independent_vars: List[str], 
                               objective: str = "Recomendar técnicas de análise para identificação de causas raiz usando Lean Six Sigma",
                               print_callback: Callable = None):
    """Implementação sequencial (sem LangGraph) do agente ReAct."""
    # Use the provided callback or default to print
    custom_print = print_callback if print_callback else print
    
    try:
        custom_print("\n" + "#"*100)
        custom_print("INICIANDO PROCESSAMENTO DE RECOMENDAÇÕES DE ANÁLISE (Versão Sequencial)")
        custom_print("#"*100)
        custom_print("FLUXO DO PROCESSO:")
        custom_print("1️⃣ Etapa 1: Enriquecer as informações recebidas no input")
        custom_print("2️⃣ Etapa 2: Recomendar técnicas de ANÁLISE focadas em causas raiz e relações")
        custom_print("3️⃣ Etapa 3: Verificar se as análises são possíveis de executar com os dados disponíveis")
        custom_print("   - Se não forem viáveis, refinar removendo análises não possíveis (máx 3 tentativas)")
        custom_print("4️⃣ Etapa 4: Entregar recomendações finais de técnicas de ANÁLISE ao usuário")
        custom_print("#"*100)
        custom_print(f"Variáveis dependentes: {', '.join(dependent_vars)}")
        custom_print(f"Variáveis independentes: {', '.join(independent_vars)}")
        custom_print(f"Objetivo: {objective}")
        custom_print("#"*100 + "\n")
        sys.stdout.flush()
        
        # Initialize state dictionary manually
        state = {
            "dataset_info": dataset_info,
            "dependent_variables": dependent_vars,
            "independent_variables": independent_vars,
            "objective": objective,
            "iteration": 0,
            "enriched_data": None,
            "analysis_suggestions": None,
            "feasibility_check": None,
            "output": None
        }
        
        # Step 1: Enrich inputs
        state = enrich_inputs(state, custom_print)
        
        # Step 2: Suggest analyses
        state = suggest_analyses(state, custom_print)
        
        # Step 3: Verify feasibility (with potential refinement loop)
        max_iterations = 3
        current_iteration = 1
        
        while current_iteration <= max_iterations:
            # Verify feasibility
            state = verify_feasibility(state, custom_print)
            
            # Check if we have output (feasible) or reached max iterations
            if state.get("output") is not None:
                break
                
            # If no output and not max iterations yet, refine and try again
            if current_iteration < max_iterations:
                state = refine_recommendations(state, custom_print)
                current_iteration += 1
            else:
                # Force final output on last iteration
                custom_print("⚠ Atingido número máximo de iterações. Gerando melhor output possível.")
                state["output"] = prepare_final_output(state, state["feasibility_check"], is_best_effort=True, custom_print=custom_print)
                break
        
        # Log token usage summary at the end
        import logging
        logger = logging.getLogger("lean-six-sigma-api.react-agent")
        logger.info("===== Uso de Tokens do Processamento Sequencial =====")
        react_token_counter.log_summary()
        
        custom_print("\n" + "#"*100)
        custom_print("PROCESSO CONCLUÍDO!")
        custom_print("#"*100)
        
        return state["output"]
        
    except Exception as e:
        error_message = f"Erro no processamento: {str(e)}"
        custom_print(f"ERRO: {error_message}")
        import traceback
        traceback.print_exc()
        return f"## Erro na Análise Avançada\n\n{error_message}\n\nPor favor, tente novamente ou use a abordagem de análise padrão."