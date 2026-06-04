"""
Módulo para geração de dashboards e relatórios a partir de análises.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger("lean-six-sigma-api.dashboard")

class DashboardGenerator:
    """
    Classe responsável por gerar dashboards e relatórios a partir de análises.
    """
    
    def __init__(self):
        """Inicializa o gerador de dashboards."""
        self.style_config = {
            "colors": {
                "primary": "#0066cc",
                "secondary": "#99ccff",
                "success": "#00cc66",
                "warning": "#ffcc00",
                "error": "#ff3333",
                "background": "#ffffff",
                "text": "#333333"
            },
            "font": {
                "family": "Arial, sans-serif",
                "size": "14px"
            }
        }
    
    def generate_html_dashboard(self, analyses_results: List[Dict[str, Any]], 
                               dataset_info: Dict[str, Any],
                               metadata: Dict[str, Any]) -> str:
        """
        Gera um dashboard HTML completo a partir dos resultados de análises.
        
        Args:
            analyses_results: Lista de resultados de análises
            dataset_info: Informações sobre o dataset
            metadata: Metadados do projeto (título, data, etc)
            
        Returns:
            String HTML contendo o dashboard completo
        """
        try:
            # Iniciar HTML
            html = self._generate_html_header(metadata.get("title", "Dashboard de Análises Lean Six Sigma"))
            
            # Adicionar seção de resumo
            html += self._generate_summary_section(dataset_info, analyses_results, metadata)
            
            # Adicionar cada análise
            for i, result in enumerate(analyses_results):
                if result.get("success", False):
                    html += self._generate_analysis_section(result, i+1)
            
            # Adicionar rodapé e fechar HTML
            html += self._generate_footer(metadata)
            
            return html
        except Exception as e:
            logger.error(f"Erro ao gerar dashboard HTML: {str(e)}")
            # Retornar mensagem de erro formatada como HTML
            return f"""
            <html>
            <head><title>Erro ao Gerar Dashboard</title></head>
            <body>
                <h1>Erro ao Gerar Dashboard</h1>
                <p>Ocorreu um erro durante a geração do dashboard: {str(e)}</p>
            </body>
            </html>
            """
    
    def generate_report_markdown(self, analyses_results: List[Dict[str, Any]], 
                                dataset_info: Dict[str, Any],
                                metadata: Dict[str, Any]) -> str:
        """
        Gera um relatório em Markdown a partir dos resultados de análises.
        
        Args:
            analyses_results: Lista de resultados de análises
            dataset_info: Informações sobre o dataset
            metadata: Metadados do projeto (título, data, etc)
            
        Returns:
            String Markdown contendo o relatório completo
        """
        try:
            # Iniciar Markdown
            md = f"# {metadata.get('title', 'Relatório de Análises Lean Six Sigma')}\n\n"
            md += f"Data de geração: {metadata.get('date', datetime.now().strftime('%d/%m/%Y'))}\n\n"
            
            # Adicionar seção de resumo
            md += "## Resumo da Análise\n\n"
            md += f"- Dataset: {metadata.get('dataset_name', 'N/A')}\n"
            md += f"- Registros: {dataset_info.get('rows', 'N/A')}\n"
            md += f"- Variáveis: {dataset_info.get('columns', 'N/A')}\n\n"
            
            # Listar variáveis
            md += "### Variáveis Analisadas\n\n"
            md += "**Variáveis dependentes:**\n\n"
            for var in dataset_info.get("dependent_variables", []):
                md += f"- {var}\n"
            
            md += "\n**Variáveis independentes:**\n\n"
            for var in dataset_info.get("independent_variables", []):
                md += f"- {var}\n"
            
            # Adicionar seção de análises
            md += "\n## Análises Realizadas\n\n"
            
            # Adicionar cada análise
            for i, result in enumerate(analyses_results):
                if result.get("success", False):
                    md += f"### Análise {i+1}: {result.get('name', 'Sem nome')}\n\n"
                    md += f"{result.get('text_output', 'Sem resultados de texto.')}\n\n"
                    
                    # Mencionar tabelas
                    if result.get("tables"):
                        md += "**Tabelas geradas:**\n\n"
                        for j, table in enumerate(result.get("tables", [])):
                            md += f"- {table.get('description', f'Tabela {j+1}')}\n"
                        md += "\n"
                    
                    # Mencionar gráficos
                    if result.get("plots"):
                        md += f"**Gráficos gerados:** {len(result.get('plots', []))}\n\n"
                    
                    md += "---\n\n"
            
            return md
        except Exception as e:
            logger.error(f"Erro ao gerar relatório Markdown: {str(e)}")
            return f"# Erro ao Gerar Relatório\n\nOcorreu um erro durante a geração do relatório: {str(e)}"
    
    def _generate_html_header(self, title: str) -> str:
        """Gera o cabeçalho HTML."""