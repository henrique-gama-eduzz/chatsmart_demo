# ChatSmart

![Lean Six Sigma](https://img.shields.io/badge/Lean_Six_Sigma-Analysis-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B)

O ChatSmart é uma plataforma que combina IA avançada com metodologias Lean Six Sigma para identificar causas raiz e oportunidades de melhoria em processos industriais e de serviços. A aplicação permite carregar conjuntos de dados, definir variáveis dependentes e independentes, e receber recomendações de análises estatísticas personalizadas.

## Recursos Principais

- Upload de arquivos CSV ou Excel
- Seleção intuitiva de variáveis dependentes e independentes
- Recomendações de análise geradas por IA
- Visualizações interativas e resultados estatísticos
- Dashboard de resultados

## Instalação

### Pré-requisitos

- Python 3.9+ 
- Pip (gerenciador de pacotes Python)

### Configuração do Ambiente

1. Clone o repositório e navegue para a pasta do projeto:
```bash
git clone https://github.com/yourusername/lean-six-sigma-recommender.git
cd lean-six-sigma-recommender
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
# No Windows
venv\Scripts\activate
# No macOS/Linux
source venv/bin/activate
```

3. Instale os pacotes necessários:
```bash
pip install -r requirements.txt
```

4. Configure suas credenciais da API Azure OpenAI como variáveis de ambiente:
```bash
# No Windows
set AZURE_OPENAI_API_KEY=your_api_key_here
set AZURE_OPENAI_ENDPOINT=your_endpoint_here

# No macOS/Linux
export AZURE_OPENAI_API_KEY=your_api_key_here
export AZURE_OPENAI_ENDPOINT=your_endpoint_here
```

5. Execute a aplicação:
```bash
streamlit run app.py
```

