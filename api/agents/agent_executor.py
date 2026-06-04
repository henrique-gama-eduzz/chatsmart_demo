import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import re
from typing import Dict, Any, List
import sys
import traceback
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import logging

# Fix the import statement before any code that uses it
import os
import sys
# Add the project root to Python path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from utils.token_counter import TokenCounter
from utils.llm_utils import initialize_llm  # Importar a função centralizada

logging.basicConfig(level=logging.INFO)

# Configurar matplotlib para não mostrar janelas interativas - ADICIONAR ISTO
plt.ioff()  # Desativa o modo interativo
plt.switch_backend('Agg')  # Usa o backend que não exibe janelas

# Carregar variáveis de ambiente
load_dotenv()

# Melhorar a função extract_analyses para extrair corretamente as variáveis
def extract_analyses(recommendations: str) -> List[Dict[str, Any]]:
    """Extract individual analyses from recommendations text with multiple formats."""
    analyses = []
    logging.info("Iniciando extração de análises")
    
    try:
        # Primeiro tente dividir pelo padrão de separador
        analysis_blocks = re.split(r'={3,}', recommendations)
        logging.info(f"Blocos brutos encontrados: {len(analysis_blocks)}")
        
        # Processar cada bloco que possa conter informações de análise
        for i, block in enumerate(analysis_blocks):
            if not block.strip():
                continue
                
            logging.info(f"Processando bloco {i+1}/{len(analysis_blocks)}")
            analysis = {}
            
            # Extrair número e nome da análise com vários padrões possíveis
            title_patterns = [
                r'<h3[^>]*>Análise\s+(\d+)\s*-\s*([^<]+)</h3>',  # HTML format
                r'Análise\s+(\d+)\s*-\s*([^\n]+)',               # Plain text format
                r'#*\s*Análise\s+(\d+)\s*[-:]\s*([^\n]+)',       # Markdown format
                r'(\d+)\.\s+((?:Análise|Teste|Avaliação)[^\n]+)' # Numbered list format
            ]
            
            # Tentar todos os padrões
            title_match = None
            for pattern in title_patterns:
                match = re.search(pattern, block)
                if match:
                    title_match = match
                    break
            
            if title_match:
                try:
                    analysis["number"] = int(title_match.group(1))
                    analysis["name"] = title_match.group(2).strip()
                    
                    # Melhorar a extração de variáveis dependentes
                    dep_vars_patterns = [
                        r'[Vv]ariáveis\s+dependentes:\s*([\w\s,]+?)(?=\n|\r|$|Variáveis\s+independentes)',
                        r'[Dd]ependentes?:\s*([\w\s,]+?)(?=\n|\r|$|[Ii]ndependentes)',
                        r'[Vv]ariáveis\s+dependentes[^:]*?:\s*(\w+(?:\s*,\s*\w+)*)',
                        r'[Dd]ependentes?[^:]*?:\s*(\w+(?:\s*,\s*\w+)*)'
                    ]
                    
                    # Tenta cada padrão até encontrar um match
                    dep_vars_found = False
                    for pattern in dep_vars_patterns:
                        dep_vars_match = re.search(pattern, block, re.IGNORECASE)
                        if dep_vars_match:
                            # Divide a string pelos separadores (vírgulas) e limpa
                            vars_text = dep_vars_match.group(1).strip()
                            # Extrai nomes de variáveis - ignora texto explicativo
                            variable_names = []
                            for var in vars_text.split(','):
                                var = var.strip()
                                if var and len(var) < 30 and not var.startswith('e as') and not var.endswith('.'):
                                    variable_names.append(var)
                            
                            analysis["dependent_vars"] = variable_names
                            dep_vars_found = True
                            break
                    
                    # Extrair variáveis independentes - melhorado
                    indep_vars_patterns = [
                        r'[Vv]ariáveis\s+independentes:\s*([\w\s,]+?)(?=\n|\r|$)',
                        r'[Ii]ndependentes?:\s*([\w\s,]+?)(?=\n|\r|$)',
                        r'[Vv]ariáveis\s+independentes[^:]*?:\s*(\w+(?:\s*,\s*\w+)*)',
                        r'[Ii]ndependentes?[^:]*?:\s*(\w+(?:\s*,\s*\w+)*)'
                    ]
                    
                    indep_vars_found = False
                    for pattern in indep_vars_patterns:
                        indep_vars_match = re.search(pattern, block, re.IGNORECASE)
                        if indep_vars_match:
                            # Divide a string pelos separadores e limpa
                            vars_text = indep_vars_match.group(1).strip()
                            # Extrai nomes de variáveis - ignora texto explicativo
                            variable_names = []
                            for var in vars_text.split(','):
                                var = var.strip()
                                if var and len(var) < 30 and not var.startswith('e as') and not var.endswith('.'):
                                    variable_names.append(var)
                            
                            analysis["independent_vars"] = variable_names
                            indep_vars_found = True
                            break
                    
                    # Usar fallbacks se não encontrou as variáveis
                    if not dep_vars_found:
                        analysis["dependent_vars"] = []
                        logging.warning(f"Variáveis dependentes não encontradas no bloco {i+1}")
                    if not indep_vars_found:
                        analysis["independent_vars"] = []
                        logging.warning(f"Variáveis independentes não encontradas no bloco {i+1}")
                    
                    # Extrair contexto - tentar vários padrões
                    context_patterns = [
                        r'Contexto de Aplicação</h4>\s*<p>([^<]+)</p>',
                        r'Contexto de Aplicação\s*\n([^\n]+)',
                        r'Contexto:?\s*\n([^\n]+)'
                    ]
                    
                    for pattern in context_patterns:
                        context_match = re.search(pattern, block)
                        if context_match:
                            analysis["context"] = context_match.group(1).strip()
                            break
                    
                    # Se não encontrar contexto, usar texto genérico
                    if "context" not in analysis:
                        analysis["context"] = f"Análise {analysis['number']}: {analysis['name']}"
                    
                    # Armazenar o conteúdo bruto
                    analysis["content"] = block.strip()
                    analysis["status"] = "pending"
                    
                    # Adicionar à nossa lista
                    analyses.append(analysis)
                    logging.info(f"Análise {analysis['number']} extraída com sucesso")
                except Exception as e:
                    logging.error(f"Erro ao extrair detalhes da análise no bloco {i+1}: {str(e)}")
        
        # Se não encontramos nenhuma análise com o método padrão, tente método alternativo mais simples
        if not analyses:
            logging.warning("Método padrão não encontrou análises, tentando método alternativo")
            # Encontre blocos que contenham a palavra "Análise" seguida de um número
            alt_matches = re.finditer(r'Análise\s*(\d+)[\s\-:]+([^\n]+)', recommendations)
            
            for i, match in enumerate(alt_matches):
                analysis = {
                    "number": int(match.group(1)),
                    "name": match.group(2).strip(),
                    "dependent_vars": [],  # Será atualizado pelo chamador
                    "independent_vars": [], # Será atualizado pelo chamador
                    "content": match.group(0),
                    "context": match.group(2).strip(),
                    "status": "pending"
                }
                analyses.append(analysis)
                logging.info(f"Análise {analysis['number']} extraída com método alternativo")
    except Exception as e:
        logging.error(f"Erro ao extrair análises: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
    
    # Ordenar por número
    analyses.sort(key=lambda x: x.get("number", 0))
    logging.info(f"Total de análises extraídas: {len(analyses)}")
    return analyses

def get_analysis_steps(recommendations: str) -> List[Dict[str, Any]]:
    """Extract and format analyses as individual steps."""
    analyses = extract_analyses(recommendations)
    steps = []
    
    for analysis in analyses:
        steps.append({
            "number": analysis["number"],
            "name": analysis["name"],
            "content": analysis["content"],
            "dependent_vars": analysis["dependent_vars"],
            "independent_vars": analysis["independent_vars"],
            "status": "pending"
        })
    
    return steps

# Melhorando o tratamento de erros na função execute_analysis
# Adicionar uma função auxiliar para validar análise antes da execução
def extract_variables_from_content(content: str) -> Dict[str, List[str]]:
    """Extract variables from analysis content using improved regex patterns."""
    result = {
        "dependent_vars": [],
        "independent_vars": []
    }
    
    # Padrões mais específicos com melhor tratamento para múltiplas variáveis
    dependent_patterns = [
        r'[Vv]ariáveis\s+[Dd]ependentes\s*[:=]\s*([^"\n]+?)(?=[Vv]ariáveis|$|\n\n)',
        r'[Vv]ariáveis\s+[Dd]ependentes\s*[:=]\s*"([^"]+)"',
        r'[Vv]ariáveis?\s+(?:a\s+[Ss]erem\s+[Uu]tilizadas\s+)?\n?\s*[Vv]ariáveis?\s+[Dd]ependentes\s*:?\s*([^"\n]+?)(?=\n\n|\n[Vv]ariáveis|\Z)',
        r'[Dd]ependentes\s*[:=]\s*([^"\n]+?)(?=[Ii]ndependentes|$|\n\n)'
    ]
    
    independent_patterns = [
        r'[Vv]ariáveis\s+[Ii]ndependentes\s*[:=]\s*([^"\n]+?)(?=$|\n\n)',
        r'[Vv]ariáveis\s+[Ii]ndependentes\s*[:=]\s*"([^"]+)"',
        r'[Vv]ariáveis?\s+(?:a\s+[Ss]erem\s+[Uu]tilizadas\s+)?\n?\s*[Vv]ariáveis?\s+[Ii]ndependentes\s*:?\s*([^"\n]+?)(?=\n\n|\Z)',
        r'[Ii]ndependentes\s*[:=]\s*([^"\n]+?)(?=$|\n\n)'
    ]
    
    # Extract dependent variables
    for pattern in dependent_patterns:
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            vars_text = match.group(1).strip()
            # Split by comma and clean up
            raw_vars = [var.strip() for var in vars_text.split(',')]
            # Filter out longer explanatory text and invalid variable names
            clean_vars = []
            for var in raw_vars:
                # Skip if too long (likely explanatory text) or contains periods or other invalid chars
                if len(var) <= 30 and '.' not in var and ':' not in var and ';' not in var and 'é' not in var.lower():
                    clean_vars.append(var)
            result["dependent_vars"] = clean_vars
            logging.info(f"Variáveis dependentes extraídas: {result['dependent_vars']}")
            break
    
    # Extract independent variables
    for pattern in independent_patterns:
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            vars_text = match.group(1).strip()
            # Split by comma and clean up
            raw_vars = [var.strip() for var in vars_text.split(',')]
            # Filter out longer explanatory text and invalid variable names
            clean_vars = []
            for var in raw_vars:
                # Skip if too long (likely explanatory text) or contains periods or other invalid chars
                if len(var) <= 30 and '.' not in var and ':' not in var and ';' not in var and 'é' not in var.lower():
                    clean_vars.append(var)
            result["independent_vars"] = clean_vars
            logging.info(f"Variáveis independentes extraídas: {result['independent_vars']}")
            break
    
    return result

def validate_analysis(df: pd.DataFrame, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Validate analysis before execution and fix common issues."""
    validated = analysis.copy()
    
    # Log para depuração
    logging.info(f"Validando análise: {validated}")
    logging.info(f"Conteúdo da análise: {validated.get('content', '(vazio)')[:200]}...")
    
    # Always prioritize the explicitly defined variables
    # Only extract variables from content if they're missing or empty
    extracted_vars = None
    
    # Verificar se as variáveis explicitamente definidas são válidas
    # (não são textos longos explicativos ou contêm caracteres inválidos)
    if "dependent_vars" in validated and validated["dependent_vars"]:
        validated["dependent_vars"] = [
            var for var in validated["dependent_vars"] 
            if isinstance(var, str) and len(var) <= 30 and '.' not in var and ':' not in var 
            and ';' not in var and 'é' not in var.lower()
        ]
        
    if "independent_vars" in validated and validated["independent_vars"]:
        validated["independent_vars"] = [
            var for var in validated["independent_vars"] 
            if isinstance(var, str) and len(var) <= 30 and '.' not in var and ':' not in var 
            and ';' not in var and 'é' not in var.lower()
        ]
    
    if "content" in validated and validated["content"]:
        # Sempre extrair variáveis do conteúdo para comparação
        extracted_vars = extract_variables_from_content(validated["content"])
        logging.info(f"Variáveis extraídas do conteúdo: dep={extracted_vars['dependent_vars']}, indep={extracted_vars['independent_vars']}")
    
    # IMPORTANTE: Se já temos variáveis explícitas no análise (payload), usar essas preferencialmente
    has_explicit_dep_vars = "dependent_vars" in validated and validated["dependent_vars"] and len(validated["dependent_vars"]) > 0
    has_explicit_indep_vars = "independent_vars" in validated and validated["independent_vars"] and len(validated["independent_vars"]) > 0
    
    # Se não existirem variáveis ou estiverem vazias, usar as extraídas do conteúdo
    if not has_explicit_dep_vars:
        logging.warning("Variáveis dependentes não encontradas nos campos específicos, tentando extração do conteúdo")
        if extracted_vars and extracted_vars["dependent_vars"]:
            validated["dependent_vars"] = extracted_vars["dependent_vars"]
            logging.info(f"Variáveis dependentes definidas a partir do conteúdo: {validated['dependent_vars']}")
    else:
        logging.info(f"Usando variáveis dependentes validadas do payload: {validated['dependent_vars']}")
        
    if not has_explicit_indep_vars:
        logging.warning("Variáveis independentes não encontradas nos campos específicos, tentando extração do conteúdo")
        if extracted_vars and extracted_vars["independent_vars"]:
            validated["independent_vars"] = extracted_vars["independent_vars"]
            logging.info(f"Variáveis independentes definidas a partir do conteúdo: {validated['independent_vars']}")
    else:
        logging.info(f"Usando variáveis independentes validadas do payload: {validated['independent_vars']}")

    # Verificar se as variáveis são válidas no DataFrame columns
    valid_dep_vars = []
    if "dependent_vars" in validated and validated["dependent_vars"]:
        for var in validated["dependent_vars"]:
            if var in df.columns:
                valid_dep_vars.append(var)
                logging.info(f"Variável dependente válida: {var}")
            else:
                logging.warning(f"Variável dependente '{var}' não encontrada no DataFrame")
    
    # Se não houver variáveis dependentes válidas nas colunas do DataFrame
    if not valid_dep_vars:
        if "dependent_vars" in validated and validated["dependent_vars"]:
            # Manter as variáveis originais se foram explicitamente especificadas
            valid_dep_vars = validated["dependent_vars"]
            logging.warning(f"Usando variáveis dependentes originais (não encontradas no DataFrame): {valid_dep_vars}")
        else:
            logging.warning("Nenhuma variável dependente válida no DataFrame, tentando obter colunas numéricas")
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                valid_dep_vars = [numeric_cols[0]]
                logging.warning(f"Usando coluna numérica {numeric_cols[0]} como variável dependente (fallback)")
    
    validated["dependent_vars"] = valid_dep_vars
    
    # Verificar se as variáveis independentes são válidas
    valid_indep_vars = []
    if "independent_vars" in validated and validated["independent_vars"]:
        for var in validated["independent_vars"]:
            if var in df.columns:
                valid_indep_vars.append(var)
                logging.info(f"Variável independente válida: {var}")
            else:
                logging.warning(f"Variável independente '{var}' não encontrada no DataFrame")
    
    # Se não houver variáveis independentes válidas nas colunas do DataFrame
    if not valid_indep_vars:
        if "independent_vars" in validated and validated["independent_vars"]:
            # Manter as variáveis originais se foram explicitamente especificadas
            valid_indep_vars = validated["independent_vars"]
            logging.warning(f"Usando variáveis independentes originais (não encontradas no DataFrame): {valid_indep_vars}")
        else:
            logging.warning("Nenhuma variável independente válida no DataFrame, tentando obter outras colunas")
            remaining_cols = [col for col in df.columns if col not in valid_dep_vars]
            if remaining_cols:
                valid_indep_vars = [remaining_cols[0]]
                logging.warning(f"Usando coluna {remaining_cols[0]} como variável independente (fallback)")
    
    validated["independent_vars"] = valid_indep_vars
    
    # Log do resultado da validação
    logging.info(f"Variáveis finais após validação: dep_vars={validated['dependent_vars']}, indep_vars={validated['independent_vars']}")
    
    return validated

def execute_analysis(df: pd.DataFrame, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single analysis on the DataFrame."""
    results = {
        "success": False,
        "number": analysis.get("number", 0),
        "name": analysis.get("name", "Análise desconhecida"),
        "plots": [],
        "tables": [],
        "text_output": "",
        "interpretation": None,
        "error": None
    }
    
    try:
        # Debug logging with more details
        logging.info(f"Análise original recebida: número={analysis.get('number')}, nome={analysis.get('name')}")
        logging.info(f"Variáveis dependentes recebidas: {analysis.get('dependent_vars', [])}")
        logging.info(f"Variáveis independentes recebidas: {analysis.get('independent_vars', [])}")
        
        print(df.columns)  # Debug print to check DataFrame columns

        # Primeiro validar e corrigir a análise
        validated_analysis = validate_analysis(df, analysis)

        # Log detalhado para validar resultado após validação
        logging.info(f"Análise validada: {validated_analysis}")
        logging.info(f"Variáveis dependentes após validação: {validated_analysis.get('dependent_vars', [])}")
        logging.info(f"Variáveis independentes após validação: {validated_analysis.get('independent_vars', [])}")
        
        # Verificações iniciais para evitar erros comuns
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("DataFrame vazio ou inválido")
            
        if not validated_analysis.get("dependent_vars") or not validated_analysis.get("independent_vars"):
            error_msg = "Variáveis dependentes ou independentes não especificadas ou inválidas"
            logging.error(f"Erro de validação: {error_msg}")
            raise ValueError(error_msg)
        
        # Verificar se todas as variáveis existem no DataFrame
        missing_vars = []
        print(f"Verificando variáveis no DataFrame: {df.columns.tolist()}")
        print(f"Variáveis dependentes: {validated_analysis.get('dependent_vars', [])}")
        for var in validated_analysis.get("dependent_vars", []) + validated_analysis.get("independent_vars", []):
            if var not in df.columns:
                missing_vars.append(var)
        if missing_vars:
            raise ValueError(f"Variáveis inexistentes no DataFrame: {', '.join(missing_vars)}")
        
        # Resto da implementação permanece igual...
        # Capture stdout for print statements
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Generate Python code for this analysis
        code = generate_analysis_code(df, validated_analysis)
        
        if not code:
            raise ValueError("Não foi possível gerar código para esta análise")
        
        # Capture matplotlib figures
        original_figure = plt.figure
        figures = []
        
        def custom_figure(*args, **kwargs):
            fig = original_figure(*args, **kwargs)
            figures.append(fig)
            return fig
        
        plt.figure = custom_figure
        plt.close('all')  # Close any existing plots
        
        # Create a namespace for execution
        namespace = {
            'pd': pd,
            'np': np,
            'plt': plt,
            'sns': sns,
            'df': df,
            'dependent_vars': validated_analysis["dependent_vars"],
            'independent_vars': validated_analysis["independent_vars"],
            'result_tables': []
        }
        
        # Modificar o código para substituir qualquer plt.show() por pass
        code = code.replace('plt.show()', 'pass')
        
        # Execute the code with timeout para evitar loops infinitos
        try:
            exec(code, namespace)
        except Exception as code_error:
            # Tentar código de fallback se o código principal falhar
            print(f"Erro ao executar código principal: {str(code_error)}")
            fallback_code = generate_fallback_code(validated_analysis, df)
            exec(fallback_code, namespace)
        
        # Capture all figures that were created
        for i, fig in enumerate(figures):
            try:
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                results["plots"].append({
                    "id": f"plot_{validated_analysis['number']}_{i}",
                    "data": base64.b64encode(buf.read()).decode('utf-8')
                })
            except Exception as fig_error:
                print(f"Erro ao salvar figura {i}: {str(fig_error)}")
        
        # Get any tables that were created and added to result_tables
        if 'result_tables' in namespace and isinstance(namespace['result_tables'], list):
            for i, table in enumerate(namespace['result_tables']):
                try:
                    if isinstance(table, pd.DataFrame):
                        results["tables"].append({
                            "id": f"table_{validated_analysis['number']}_{i}",
                            "html": table.head(20).to_html(classes="table table-striped table-hover"),
                            "description": f"Tabela {i+1}"
                        })
                except Exception as table_error:
                    print(f"Erro ao processar tabela {i}: {str(table_error)}")
        
        # Also check for any DataFrames created in the namespace
        for name, value in namespace.items():
            try:
                if isinstance(value, pd.DataFrame) and name != 'df' and name not in ['result_tables']:
                    if len(results["tables"]) < 5:  # Limit number of tables
                        results["tables"].append({
                            "id": f"table_{validated_analysis['number']}_{name}",
                            "html": value.head(10).to_html(classes="table table-striped table-hover"),
                            "description": f"DataFrame: {name}"
                        })
            except Exception as df_error:
                print(f"Erro ao processar DataFrame {name}: {str(df_error)}")
        
        # Get text output
        results["text_output"] = captured_output.getvalue()
        
        # Se não conseguimos gerar plots ou tabelas, criar um resumo básico
        if not results["plots"] and not results["tables"]:
            create_basic_summary(df, validated_analysis, results)
        
        # Gerar interpretação dos resultados usando LLM
        results["interpretation"] = generate_interpretation(
            results["text_output"], 
            results["plots"], 
            results["tables"],
            validated_analysis
        )
        
        # Success if we have something to show
        results["success"] = True
        
    except Exception as e:
        results["error"] = f"Erro ao executar análise: {str(e)}\n{traceback.format_exc()}"
        
        # Ainda assim, tente criar um resumo básico mesmo em caso de erro
        try:
            create_basic_summary(df, validated_analysis, results)
            results["text_output"] += "\n\nNOTA: Esta é uma análise simplificada gerada após erro na execução da análise completa."
        except:
            results["text_output"] = "Não foi possível executar a análise devido a um erro."
    finally:
        # Reset stdout and close plots
        try:
            sys.stdout = old_stdout
            plt.close('all')
            plt.figure = original_figure
        except:
            pass
    
    return results

# Nova função para criar um resumo básico como fallback
def create_basic_summary(df: pd.DataFrame, analysis: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Create a basic summary of the variables when other analyses fail."""
    try:
        # Verificar se temos variáveis válidas
        if not analysis.get("dependent_vars") or not analysis.get("independent_vars"):
            results["text_output"] = "Erro: Não foi possível encontrar variáveis válidas para a análise."
            logging.error("Tentativa de criar resumo básico sem variáveis válidas")
            return
        
        # Criar pelo menos uma visualização básica
        plt.figure(figsize=(10, 6))
        
        # Garantir que estamos usando variáveis que existem no DataFrame
        dep_vars = []
        indep_vars = []
        
        for var in analysis.get("dependent_vars", []):
            if var in df.columns:
                dep_vars.append(var)
        
        for var in analysis.get("independent_vars", []):
            if var in df.columns:
                indep_vars.append(var)
        
        if not dep_vars or not indep_vars:
            results["text_output"] = "Erro: As variáveis selecionadas não existem no DataFrame."
            logging.error(f"Variáveis não encontradas no DataFrame: dep={analysis.get('dependent_vars')}, indep={analysis.get('independent_vars')}")
            # Incluir informação de debug
            results["text_output"] += f"\nVariáveis dependentes: {analysis.get('dependent_vars', [])} (válidas: {dep_vars})"
            results["text_output"] += f"\nVariáveis independentes: {analysis.get('independent_vars', [])} (válidas: {indep_vars})"
            results["text_output"] += f"\nColunas disponíveis: {list(df.columns)}"
            return
            
        dep_var = dep_vars[0] if dep_vars else None
        indep_var = indep_vars[0] if indep_vars else None
        
        if dep_var and indep_var:
            # Verificar tipos de dados
            if pd.api.types.is_numeric_dtype(df[dep_var]) and pd.api.types.is_numeric_dtype(df[indep_var]):
                # Ambas numéricas: scatter plot
                plt.scatter(df[indep_var], df[dep_var])
                plt.title(f'Relação entre {dep_var} e {indep_var}')
                plt.xlabel(indep_var)
                plt.ylabel(dep_var)
                plt.grid(True)
            elif pd.api.types.is_numeric_dtype(df[dep_var]):
                # Dependente numérica, independente categórica: box plot
                plt.boxplot([df[df[indep_var] == cat][dep_var].dropna() for cat in df[indep_var].unique()], 
                           labels=df[indep_var].unique())
                plt.title(f'{dep_var} por {indep_var}')
                plt.ylabel(dep_var)
                plt.grid(True)
            elif pd.api.types.is_numeric_dtype(df[indep_var]):
                # Independente numérica, dependente categórica: histograma agrupado
                for cat in df[dep_var].unique():
                    plt.hist(df[df[dep_var] == cat][indep_var].dropna(), alpha=0.5, label=cat)
                plt.title(f'Distribuição de {indep_var} por {dep_var}')
                plt.xlabel(indep_var)
                plt.legend()
                plt.grid(True)
            else:
                # Ambas categóricas: tabela de contingência/heatmap
                contingency = pd.crosstab(df[dep_var], df[indep_var])
                sns.heatmap(contingency, annot=True, fmt='d', cmap='Blues')
                plt.title(f'Tabela de Contingência: {dep_var} vs {indep_var}')
        
        # Salvar o gráfico básico
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        results["plots"].append({
            "id": f"plot_basic",
            "data": base64.b64encode(buf.read()).decode('utf-8')
        })
        
        # Criar uma tabela de resumo básica
        if dep_var:
            basic_stats = df[dep_var].describe().to_frame()
            
            # Adicionar correlação se apropriado
            if dep_var and indep_var and pd.api.types.is_numeric_dtype(df[dep_var]) and pd.api.types.is_numeric_dtype(df[indep_var]):
                corr = df[dep_var].corr(df[indep_var])
                basic_stats.loc['correlation'] = corr
            
            results["tables"].append({
                "id": "table_basic",
                "html": basic_stats.to_html(classes="table table-striped"),
                "description": f"Estatísticas básicas para {dep_var}"
            })
            
            results["text_output"] += f"\nResumo básico criado para {dep_var} e {indep_var}."
            
    except Exception as e:
        # Se mesmo o resumo básico falhar, adicione uma mensagem ao output
        error_msg = f"Erro ao criar resumo básico: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        results["text_output"] += f"\n{error_msg}"

def generate_analysis_code(df: pd.DataFrame, analysis: Dict[str, Any]) -> str:
    """Generate Python code to perform the analysis based on the description."""
    # Extract column info
    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    categorical_cols = [col for col in df.columns if not pd.api.types.is_numeric_dtype(df[col])]
    
    # Extract analysis type
    analysis_name = analysis["name"].lower()
    dep_vars = analysis["dependent_vars"]
    indep_vars = analysis["independent_vars"]
    
    analysis_prompt = f"""
    # TAREFA: GERAR CÓDIGO PYTHON PARA ANÁLISE ESTATÍSTICA
    
    Você é um especialista em ciência de dados especializado em Lean Six Sigma.
    
    ## Análise a ser implementada
    Número: {analysis["number"]}
    Nome: {analysis["name"]}
    
    ## Informações da análise
    {analysis["content"]}
    
    ## Variáveis disponíveis
    Dependentes: {', '.join(analysis["dependent_vars"])}
    Independentes: {', '.join(analysis["independent_vars"])}
    
    ## Colunas do DataFrame
    O DataFrame está disponível como 'df' e contém as seguintes colunas:
    - Numéricas: {', '.join(numeric_cols)}
    - Categóricas: {', '.join(categorical_cols)}
    
    ## Sua tarefa
    Gere um código Python completo que:
    1. Implemente a análise {analysis["name"]} usando as variáveis especificadas
    2. Crie visualizações claras usando matplotlib e seaborn
    3. Calcule estatísticas relevantes
    4. Armazene DataFrames resultantes na lista 'result_tables'
    5. Exiba conclusões claras com print()
    
    O código deve ser independente e usar apenas as bibliotecas: pandas, numpy, matplotlib, seaborn.
    Não inclua comentários sobre o código, apenas o código executável.
    """
    
    try:
        llm = initialize_llm()
        prompt_template = ChatPromptTemplate.from_template(analysis_prompt)
        
        # Contar tokens do prompt
        prompt_str = analysis_prompt  # Já é uma string
        agent_token_counter.count_prompt(prompt_str, f"gerar_codigo_{analysis['number']}")
        
        chain = prompt_template | llm | StrOutputParser()
        code = chain.invoke({})
        
        # Contar tokens da resposta
        agent_token_counter.count_completion(code, f"gerar_codigo_{analysis['number']}")
        
        # Registrar estatísticas
        logging.info(f"Estatísticas de tokens para análise #{analysis['number']}:")
        agent_token_counter.log_summary()
        
        # Extract only the Python code if enclosed in code blocks
        code_pattern = re.compile(r'```python\s*(.*?)\s*```', re.DOTALL)
        code_match = code_pattern.search(code)
        
        if code_match:
            return code_match.group(1)
        else:
            # If no code block is found, use the whole response
            return code
    
    except Exception as e:
        print(f"Erro ao gerar código: {str(e)}")
        # Fallback code generator based on analysis type
        return generate_fallback_code(analysis, df)

def generate_fallback_code(analysis: Dict[str, Any], df: pd.DataFrame) -> str:
    """Generate fallback code for common analysis types if API call fails."""
    name = analysis["name"].lower()
    dep_vars = analysis["dependent_vars"]
    indep_vars = analysis["independent_vars"]
    
    if not dep_vars or not indep_vars:
        return "print('Erro: Variáveis dependentes ou independentes não especificadas')"
    
    # Regression analysis
    if "regressão" in name:
        return f"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Prepare data
X = df[{indep_vars}]
y = df['{dep_vars[0]}']

# Create scatter plot
plt.figure(figsize=(10, 6))
plt.scatter(X, y)
plt.title('Scatter plot: {dep_vars[0]} vs {indep_vars[0]}')
plt.xlabel('{indep_vars[0]}')
plt.ylabel('{dep_vars[0]}')
plt.grid(True)

# Calculate correlation
correlation = df['{dep_vars[0]}'].corr(df['{indep_vars[0]}'])
print(f"Correlação entre {dep_vars[0]} e {indep_vars[0]}: {correlation:.4f}")

# Simple linear regression
from scipy import stats
slope, intercept, r_value, p_value, std_err = stats.linregress(df['{indep_vars[0]}'], df['{dep_vars[0]}'])

# Add regression line to plot
plt.plot(df['{indep_vars[0]}'], intercept + slope * df['{indep_vars[0]}'], 'r')
plt.legend(['Dados', 'Regressão Linear'])

# Print regression results
print(f"Equação de regressão: y = {slope:.4f} * x + {intercept:.4f}")
print(f"R²: {r_value**2:.4f}")
print(f"p-valor: {p_value:.4f}")

# Add results to tables
result_df = pd.DataFrame({
    'Métrica': ['Correlação', 'Slope', 'Intercept', 'R²', 'p-valor'],
    'Valor': [correlation, slope, intercept, r_value**2, p_value]
})
result_tables.append(result_df)
        """
    
    # ANOVA or comparison
    elif any(t in name for t in ["anova", "comparação", "teste t"]):
        return f"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Create box plot
plt.figure(figsize=(12, 6))
sns.boxplot(x='{indep_vars[0]}', y='{dep_vars[0]}', data=df)
plt.title(f'Boxplot de {dep_vars[0]} agrupado por {indep_vars[0]}')
plt.grid(True)

# Create summary statistics by group
grouped_stats = df.groupby('{indep_vars[0]}')['{dep_vars[0]}'].agg(['count', 'mean', 'std', 'min', 'max']).round(2)
print("Estatísticas por grupo:")
print(grouped_stats)
result_tables.append(grouped_stats)

# Perform one-way ANOVA if there are more than 2 categories
categories = df['{indep_vars[0]}'].unique()
if len(categories) > 2:
    groups = [df[df['{indep_vars[0]}'] == cat]['{dep_vars[0]}'].dropna() for cat in categories]
    f_val, p_val = stats.f_oneway(*groups)
    print(f"\\nResultados ANOVA:")
    print(f"F-valor: {f_val:.4f}")
    print(f"p-valor: {p_val:.4f}")
    if p_val < 0.05:
        print(f"Conclusão: Existe diferença significativa entre os grupos (p<0.05)")
    else:
        print(f"Conclusão: Não há evidência de diferença significativa entre os grupos (p>0.05)")
    
    anova_results = pd.DataFrame({
        'Métrica': ['F-valor', 'p-valor'],
        'Valor': [f_val, p_val]
    })
    result_tables.append(anova_results)
# Perform t-test for 2 categories
elif len(categories) == 2:
    group1 = df[df['{indep_vars[0]}'] == categories[0]]['{dep_vars[0]}'].dropna()
    group2 = df[df['{indep_vars[0]}'] == categories[1]]['{dep_vars[0]}'].dropna()
    t_stat, p_val = stats.ttest_ind(group1, group2, equal_var=False)
    print(f"\\nResultados Teste-t:")
    print(f"t-estatística: {t_stat:.4f}")
    print(f"p-valor: {p_val:.4f}")
    if p_val < 0.05:
        print(f"Conclusão: Existe diferença significativa entre {categories[0]} e {categories[1]} (p<0.05)")
    else:
        print(f"Conclusão: Não há evidência de diferença significativa (p>0.05)")
    
    ttest_results = pd.DataFrame({
        'Métrica': ['t-estatística', 'p-valor'],
        'Valor': [t_stat, p_val]
    })
    result_tables.append(ttest_results)
        """
    
    # Correlation analysis
    elif "correlação" in name:
        return f"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Select numeric columns
numeric_df = df.select_dtypes(include=['number'])

# Create correlation matrix
corr_matrix = numeric_df.corr().round(3)
print("Matriz de correlação:")
print(corr_matrix)
result_tables.append(corr_matrix)

# Create correlation heatmap
plt.figure(figsize=(10, 8))
sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1, 
            fmt='.2f', linewidths=0.5)
plt.title('Matriz de Correlação')
plt.tight_layout()

# Highlight correlations with dependent variable
dep_corr = corr_matrix['{dep_vars[0]}'].sort_values(ascending=False)
print(f"\\nCorrelações com {dep_vars[0]}:")
print(dep_corr)

# Create bar chart of correlations with dependent variable
plt.figure(figsize=(10, 6))
dep_corr.drop('{dep_vars[0]}').plot(kind='bar')
plt.title(f'Correlação com {dep_vars[0]}')
plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
plt.grid(True, alpha=0.3)
plt.tight_layout()
        """
    
    # Chi-Square test
    elif any(t in name for t in ["qui-quadrado", "chi-square", "tabela de contingência"]):
        return f"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import chi2_contingency

# Create contingency table
contingency_table = pd.crosstab(df['{dep_vars[0]}'], df['{indep_vars[0]}'])
print("Tabela de contingência:")
print(contingency_table)
result_tables.append(contingency_table)

# Calculate percentages
percentage_table = pd.crosstab(df['{dep_vars[0]}'], df['{indep_vars[0]}'], normalize='columns').round(3) * 100
print("\\nPercentagem por coluna:")
print(percentage_table)
result_tables.append(percentage_table)

# Chi-square test
chi2, p, dof, expected = chi2_contingency(contingency_table)
print(f"\\nResultados do teste Qui-quadrado:")
print(f"Estatística qui-quadrado: {chi2:.4f}")
print(f"p-valor: {p:.4f}")
print(f"Graus de liberdade: {dof}")

chi2_results = pd.DataFrame({
    'Métrica': ['Estatística qui-quadrado', 'p-valor', 'Graus de liberdade'],
    'Valor': [chi2, p, dof]
})
result_tables.append(chi2_results)

# Visualize contingency table as heatmap
plt.figure(figsize=(10, 8))
sns.heatmap(contingency_table, annot=True, fmt='d', cmap='Blues')
plt.title(f'Tabela de Contingência: {dep_vars[0]} vs {indep_vars[0]}')
plt.tight_layout()

# Create mosaic plot
plt.figure(figsize=(10, 8))
sns.heatmap(percentage_table, annot=True, fmt='.1f', cmap='YlGnBu')
plt.title(f'Percentual por coluna: {dep_vars[0]} vs {indep_vars[0]} (%)')
plt.tight_layout()
        """
    
    # Default for any other analysis
    else:
        return f"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Data exploration for {analysis["name"]}
print(f"Análise {analysis['number']}: {analysis['name']}")
print(f"Variáveis dependentes: {dep_vars}")
print(f"Variáveis independentes: {indep_vars}")

# Summary statistics
if '{dep_vars[0]}' in df.columns:
    dep_stats = df['{dep_vars[0]}'].describe()
    print("\\nEstatísticas da variável dependente:")
    print(dep_stats)

# Create descriptive plots
plt.figure(figsize=(12, 6))

if len(dep_vars) > 0 and len(indep_vars) > 0:
    if df['{dep_vars[0]}'].nunique() < 10 and df['{indep_vars[0]}'].nunique() < 10:
        # Categorical vs categorical
        contingency = pd.crosstab(df['{dep_vars[0]}'], df['{indep_vars[0]}'])
        result_tables.append(contingency)
        sns.heatmap(contingency, annot=True, fmt='d', cmap='Blues')
        plt.title(f'Tabela de Contingência: {dep_vars[0]} vs {indep_vars[0]}')
    elif pd.api.types.is_numeric_dtype(df['{dep_vars[0]}']) and df['{indep_vars[0]}'].nunique() < 10:
        # Numeric vs categorical
        plt.subplot(1, 2, 1)
        sns.boxplot(x='{indep_vars[0]}', y='{dep_vars[0]}', data=df)
        plt.title(f'Boxplot: {dep_vars[0]} por {indep_vars[0]}')
        plt.grid(True)
        
        plt.subplot(1, 2, 2)
        sns.barplot(x='{indep_vars[0]}', y='{dep_vars[0]}', data=df, ci=None)
        plt.title(f'Média de {dep_vars[0]} por {indep_vars[0]}')
        plt.grid(True)
    elif pd.api.types.is_numeric_dtype(df['{dep_vars[0]}']) and pd.api.types.is_numeric_dtype(df['{indep_vars[0]}']):
        # Numeric vs numeric
        plt.subplot(1, 2, 1)
        sns.scatterplot(x='{indep_vars[0]}', y='{dep_vars[0]}', data=df)
        plt.title(f'Scatter plot: {dep_vars[0]} vs {indep_vars[0]}')
        plt.grid(True)
        
        plt.subplot(1, 2, 2)
        sns.regplot(x='{indep_vars[0]}', y='{dep_vars[0]}', data=df)
        plt.title(f'Regressão: {dep_vars[0]} vs {indep_vars[0]}')
        plt.grid(True)
    else:
        # General case
        if pd.api.types.is_numeric_dtype(df['{dep_vars[0]}']):
            plt.subplot(1, 2, 1)
            sns.histplot(df['{dep_vars[0]}'], kde=True)
            plt.title(f'Distribuição de {dep_vars[0]}')
            plt.grid(True)
        
        if pd.api.types.is_numeric_dtype(df['{indep_vars[0]}']):
            plt.subplot(1, 2, 2)
            sns.histplot(df['{indep_vars[0]}'], kde=True)
            plt.title(f'Distribuição de {indep_vars[0]}')
            plt.grid(True)

plt.tight_layout()
        """

# Patch para plt.get_figureaddon
def patch_matplotlib():
    # Backup original figure function
    original_figure = plt.figure
    
    # Store created figures
    figures = []
    
    def custom_figure(*args, **kwargs):
        fig = original_figure(*args, **kwargs)
        figures.append(fig)
        return fig
    
    # Replace the original function
    plt.figure = custom_figure
    
    # Add method to get all figures
    def get_figureaddon():
        return figures
    
    plt.get_figureaddon = get_figureaddon

# Patch matplotlib at import time
patch_matplotlib()

# Atualizar a criação do contador de tokens
# Criar contador de tokens para Agent Executor
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
agent_token_counter = TokenCounter(model=DEFAULT_MODEL)

def generate_interpretation(text_output: str, plots: List[Dict[str, Any]], 
                           tables: List[Dict[str, Any]], analysis: Dict[str, Any]) -> str:
    """
    Gera uma interpretação dos resultados da análise usando LLM.
    """
    try:
        llm = initialize_llm()
        
        # Extrair informações úteis do texto de saída
        text_sample = text_output if text_output else "Sem saída de texto."
        
        # Contar plots e tabelas
        plot_count = len(plots)
        table_count = len(tables)
        
        table_descriptions = []
        for table in tables:
            desc = table.get("description", "")
            if desc:
                table_descriptions.append(desc)
        
        # Montar prompt para o LLM
        prompt_template = """
        Por favor, interprete os resultados da seguinte análise estatística:
        
        ### Nome da Análise
        {analysis_name}
        
        ### Variáveis Analisadas
        Dependentes: {dependent_vars}
        Independentes: {independent_vars}
        
        ### Saída da Análise
        {text_output}
        
        ### Visualizações e Tabelas
        Gráficos gerados: {plot_count}
        Tabelas geradas: {table_count}
        {table_info}
        
        Forneça uma interpretação clara e concisa dos resultados em até 1 parágrafos e com bullet points com os principais insights.
        Foque em:
        1. O que os dados mostram (padrões, correlações, diferenças significativas)
        2. O significado prático para um contexto de negócios
        3. Possíveis ações ou recomendações baseadas nos resultados
        4. Traga um paragrafo de conclusão com os principais insights de maneira clara.
        
        Traga os pontos prinipais em destaque.
        
        Sua interpretação deve ser técnica mas acessível para não-especialistas.
        """
        
        # Preparar informações de tabelas
        table_info = ""
        if table_descriptions:
            table_info = "Descrições das tabelas: " + ", ".join(table_descriptions)
        
        # Formatar o prompt com os dados da análise
        prompt = ChatPromptTemplate.from_template(prompt_template).format(
            analysis_name=analysis.get("name", ""),
            dependent_vars=", ".join(analysis.get("dependent_vars", [])),
            independent_vars=", ".join(analysis.get("independent_vars", [])),
            text_output=text_sample,
            plot_count=plot_count,
            table_count=table_count,
            table_info=table_info
        )
        
        # Chamar o LLM para gerar a interpretação
        response = llm.invoke(prompt)
        interpretation = response.content
        
        # Contar tokens
        agent_token_counter.count_prompt(str(prompt), "interpretar_resultados")
        agent_token_counter.count_completion(interpretation, "interpretar_resultados")
        
        # Registrar estatísticas depois de gerar interpretação
        logging.info(f"Estatísticas de tokens para interpretação da análise #{analysis.get('number', 'N/A')}:")
        agent_token_counter.log_summary()
        
        return interpretation
        
    except Exception as e:
        logging.error(f"Erro ao gerar interpretação: {str(e)}")
        return "Não foi possível gerar uma interpretação automática para esta análise."
