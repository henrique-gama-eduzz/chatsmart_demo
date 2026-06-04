"""
Utilitário para contagem de tokens em prompts e respostas.
"""
import tiktoken
import logging
from typing import Dict, Any, List, Optional, Union
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

logger = logging.getLogger("lean-six-sigma-api.token-counter")

# Obter o modelo padrão do arquivo .env ou usar fallback
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

def count_tokens(text: str, model: str = None) -> int:
    """
    Conta o número de tokens em um texto.
    
    Args:
        text: Texto para contar tokens
        model: Modelo de linguagem (afeta a codificação de tokens)
    
    Returns:
        Número de tokens no texto
    """
    try:
        # Verificar se o texto é None ou vazio
        if text is None or text == "":
            return 0
            
        # Verificar se é uma string
        if not isinstance(text, str):
            text = str(text)
            
        # Usar modelo do parâmetro ou o default
        model_to_use = model or DEFAULT_MODEL
        logger.info(f"Contando tokens usando modelo: {model_to_use}")
            
        # Selecione o codificador apropriado para o modelo
        if "gpt-4o-mini" in model_to_use:
            encoding = tiktoken.get_encoding("cl100k_base")  # gpt-4o-mini usa o mesmo tokenizador
        elif "gpt-4" in model_to_use:
            encoding = tiktoken.encoding_for_model("gpt-4")
        elif "gpt-3.5-turbo" in model_to_use:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        else:
            # Codificação padrão para outros modelos
            encoding = tiktoken.get_encoding("cl100k_base")
        
        # Tokenizar o texto
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        logger.warning(f"Erro ao contar tokens: {e}")
        # Estimativa aproximada de fallback (1 token ~= 4 caracteres em inglês)
        try:
            return len(text) // 4
        except:
            return 0

class TokenCounter:
    """
    Classe para monitorar e rastrear o uso de tokens.
    """
    
    def __init__(self, model: str = None):
        """
        Inicializa o contador de tokens.
        
        Args:
            model: Modelo de linguagem padrão para contagem. Se None, usa o valor do .env
        """
        self.model = model or DEFAULT_MODEL
        logger.info(f"Inicializando TokenCounter com modelo: {self.model}")
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.request_counts = 0
        self.breakdown = {}
    
    def count_prompt(self, text: str, context_name: str = "default") -> int:
        """
        Conta tokens em um prompt e registra no contexto especificado.
        
        Args:
            text: Texto do prompt
            context_name: Nome do contexto (ex: "enriquecimento", "análise", etc.)
            
        Returns:
            Número de tokens contados
        """
        token_count = count_tokens(text, self.model)
        self.total_prompt_tokens += token_count
        self.request_counts += 1
        
        # Registrar o contexto
        if context_name not in self.breakdown:
            self.breakdown[context_name] = {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}
        
        self.breakdown[context_name]["prompt_tokens"] += token_count
        self.breakdown[context_name]["requests"] += 1
        
        # Log para debug
        logger.info(f"Prompt tokens ({context_name}): {token_count}")
        
        return token_count
    
    def count_completion(self, text: str, context_name: str = "default") -> int:
        """
        Conta tokens em uma resposta e registra no contexto especificado.
        
        Args:
            text: Texto da resposta
            context_name: Nome do contexto (ex: "enriquecimento", "análise", etc.)
            
        Returns:
            Número de tokens contados
        """
        token_count = count_tokens(text, self.model)
        self.total_completion_tokens += token_count
        
        # Registrar o contexto
        if context_name not in self.breakdown:
            self.breakdown[context_name] = {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}
        
        self.breakdown[context_name]["completion_tokens"] += token_count
        
        # Log para debug
        logger.info(f"Completion tokens ({context_name}): {token_count}")
        
        return token_count
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna um resumo do uso de tokens.
        
        Returns:
            Dicionário com informações de uso de tokens
        """
        total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        
        return {
            "total_tokens": total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "requests": self.request_counts,
            "breakdown": self.breakdown,
            "estimated_cost_usd": self._estimate_cost(total_tokens)
        }
    
    def log_summary(self) -> None:
        """
        Registra um resumo do uso de tokens no log.
        """
        summary = self.get_summary()
        
        logger.info("===== Resumo de Uso de Tokens =====")
        logger.info(f"Total de Tokens: {summary['total_tokens']}")
        logger.info(f"Tokens de Prompt: {summary['prompt_tokens']}")
        logger.info(f"Tokens de Completion: {summary['completion_tokens']}")
        logger.info(f"Número de Requisições: {summary['requests']}")
        logger.info(f"Custo Estimado USD: ${summary['estimated_cost_usd']:.4f}")
        
        logger.info("Breakdown por Contexto:")
        for context, data in summary['breakdown'].items():
            logger.info(f"  {context}:")
            logger.info(f"    Prompt Tokens: {data['prompt_tokens']}")
            logger.info(f"    Completion Tokens: {data['completion_tokens']}")
            logger.info(f"    Requisições: {data['requests']}")
    
    def _estimate_cost(self, tokens: int) -> float:
        """
        Estima o custo do uso de tokens com base no modelo.
        
        Args:
            tokens: Número de tokens
            
        Returns:
            Custo estimado em USD
        """
        if "gpt-4o-mini" in self.model:
            # gpt-4o-mini: $0.0005 por 1K tokens para prompt, $0.0015 por 1K tokens para completion
            return (self.total_prompt_tokens / 1000 * 0.0005) + (self.total_completion_tokens / 1000 * 0.0015)
        elif "gpt-4-turbo" in self.model:
            # gpt-4-turbo: $0.01 por 1K tokens para prompt, $0.03 por 1K tokens para completion
            return (self.total_prompt_tokens / 1000 * 0.01) + (self.total_completion_tokens / 1000 * 0.03)
        elif "gpt-4" in self.model:
            # gpt-4: $0.03 por 1K tokens para prompt, $0.06 por 1K tokens para completion
            return (self.total_prompt_tokens / 1000 * 0.03) + (self.total_completion_tokens / 1000 * 0.06)
        elif "gpt-3.5-turbo" in self.model:
            # gpt-3.5-turbo: $0.0005 por 1K tokens para prompt, $0.0015 por 1K tokens para completion
            return (self.total_prompt_tokens / 1000 * 0.0005) + (self.total_completion_tokens / 1000 * 0.0015)
        else:
            # Taxa genérica
            return tokens / 1000 * 0.02
