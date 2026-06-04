"""
Agente de execução de código usando LangChain e LangGraph.
Este agente gera código Python, executa e corrige automaticamente com base em erros.
"""
import asyncio
import logging
import sys
from io import StringIO
from typing import Dict, Any, List, Optional
import traceback
import pandas as pd
import numpy as np
from contextlib import redirect_stdout, redirect_stderr

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from api.services.data_service import get_dataset

from api.config import settings

logger = logging.getLogger(__name__)

class CodeExecutionState(BaseModel):
    """Estado do agente de execução de código."""
    rule_text: str
    columns: List[str]
    upload_id: str
    generated_code: Optional[str] = None
    execution_output: Optional[str] = None
    execution_error: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    success: bool = False
    final_result: Optional[Dict[str, Any]] = None

class CodeExecutionAgent:
    """Agente para geração e execução de código com correção automática."""
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.DEPLOYMENT_NAME,
            api_key=settings.AZURE_KEY,
            temperature=0.1,
        )
        self.graph = self._build_graph()
    def _build_graph(self):
        """Constrói o grafo de estados do LangGraph."""
        
        # Definir o grafo usando dicionário em vez de modelo Pydantic
        workflow = StateGraph(dict)
        
        # Adicionar nós
        workflow.add_node("generate_code", self._generate_code_node)
        workflow.add_node("execute_code", self._execute_code_node)
        workflow.add_node("fix_code", self._fix_code_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Definir ponto de entrada
        workflow.set_entry_point("generate_code")
        
        # Adicionar arestas condicionais
        workflow.add_conditional_edges(
            "generate_code",
            self._should_execute,
            {
                "execute": "execute_code",
                "error": "finalize"
            }
        )
        
        workflow.add_conditional_edges(
            "execute_code",
            self._handle_execution_result,
            {
                "success": "finalize",
                "retry": "fix_code",
                "max_attempts": "finalize"
            }
        )
        
        workflow.add_conditional_edges(
            "fix_code",
            self._should_retry,
            {
                "retry": "execute_code",
                "max_attempts": "finalize"
            }        )
        
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    async def process_rule(self, rule_text: str, columns: List[str], upload_id: str) -> Dict[str, Any]:
        """Processa uma regra em linguagem natural."""
        
        initial_state = {
            "rule_text": rule_text,
            "columns": columns,
            "upload_id": upload_id,
            "generated_code": None,
            "execution_output": None,
            "execution_error": None,
            "attempt_count": 0,
            "max_attempts": 3,
            "success": False,
            "final_result": None
        }
        
        try:
            # Executar o grafo
            result = await self.graph.ainvoke(initial_state)
            
            return {
                "success": result.get("success", False),
                "generated_code": result.get("generated_code"),
                "execution_output": result.get("execution_output"),
                "execution_error": result.get("execution_error"),
                "attempt_count": result.get("attempt_count", 0),
                "final_result": result.get("final_result")
            }
            
        except Exception as e:
            logger.error(f"Erro no agente de execução: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "generated_code": None,
                "execution_output": None,
                "execution_error": str(e),
                "attempt_count": 0,
                "final_result": None
            }
    
    async def _generate_code_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Nó para gerar código Python."""
        try:
            prompt = self._create_code_generation_prompt(state)
            
            messages = [
                SystemMessage(content="Você é um especialista em Python e pandas. Gere código limpo e seguro."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            generated_code = self._extract_python_code(response.content)
            
            state["generated_code"] = generated_code
            logger.info(f"Código gerado: {generated_code[:100]}...")
            
            return state
            
        except Exception as e:
            logger.error(f"Erro ao gerar código: {str(e)}")
            state["execution_error"] = f"Erro na geração de código: {str(e)}"
            return state
    
    async def _execute_code_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Nó para executar o código gerado."""
        state["attempt_count"] += 1
        
        try:
            # Carregar dataset
            df = self._load_dataset(state["upload_id"])
            
            # Preparar ambiente de execução
            execution_env = {
                'df': df.copy(),
                'pd': pd,
                'np': np,
                '__builtins__': {
                    '__import__': __import__,  # Permitir importações
                    'print': print,
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float,
                    'list': list,
                    'dict': dict,
                    'range': range,
                    'enumerate': enumerate,
                    'zip': zip,
                    'sum': sum,
                    'max': max,
                    'min': min,
                    'abs': abs,
                    'round': round,
                    'sorted': sorted,
                    'any': any,
                    'all': all,
                    'type': type,
                    'isinstance': isinstance,
                    'getattr': getattr,
                    'hasattr': hasattr,
                    'setattr': setattr,
                }
            }
            
            # Capturar stdout e stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(state["generated_code"], execution_env)
            
            # Obter DataFrame original para comparação
            original_df = get_dataset(state["upload_id"])
            
            # Obter DataFrame resultante
            result_df = execution_env['df']

            # Não salvar aqui diretamente - usamos a função de serviço abaixo
            # para garantir que o original seja substituído corretamente
            
            state["execution_output"] = stdout_capture.getvalue()
            state["success"] = True
            state["final_result"] = {
                "preview": result_df.head(10).to_dict(orient="records"),
                "rows": len(result_df),
                "columns": result_df.columns.tolist(),
            }
            
            # Salvar os dados tratados substituindo os originais (sem manter backup)
            from api.services.data_service import save_treated_dataset
            save_success = save_treated_dataset(state["upload_id"], result_df, keep_backup=False)
            if save_success:
                logger.info(f"Dados tratados salvos com sucesso para upload_id: {state['upload_id']}")
            else:
                logger.warning(f"Falha ao salvar dados tratados para upload_id: {state['upload_id']}")
            
            logger.info(f"Código executado com sucesso na tentativa {state['attempt_count']}")
            
        except Exception as e:
            error_msg = f"Erro na execução (tentativa {state['attempt_count']}): {str(e)}\n{traceback.format_exc()}"
            state["execution_error"] = error_msg
            state["success"] = False
            logger.error(error_msg)
        
        return state
    
    async def _fix_code_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Nó para corrigir código com base no erro."""
        try:
            prompt = self._create_code_fix_prompt(state)
            
            messages = [
                SystemMessage(content="Você é um especialista em debugging Python. Corrija o código com base no erro."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            corrected_code = self._extract_python_code(response.content)
            
            state["generated_code"] = corrected_code
            logger.info(f"Código corrigido na tentativa {state['attempt_count']}")
            
        except Exception as e:
            logger.error(f"Erro ao corrigir código: {str(e)}")
            state["execution_error"] = f"Erro na correção de código: {str(e)}"
        
        return state
    
    async def _finalize_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Nó final para processar resultado."""
        if not state["success"] and state["attempt_count"] >= state["max_attempts"]:
            state["execution_error"] = f"Falha após {state['max_attempts']} tentativas. Último erro: {state.get('execution_error', 'Erro desconhecido')}"
        
        return state
    
    def _should_execute(self, state: Dict[str, Any]) -> str:
        """Determina se deve executar o código."""
        return "execute" if state.get("generated_code") else "error"
    
    def _handle_execution_result(self, state: Dict[str, Any]) -> str:
        """Determina próximo passo após execução."""
        if state.get("success"):
            return "success"
        elif state["attempt_count"] >= state["max_attempts"]:
            return "max_attempts"
        else:
            return "retry"
    
    def _should_retry(self, state: Dict[str, Any]) -> str:
        """Determina se deve tentar novamente."""
        return "retry" if state["attempt_count"] < state["max_attempts"] else "max_attempts"
    
    def _create_code_generation_prompt(self, state: Dict[str, Any]) -> str:
        """Cria prompt para geração de código."""
        return f"""
Crie código Python usando pandas para aplicar a seguinte regra em um DataFrame:
"{state['rule_text']}"

O DataFrame está na variável 'df' e tem as seguintes colunas:
{', '.join(state['columns'])}

INSTRUÇÕES IMPORTANTES:
1. Retorne APENAS o código Python, sem explicações
2. NÃO inclua imports - pandas está disponível como 'pd' e numpy como 'np'
3. Use apenas operações seguras do pandas
4. Não use funções que podem ser perigosas (eval, exec, import, etc.)
5. O DataFrame modificado deve permanecer na variável 'df'
6. Trate possíveis erros (valores nulos, tipos incorretos, etc.)
7. Para criar novas colunas, use df['nova_coluna'] = valores
8. Para operações condicionais, use np.where ou df.loc
9. Para categorização, use pd.cut ou condições customizadas

EXEMPLOS DE OPERAÇÕES COMUNS:

Criar coluna baseada em condição:
```python
df['faixa_etaria'] = df['idade'].apply(lambda x: 'Jovem' if x < 30 else 'Adulto' if x < 60 else 'Idoso')
```

Criar coluna numérica baseada em cálculo:
```python
df['imc'] = df['peso'] / (df['altura'] ** 2)
```

Criar coluna categórica com base em faixas:
```python
df['categoria_salario'] = pd.cut(df['salario'], bins=[0, 3000, 6000, float('inf')], labels=['Baixo', 'Médio', 'Alto'])
```

Criar coluna com operações matemáticas:
```python
df['total'] = df['quantidade'] * df['preco']
```

Formato de resposta esperado:
```python
# Aplicar a regra (SEM IMPORTS)
[seu código aqui]
```
"""
    
    def _create_code_fix_prompt(self, state: Dict[str, Any]) -> str:
        """Cria prompt para correção de código."""
        return f"""
O código Python abaixo gerou um erro. Corrija o código com base no erro:

CÓDIGO ORIGINAL:
```python
{state['generated_code']}
```

ERRO ENCONTRADO:
{state['execution_error']}

REGRA ORIGINAL:
"{state['rule_text']}"

COLUNAS DISPONÍVEIS:
{', '.join(state['columns'])}

Forneça o código corrigido que resolve o erro. Retorne APENAS o código Python corrigido:
"""
    
    def _extract_python_code(self, text: str) -> str:
        """Extrai código Python de uma resposta e remove imports desnecessários."""
        # Remover markdown code blocks
        if "```python" in text:
            start = text.find("```python") + 9
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        
        # Filtrar linhas do código
        lines = text.split('\n')
        code_lines = []
        for line in lines:
            line = line.strip()
            # Pular linhas vazias e imports
            if not line or line.startswith('#'):
                continue
            if line.startswith('import ') or line.startswith('from '):
                continue  # Pular imports
            code_lines.append(line)
        
        return '\n'.join(code_lines)
    def _load_dataset(self, upload_id: str) -> pd.DataFrame:
        """Carrega dataset do arquivo."""
        try:
            # Primeiro tentar carregar do serviço
            from api.services.data_service import get_dataset
            return get_dataset(upload_id)
        except Exception as e:
            logger.error(f"Erro ao carregar dataset {upload_id}: {str(e)}")
            raise Exception(f"Dataset não encontrado ou erro no carregamento: {str(e)}")

# Instância global do agente
code_execution_agent = CodeExecutionAgent()
