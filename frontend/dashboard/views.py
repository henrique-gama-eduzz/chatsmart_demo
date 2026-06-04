import json
import time
import requests
import pandas as pd
import io
import base64
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib import messages
from django.views import View
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models  # For Q objects
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import Dataset, Analysis, Project
from .forms import (DatasetUploadForm, VariableSelectionForm, ColumnDescriptionForm, 
                   AnalysisEditForm, ExecuteAnalysisForm, ProjectForm)

# Logger para operações de dashboard
logger = logging.getLogger("dashboard-view")
from .utils import (upload_file, get_dataset_preview, request_recommendations, 
                   execute_analysis, execute_all_analyses, get_analyses_status,
                   extract_analysis_context, generate_html_report, generate_docx_report, 
                   get_ai_comparison_insights, get_treated_dataset_preview)

# Import DatabaseConnection model
from accounts.models import DatabaseConnection

# API URL from settings
API_URL = settings.API_URL

def check_api_status(request):
    """API status check endpoint"""
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            return JsonResponse({"status": "connected"})
        else:
            return JsonResponse({"status": "error", "message": "Serviço indisponível"})
    except:
        return JsonResponse({"status": "error", "message": "Serviço indisponível"})

class HomeView(LoginRequiredMixin, View):
    def get(self, request):
        # Verificar status da API
        try:
            response = requests.get(f"{API_URL}/health")
            api_connected = response.status_code == 200
        except:
            api_connected = False
            
        # Get user's projects with comprehensive error handling
        recent_projects = []
        try:
            # Check database connection and migration status
            from django.db import connection
            from django.db.utils import OperationalError, ProgrammingError
            
            try:
                # Use database-agnostic table check
                table_exists = False
                with connection.cursor() as cursor:
                    if connection.vendor == 'sqlite':
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_project'")
                        table_exists = cursor.fetchone() is not None
                    elif connection.vendor == 'postgresql':
                        cursor.execute("SELECT to_regclass('dashboard_project')")
                        table_exists = cursor.fetchone()[0] is not None
                    else:
                        # Generic approach for other databases
                        cursor.execute("""
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_name = 'dashboard_project'
                        """)
                        table_exists = cursor.fetchone()[0] > 0
                
                if table_exists:
                    # Table exists, try to get projects
                    recent_projects = Project.objects.filter(owner=request.user).order_by('-updated_at')[:5]
                else:
                    # Table doesn't exist, we need migrations
                    messages.warning(
                        request, 
                        "O banco de dados precisa ser inicializado. "
                        "Por favor, execute 'python manage.py migrate' no terminal."
                    )
                    print("Project table not found. Run migrations first.")
            except (OperationalError, ProgrammingError) as db_error:
                # Database error, migrations needed
                messages.warning(
                    request,
                    "Configuração do banco de dados necessária. "
                    "Por favor, execute 'python manage.py migrate'."
                )
                print(f"Database error: {str(db_error)}")
                
        except Exception as e:
            # Handle unexpected errors
            print(f"Error when initializing projects: {str(e)}")
            messages.error(request, "Erro ao acessar projetos. Por favor, contate o administrador.")
        
        context = {
            'api_connected': api_connected,
            'recent_projects': recent_projects,
        }
        return render(request, 'dashboard/home.html', context)

# Project Views
class ProjectListView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            # Use database-agnostic table check
            from django.db import connection
            from django.db.utils import OperationalError, ProgrammingError
            
            table_exists = False
            try:
                with connection.cursor() as cursor:
                    if connection.vendor == 'sqlite':
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_project'")
                        table_exists = cursor.fetchone() is not None
                    elif connection.vendor == 'postgresql':
                        cursor.execute("SELECT to_regclass('dashboard_project')")
                        table_exists = cursor.fetchone()[0] is not None
                    else:
                        # Generic approach for other databases
                        cursor.execute("""
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_name = 'dashboard_project'
                        """)
                        table_exists = cursor.fetchone()[0] > 0
                        
                if not table_exists:
                    messages.error(
                        request, 
                        "O banco de dados precisa ser inicializado. "
                        "Por favor, execute 'python manage.py migrate' no terminal."
                    )
                    return redirect('home')
            except (OperationalError, ProgrammingError) as db_error:
                messages.error(request, f"Erro de banco de dados: {str(db_error)}")
                return redirect('home')
                
            projects = Project.objects.filter(owner=request.user).order_by('-updated_at')
            context = {
                'projects': projects,
                'form': ProjectForm()
            }
            return render(request, 'dashboard/projects/list.html', context)
        except Exception as e:
            messages.error(request, f"Erro inesperado: {str(e)}")
            return redirect('home')
    
    def post(self, request):
        form = ProjectForm(request.POST)
        if form.is_valid():
            # Create new project
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            
            # Set newly created project as current project in session
            request.session['current_project_id'] = str(project.id)
            request.session['current_project_name'] = project.name
            
            messages.success(request, f"Projeto '{project.name}' criado com sucesso!")
            return redirect('project_detail', project_id=project.id)
        
        projects = Project.objects.filter(owner=request.user).order_by('-updated_at')
        context = {
            'projects': projects,
            'form': form
        }
        return render(request, 'dashboard/projects/list.html', context)

class ProjectCreateView(LoginRequiredMixin, View):
    def get(self, request):
        form = ProjectForm()
        return render(request, 'dashboard/projects/create.html', {'form': form})
        
    def post(self, request):
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            
            # Set newly created project as current project in session
            request.session['current_project_id'] = str(project.id)
            request.session['current_project_name'] = project.name
            
            messages.success(request, "Projeto criado com sucesso!")
            return redirect('project_detail', project_id=project.id)
        return render(request, 'dashboard/projects/create.html', {'form': form})

class ProjectDetailView(LoginRequiredMixin, View):
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        datasets = Dataset.objects.filter(project=project).order_by('-uploaded_at')
        
        # Set current project in session
        request.session['current_project_id'] = str(project.id)
        request.session['current_project_name'] = project.name
        
        context = {
            'project': project,
            'datasets': datasets,
            'upload_form': DatasetUploadForm(user=request.user, initial={'project': project})
        }
        return render(request, 'dashboard/projects/detail.html', context)

class ProjectEditView(LoginRequiredMixin, View):
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        form = ProjectForm(instance=project)
        
        context = {
            'form': form,
            'project': project
        }
        return render(request, 'dashboard/projects/edit.html', context)
    
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        form = ProjectForm(request.POST, instance=project)
        
        if form.is_valid():
            form.save()
            messages.success(request, f"Projeto '{project.name}' atualizado com sucesso!")
            return redirect('project_detail', project_id=project.id)
        
        context = {
            'form': form,
            'project': project
        }
        return render(request, 'dashboard/projects/edit.html', context)

class ProjectDeleteView(LoginRequiredMixin, View):
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        name = project.name
        
        # Obter todos os datasets associados ao projeto
        datasets = Dataset.objects.filter(project=project)
        
        # Excluir arquivos físicos relacionados a cada dataset
        # Obtém o diretório atual
        import os
        diretorio_atual = os.getcwd()
        print(f"Você está no diretório: {diretorio_atual}")
        from api.config import settings
        
        import shutil
        
        total_files_deleted = 0
        total_bytes_freed = 0
        
        for dataset in datasets:
            try:
                files_deleted = 0
                bytes_freed = 0
                
                # Arquivo principal do dataset
                file_path = os.path.join(settings.UPLOAD_DIR, f"{dataset.upload_id}.pkl")
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    files_deleted += 1
                    bytes_freed += file_size
                    
                # Possível arquivo de backup
                backup_path = os.path.join(settings.UPLOAD_DIR, f"{dataset.upload_id}_backup.pkl")
                if os.path.exists(backup_path):
                    file_size = os.path.getsize(backup_path)
                    os.remove(backup_path)
                    files_deleted += 1
                    bytes_freed += file_size
                    
                # Arquivo de upload original (se existir)
                if dataset.file and os.path.exists(dataset.file.path):
                    file_size = os.path.getsize(dataset.file.path)
                    dataset.file.delete(save=False)
                    files_deleted += 1
                    bytes_freed += file_size
                
                total_files_deleted += files_deleted
                total_bytes_freed += bytes_freed
                
                logger.info(f"Arquivos do dataset {dataset.upload_id} excluídos: {files_deleted} arquivos, {bytes_freed / (1024*1024):.2f} MB")
            except Exception as e:
                logger.error(f"Erro ao excluir arquivos do dataset {dataset.upload_id}: {str(e)}")
        
        # Excluir o projeto (isso excluirá automaticamente os datasets e análises associados devido ao CASCADE)
        project.delete()
        
        # Formatar mensagem com detalhes sobre arquivos excluídos
        if total_files_deleted > 0:
            space_freed_mb = total_bytes_freed / (1024*1024)
            messages.success(
                request, 
                f"Projeto '{name}' excluído com sucesso! {total_files_deleted} arquivos removidos ({space_freed_mb:.2f} MB liberados)."
            )
        else:
            messages.success(request, f"Projeto '{name}' excluído com sucesso!")
            
        logger.info(f"Projeto {project_id} excluído. Total: {total_files_deleted} arquivos, {total_bytes_freed / (1024*1024):.2f} MB")
        return redirect('project_list')

@login_required
def set_current_project(request, project_id):
    """Set a project as the current active project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    
    # Set as current project in session
    request.session['current_project_id'] = str(project.id)
    request.session['current_project_name'] = project.name
    
    messages.success(request, f"Projeto '{project.name}' definido como projeto atual.")
    
    # Redirect back to referring page or project list
    next_page = request.GET.get('next', 'project_list')
    return redirect(next_page)

class DataUploadView(LoginRequiredMixin, View):
    def get(self, request):
        form = DatasetUploadForm(user=request.user)
        
        # Get project_id from query params if present
        project_id = request.GET.get('project')
        if project_id:
            try:
                project = Project.objects.get(id=project_id, owner=request.user)
                form = DatasetUploadForm(user=request.user, initial={'project': project})
            except Project.DoesNotExist:
                pass
        
        # Get database connections for the database tab
        connections = DatabaseConnection.objects.filter(user=request.user).order_by('-created_at')

        # Check API connection
        api_connected = True
        try:
            response = requests.get(f"{settings.API_URL}/health", timeout=2)
            if response.status_code != 200:
                api_connected = False
        except:
            api_connected = False
        
        context = {
            'form': form,
            'api_connected': api_connected,
            'connections': connections
        }
        return render(request, 'dashboard/upload.html', context)
    
    def post(self, request):
        form = DatasetUploadForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            # Processar upload do arquivo
            uploaded_file = request.FILES['file']
            
            # Enviar para API
            try:
                api_response = upload_file(uploaded_file)
                
                if api_response.get("success", False):
                    # Salvar dataset no banco de dados
                    dataset = form.save(commit=False)
                    dataset.upload_id = api_response.get("upload_id")
                    dataset.name = uploaded_file.name
                    dataset.columns = api_response.get("columns", [])
                    dataset.original_columns = api_response.get("columns", [])  # Salvar colunas originais
                    dataset.rows = api_response.get("rows", 0)
                    dataset.save()
                    
                    # Store project in session
                    request.session['current_project_id'] = str(dataset.project.id)
                    
                    # Armazenar visualização na sessão
                    request.session['df_preview'] = api_response.get("preview", [])
                    request.session['upload_id'] = str(dataset.upload_id)
                    request.session['columns'] = dataset.columns
                    
                    messages.success(request, f"Arquivo '{uploaded_file.name}' carregado com sucesso!")
                    return redirect('define_variables', upload_id=dataset.upload_id)
                else:
                    messages.error(request, f"Erro ao carregar arquivo: {api_response.get('message')}")
            except Exception as e:
                messages.error(request, f"Erro ao processar arquivo: {str(e)}")
        
        context = {
            'form': form,
        }
        return render(request, 'dashboard/upload.html', context)

def upload_view(request):
    if request.method == 'POST':
        form = DatasetUploadForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            # Processar upload do arquivo
            uploaded_file = request.FILES['file']
            
            # Enviar para API
            try:
                api_response = upload_file(uploaded_file)
                
                if api_response.get("success", False):
                    # Salvar dataset no banco de dados
                    dataset = form.save(commit=False)
                    dataset.upload_id = api_response.get("upload_id")
                    dataset.name = uploaded_file.name
                    dataset.columns = api_response.get("columns", [])
                    dataset.rows = api_response.get("rows", 0)
                    dataset.save()
                    
                    # Store project in session
                    request.session['current_project_id'] = str(dataset.project.id)
                    
                    # Armazenar visualização na sessão
                    request.session['df_preview'] = api_response.get("preview", [])
                    request.session['upload_id'] = str(dataset.upload_id)
                    request.session['columns'] = dataset.columns
                    
                    messages.success(request, f"Arquivo '{uploaded_file.name}' carregado com sucesso!")
                    return redirect('define_variables', upload_id=dataset.upload_id)
                else:
                    messages.error(request, f"Erro ao carregar arquivo: {api_response.get('message')}")
            except Exception as e:
                messages.error(request, f"Erro ao processar arquivo: {str(e)}")
    else:
        form = DatasetUploadForm(request.user)
    
    # Get database connections for the database tab
    connections = DatabaseConnection.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'dashboard/upload.html', {
        'form': form,
        'connections': connections
    })

class DefineVariablesView(LoginRequiredMixin, View):
    def get(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        
        # Verificar se foi solicitada atualização forçada
        force_refresh = request.GET.get('refresh') == '1'
        
        # Verificar se as colunas do dataset estão atualizadas
        try:
            from .utils import get_treated_dataset_preview
            current_data = get_treated_dataset_preview(str(upload_id))
            
            if current_data.get('success'):
                current_columns = current_data.get('columns', dataset.columns)               
                
            else:
                if force_refresh:
                    messages.warning(request, "Não foi possível atualizar as colunas. Verifique se o dataset está disponível.")
        except Exception as e:
            print(f"Erro ao verificar colunas atuais: {str(e)}")
            # Em caso de erro, tentar recarregar da API de dados
            try:
                from .utils import get_dataset_preview
                fallback_data = get_dataset_preview(str(upload_id))
                if fallback_data.get('success'):
                    current_columns = fallback_data.get('columns', dataset.columns)
                    if set(current_columns) != set(dataset.columns):
                        dataset.columns = current_columns
                        dataset.save()
                        messages.info(request, "Colunas do dataset atualizadas (via fallback).")
            except Exception as e2:
                print(f"Erro no fallback: {str(e2)}")
                if force_refresh:
                    messages.error(request, "Erro ao tentar atualizar as colunas. Tente novamente mais tarde.")
        
        # Initialize form with saved objective if available
        initial_data = {}
        if dataset.analysis_objective:
            initial_data['analysis_objective'] = dataset.analysis_objective
            
        variable_form = VariableSelectionForm(columns=dataset.columns, initial=initial_data)
        
        # Iniciar formulário de descrições de colunas
        description_form = ColumnDescriptionForm(columns=dataset.columns)
        
        # Obter descrições existentes
        column_descriptions = dataset.column_descriptions or {}
        
        # Preencher valores iniciais para descrições
        initial_descriptions = {}
        for column in dataset.columns:
            field_name = f'desc_{column}'
            initial_descriptions[field_name] = column_descriptions.get(column, '')
        
        if initial_descriptions:
            description_form = ColumnDescriptionForm(columns=dataset.columns, initial=initial_descriptions)
        
        # Obter preview atualizado da API
        preview = []
        try:
            from .utils import get_treated_dataset_preview
            preview_response = get_treated_dataset_preview(upload_id)
            
            if preview_response.get('success'):
                preview = preview_response.get('preview', [])
                # Preview já foi obtido durante a verificação de colunas
            else:
                # Fallback para preview da sessão se houver erro na API
                preview = request.session.get('df_preview', [])
                print(f"DEBUG - Usando preview da sessão (fallback)")
        except Exception as e:
            # Fallback para preview da sessão se houver erro na API
            preview = request.session.get('df_preview', [])
            print(f"DEBUG - Erro ao obter preview: {str(e)}")
        
        context = {
            'dataset': dataset,
            'variable_form': variable_form,
            'description_form': description_form,
            'preview': preview,
        }
        return render(request, 'dashboard/define_variables.html', context)
    
    def post(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        
        variable_form = VariableSelectionForm(dataset.columns, request.POST)
        description_form = ColumnDescriptionForm(dataset.columns, request.POST)
        
        if variable_form.is_valid() and description_form.is_valid():
            # Extrair descrições de colunas
            column_descriptions = {}
            for column in dataset.columns:
                desc = description_form.cleaned_data.get(f'desc_{column}')
                if desc:
                    column_descriptions[column] = desc
            
            # Atualizar descrições no dataset
            dataset.column_descriptions = column_descriptions
            
            # Save the analysis objective to the dataset
            dataset.analysis_objective = variable_form.cleaned_data['analysis_objective']
            dataset.save()
            
            # Obter dados do formulário
            dependent_vars = variable_form.cleaned_data['dependent_vars']
            independent_vars = variable_form.cleaned_data['independent_vars']
            objective = variable_form.cleaned_data['analysis_objective']
            
            # Solicitar recomendações da API
            try:
                result = request_recommendations(
                    str(dataset.upload_id),
                    dependent_vars,
                    independent_vars,
                    column_descriptions,
                    objective
                )
                
                if result.get("success", False):
                    # Remover análises existentes para este dataset para evitar duplicatas
                    Analysis.objects.filter(dataset=dataset).delete()
                    
                    # Salvar análises no banco de dados
                    analyses = result.get("analyses", [])
                    for analysis_data in analyses:
                        Analysis.objects.create(
                            dataset=dataset,
                            number=analysis_data.get('number'),
                            name=analysis_data.get('name'),
                            dependent_vars=analysis_data.get('dependent_vars', []),
                            independent_vars=analysis_data.get('independent_vars', []),
                            content=analysis_data.get('content', ''),
                            status='pending'
                        )
                    
                    messages.success(request, f"Recomendações geradas com sucesso em {result.get('processing_time', 0):.2f} segundos.")
                    return redirect('recommendations', upload_id=dataset.upload_id)
                else:
                    messages.error(request, f"Erro ao gerar recomendações: {result.get('message')}")
            except Exception as e:
                messages.error(request, f"Erro ao processar recomendações: {str(e)}")
        
        context = {
            'dataset': dataset,
            'variable_form': variable_form,
            'description_form': description_form,
            'preview': request.session.get('df_preview', []),
        }
        return render(request, 'dashboard/define_variables.html', context)

class RecommendationsView(LoginRequiredMixin, View):
    def get(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id, project__owner=request.user)
        
        # Atualizar contexto da sessão
        request.session['current_project_id'] = str(dataset.project.id)
        request.session['current_project_name'] = dataset.project.name
        
        analyses = Analysis.objects.filter(dataset=dataset)
        
        # Verificar se foi solicitada atualização forçada
        force_refresh = request.GET.get('refresh') == '1'
        
        # Sempre verificar se as colunas do dataset estão atualizadas
        try:
            from .utils import get_treated_dataset_preview
            current_data = get_treated_dataset_preview(str(upload_id))
            
            if current_data.get('success'):
                current_columns = current_data.get('columns', dataset.columns)
                
                # Atualizar colunas se diferentes ou se forçado
                if force_refresh or set(current_columns) != set(dataset.columns):
                    old_columns = dataset.columns.copy()
                    dataset.columns = current_columns
                    dataset.save()
                    
                    # Identificar colunas criadas e removidas
                    created = list(set(current_columns) - set(old_columns))
                    removed = list(set(old_columns) - set(current_columns))
                    
                    change_messages = []
                    if created:
                        change_messages.append(f"Colunas criadas: {', '.join(created)}")
                    if removed:
                        change_messages.append(f"Colunas removidas: {', '.join(removed)}")
                    
                    if change_messages:
                        messages.success(request, f"Dataset atualizado! {' | '.join(change_messages)}")
                    elif force_refresh:
                        messages.success(request, "Lista de colunas atualizada com sucesso!")
                    else:
                        messages.info(request, "Colunas do dataset atualizadas.")
                else:
                    if force_refresh:
                        messages.info(request, "As colunas já estão atualizadas.")
            else:
                if force_refresh:
                    messages.warning(request, "Não foi possível atualizar as colunas. Verifique se o dataset está disponível.")
        except Exception as e:
            print(f"Erro ao verificar colunas atuais na página de recomendações: {str(e)}")
            if force_refresh:
                messages.error(request, "Erro ao tentar atualizar as colunas. Tente novamente mais tarde.")
        
        # Obter as colunas diretamente da API para garantir que estamos usando dados atualizados
        try:
            updated_data = get_treated_dataset_preview(str(upload_id))
            if updated_data.get('success'):
                # Usar as colunas retornadas pela API diretamente no contexto
                current_columns = updated_data.get('columns', [])
                dataset.columns = current_columns  # Atualiza localmente (não persiste no banco ainda)
        except Exception as e:
            print(f"Erro ao obter colunas atualizadas do dataset: {str(e)}")
        
        context = {
            'dataset': dataset,
            'analyses': analyses,
        }
        return render(request, 'dashboard/recommendations.html', context)
    
    def post(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id, project__owner=request.user)
        
        # Atualizar contexto da sessão
        request.session['current_project_id'] = str(dataset.project.id)
        request.session['current_project_name'] = dataset.project.name
        
        # Obter as colunas atualizadas do dataset diretamente da API
        try:
            from .utils import get_treated_dataset_preview
            updated_data = get_treated_dataset_preview(str(upload_id))
            if updated_data.get('success'):
                current_columns = updated_data.get('columns', dataset.columns)
                
                # Atualizar o objeto do dataset somente se as colunas forem diferentes
                if set(current_columns) != set(dataset.columns):
                    dataset.columns = current_columns
                    dataset.save()
            else:
                messages.warning(request, "Não foi possível obter as colunas atualizadas do dataset.")
        except Exception as e:
            print(f"Erro ao atualizar colunas do dataset: {str(e)}")
            messages.warning(request, "Erro ao tentar atualizar as colunas do dataset.")
        
        # Tratar envio do formulário para editar análises
        if 'save_all_edits' in request.POST:
            for analysis in Analysis.objects.filter(dataset=dataset):
                # Processar edições para cada análise
                if f'name_{analysis.number}' in request.POST:
                    analysis.name = request.POST.get(f'name_{analysis.number}')
                
                # Obter variáveis dependentes e independentes
                dep_vars = request.POST.getlist(f'dep_{analysis.number}')
                indep_vars = request.POST.getlist(f'indep_{analysis.number}')
                
                # Validar que variáveis existem nas colunas atuais do dataset
                valid_dep_vars = [var for var in dep_vars if var in dataset.columns]
                valid_indep_vars = [var for var in indep_vars if var in dataset.columns]
                
                # Verificar se alguma variável foi descartada por não existir mais
                if len(valid_dep_vars) != len(dep_vars) or len(valid_indep_vars) != len(indep_vars):
                    messages.warning(
                        request,
                        f"Algumas variáveis selecionadas para a análise '{analysis.name}' não existem mais no dataset e foram removidas."
                    )
                
                # Salvar variáveis válidas
                if valid_dep_vars and valid_indep_vars:
                    analysis.dependent_vars = valid_dep_vars
                    analysis.independent_vars = valid_indep_vars
                elif not valid_dep_vars:
                    messages.error(request, f"Nenhuma variável dependente válida para a análise '{analysis.name}'.")
                elif not valid_indep_vars:
                    messages.error(request, f"Nenhuma variável independente válida para a análise '{analysis.name}'.")
                
                # Atualizar conteúdo preservando estrutura
                if f'content_{analysis.number}' in request.POST:
                    new_content = request.POST.get(f'content_{analysis.number}')
                    full_content = analysis.content
                    
                    # Atualizar seção de contexto
                    if "Contexto de Aplicação:" in full_content:
                        import re
                        full_content = re.sub(
                            r'(Contexto de Aplicação:).*?((?=\n\n\*\*Variáveis|\Z))', 
                            f'\\1 {new_content}\\2', 
                            full_content, 
                            flags=re.DOTALL
                        )
                    else:
                        full_content = new_content
                    
                    analysis.content = full_content
                
                analysis.save()
            
            messages.success(request, "Todas as alterações foram salvas com sucesso!")
        
        # Tratar remoção de análise
        if 'remove_analysis' in request.POST:
            analysis_id = request.POST.get('remove_analysis')
            Analysis.objects.filter(id=analysis_id).delete()
            messages.success(request, "Análise removida com sucesso!")
        
        # Tratar adição de nova análise
        if 'add_new_analysis' in request.POST:
            # Obter variáveis da nova análise
            dep_vars = request.POST.getlist('new_analysis_dep_vars', [])
            indep_vars = request.POST.getlist('new_analysis_indep_vars', [])
            
            # Validar variáveis contra as colunas atuais
            valid_dep_vars = [var for var in dep_vars if var in dataset.columns]
            valid_indep_vars = [var for var in indep_vars if var in dataset.columns]
            
            # Verificar se temos variáveis suficientes
            if not valid_dep_vars or not valid_indep_vars:
                messages.error(request, "Selecione pelo menos uma variável dependente e uma variável independente válidas.")
            else:
                # Encontrar o próximo número disponível
                existing_numbers = list(Analysis.objects.filter(dataset=dataset).values_list('number', flat=True))
                next_number = 1
                while next_number in existing_numbers:
                    next_number += 1
                
                # Criar uma nova análise
                new_analysis = Analysis(
                    dataset=dataset,
                    number=next_number,
                    name=request.POST.get('new_analysis_name', 'Nova Análise'),
                    dependent_vars=valid_dep_vars,
                    independent_vars=valid_indep_vars,
                    content=request.POST.get('new_analysis_content', ''),
                    status='pending'
                )
                new_analysis.save()
                messages.success(request, f"Nova análise '{new_analysis.name}' adicionada com sucesso!")
        
        return redirect('recommendations', upload_id=dataset.upload_id)

class ExecuteAnalysisView(LoginRequiredMixin, View):
    def get(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        analyses = Analysis.objects.filter(dataset=dataset)
        # Obter índice da análise atual dos parâmetros de consulta ou padrão para 0
        current_idx = int(request.GET.get('analysis', 0))
        if current_idx >= analyses.count():
            current_idx = 0
        
        current_analysis = analyses[current_idx] if analyses.exists() else None

        context = {
            'dataset': dataset,
            'analyses': analyses,
            'current_analysis': current_analysis,
            'current_idx': current_idx,
            'total_analyses': analyses.count(),
        }

        return render(request, 'dashboard/execute.html', context)
    
    def post(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        
        # Tratar execução de uma única análise
        if 'execute_analysis' in request.POST:
            analysis_id = request.POST.get('execute_analysis')
            analysis = get_object_or_404(Analysis, id=analysis_id)
            
            try:
                # Formatar detalhes da análise
                analysis_detail = f"Analise: {analysis.name} Detalhes: {analysis.content}"
                # Chamar a API para executar análise
                result = execute_analysis(
                    str(dataset.upload_id),
                    analysis.number,
                    analysis_detail,
                    analysis.dependent_vars,
                    analysis.independent_vars,
                )
                
                if result.get('success', False):
                    # Atualizar análise com resultados
                    analysis.results = result.get('result')
                    analysis.status = 'completed'
                    analysis.save()
                    messages.success(request, "Análise executada com sucesso!")
                else:
                    analysis.status = 'failed'
                    analysis.save()
                    messages.error(request, f"Erro ao executar análise: {result.get('message')}")
            except Exception as e:
                messages.error(request, f"Erro ao processar análise: {str(e)}")
        
        # Tratar execução de todas as análises
        if 'execute_all' in request.POST:
            try:
                # Chamar API para executar todas as análises
                response = execute_all_analyses(str(dataset.upload_id))
                
                if response.get('success', False):
                    messages.success(request, "Iniciada execução de todas as análises. Este processo pode levar alguns minutos.")
                    # Marcar todas as análises como em execução
                    Analysis.objects.filter(dataset=dataset).update(status='running')
                else:
                    messages.error(request, f"Erro ao iniciar análises: {response.get('message')}")
            except Exception as e:
                messages.error(request, f"Erro ao processar requisição: {str(e)}")
        
        # Redirecionar de volta para a mesma página preservando o índice da análise atual
        current_idx = int(request.POST.get('current_idx', 0))
        return redirect(f'/execute/{upload_id}?analysis={current_idx}')

class ResultsView(LoginRequiredMixin, View):
    def get(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        analyses = Analysis.objects.filter(dataset=dataset)
        
        # Calcular estatísticas
        total_analyses = analyses.count()
        completed_analyses = analyses.filter(status='completed').count()
        failed_analyses = analyses.filter(status='failed').count()
        pending_analyses = total_analyses - completed_analyses - failed_analyses
        
        context = {
            'dataset': dataset,
            'analyses': analyses,
            'total_analyses': total_analyses,
            'completed_analyses': completed_analyses,
            'failed_analyses': failed_analyses,
            'pending_analyses': pending_analyses,
        }
        return render(request, 'dashboard/results.html', context)

def download_report(request, upload_id, format_type):
    """View para download de relatórios em diferentes formatos"""
    dataset = get_object_or_404(Dataset, upload_id=upload_id)
    analyses = list(Analysis.objects.filter(dataset=dataset).values())
    
    if format_type == 'html':
        # Gerar relatório HTML
        html = generate_html_report(analyses)
        response = HttpResponse(html, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="relatorio_analises_{upload_id}.html"'
        return response
    
    elif format_type == 'docx':
        # Gerar relatório DOCX
        docx_data = generate_docx_report(analyses)
        response = HttpResponse(docx_data, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="relatorio_analises_{upload_id}.docx"'
        return response
    
    else:
        messages.error(request, "Formato de relatório inválido")
        return redirect('results', upload_id=upload_id)

class AnalysisHistoryView(LoginRequiredMixin, View):
    """View to display history of executed analyses across all datasets"""
    def get(self, request):
        # Get project_id filter from query params if present
        project_id = request.GET.get('project')
        
        # Filter analyses by project if specified, otherwise show all analyses for the user's projects
        if project_id:
            try:
                project = Project.objects.get(id=project_id, owner=request.user)
                analyses = Analysis.objects.filter(
                    dataset__project=project,
                    status__in=['completed', 'failed']
                ).select_related('dataset').order_by('-updated_at')
                selected_project = project
            except Project.DoesNotExist:
                analyses = Analysis.objects.filter(
                    dataset__project__owner=request.user,
                    status__in=['completed', 'failed']
                ).select_related('dataset').order_by('-updated_at')
                selected_project = None
        else:
            analyses = Analysis.objects.filter(
                dataset__project__owner=request.user,
                status__in=['completed', 'failed']
            ).select_related('dataset').order_by('-updated_at')
            selected_project = None
        
        # Get all user projects for the filter dropdown
        user_projects = Project.objects.filter(owner=request.user)
        
        # Group analyses by dataset for better organization
        datasets = {}
        for analysis in analyses:
            if analysis.dataset not in datasets:
                datasets[analysis.dataset] = []
            datasets[analysis.dataset].append(analysis)
        
        context = {
            'datasets': datasets,
            'analyses_count': analyses.count(),
            'user_projects': user_projects,
            'selected_project': selected_project,
        }
        return render(request, 'dashboard/history.html', context)

class CompareAnalysesView(LoginRequiredMixin, View):
    def get(self, request, analysis1_id, analysis2_id):
        # Get both analyses with their datasets
        analysis1 = get_object_or_404(Analysis, id=analysis1_id)
        analysis2 = get_object_or_404(Analysis, id=analysis2_id)
        
        # Verify the user can access these analyses
        if (analysis1.dataset.project.owner != request.user or 
            analysis2.dataset.project.owner != request.user):
            messages.error(request, "Você não tem permissão para acessar essas análises.")
            return redirect('project_list')
        
        # Check if analyses are from same project
        same_project = analysis1.dataset.project.id == analysis2.dataset.project.id
        
        # Check if analyses are from same dataset
        #same_dataset = analysis1.dataset.upload_id == analysis2.dataset.upload_id
        
        # Create comparison data
        comparison = {
            # Variables comparison
            'common_dep_vars': set(analysis1.dependent_vars) & set(analysis2.dependent_vars),
            'unique_dep_vars1': set(analysis1.dependent_vars) - set(analysis2.dependent_vars),
            'unique_dep_vars2': set(analysis2.dependent_vars) - set(analysis1.dependent_vars),
            'common_indep_vars': set(analysis1.independent_vars) & set(analysis2.independent_vars),
            'unique_indep_vars1': set(analysis1.independent_vars) - set(analysis2.independent_vars),
            'unique_indep_vars2': set(analysis2.independent_vars) - set(analysis1.independent_vars),
            
            # Results status
            'both_successful': analysis1.is_successful() and analysis2.is_successful(),
            
            # Get number of plots and tables for comparison
            'plots_count1': len(analysis1.get_plots()),
            'plots_count2': len(analysis2.get_plots()),
            'tables_count1': len(analysis1.get_tables()),
            'tables_count2': len(analysis2.get_tables()),
        }
        
        # Get AI-generated insights if both analyses were successful
        ai_insights = None
        if comparison['both_successful']:
            ai_insights = get_ai_comparison_insights(analysis1, analysis2)
            # Add to comparison dictionary
            if ai_insights:
                comparison['ai_insights'] = ai_insights.get('insights', '')
                comparison['ai_suggestions'] = ai_insights.get('improvement_suggestions', '')
        
        context = {
            'analysis1': analysis1,
            'analysis2': analysis2,
            'comparison': comparison,
            'ai_insights': ai_insights,
            'same_project': same_project,
            'project': analysis1.dataset.project
        }
        
        return render(request, 'dashboard/compare.html', context)

class DataTreatmentView(LoginRequiredMixin, View):
    def get(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        print(dataset)
        # Sempre buscar a preview atual dos dados da API
        try:
            preview_response = get_treated_dataset_preview(str(upload_id))
            print(f"DEBUG GET - Preview response: {preview_response}")
            if preview_response.get('success'):
                preview = preview_response.get('preview', [])
                # Atualizar informações do dataset se necessário
                if preview_response.get('rows') != dataset.rows or preview_response.get('columns') != dataset.columns:
                    dataset.rows = preview_response.get('rows', dataset.rows)
                    dataset.columns = preview_response.get('columns', dataset.columns)
                    dataset.save()
            else:
                print(f"DEBUG GET - Falha na API, usando sessão: {preview_response}")
                # Fallback para preview da sessão se houver erro na API
                preview = request.session.get('df_preview', [])
        except Exception as e:
            print(f"DEBUG GET - Erro na chamada da API: {str(e)}")
            # Fallback para preview da sessão se houver erro na API
            preview = request.session.get('df_preview', [])
        
        context = {
            'dataset': dataset,
            'preview': preview,
            'columns': dataset.columns,
        }
        return render(request, 'dashboard/data_treatment.html', context)
    
    def post(self, request, upload_id):
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        rule_text = request.POST.get('rule_text')
        
        if not rule_text:
            messages.error(request, "Por favor, descreva a regra de tratamento.")
            return redirect('data_treatment', upload_id=upload_id)
        try:
            # Corrigir URL da API para usar o prefixo correto
            response = requests.post(f"{settings.API_URL}/api/data-treatment/process", json={
                'upload_id': str(upload_id),
                'rule_text': rule_text
            })
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG - Resposta da API: {result}")  # Log para debug
            
            if result.get('success'):
                messages.success(request, "Regra aplicada com sucesso! Os dados originais foram atualizados.")
                
                # Verificar se houve mudanças na estrutura
                final_result = result.get('final_result', {})
                structure_changed = final_result.get('structure_changed', False)
                columns_added = final_result.get('columns_added', [])
                columns_removed = final_result.get('columns_removed', [])
                
                # Atualizar informações do dataset se houve mudanças na estrutura
                # Atualizar as informações do dataset se necessário
                new_columns = final_result.get('columns', dataset.columns)
                dataset.columns = new_columns
                dataset.rows = final_result.get('rows', dataset.rows)
                dataset.save()
                
                # Adicionar mensagem informativa sobre mudanças estruturais
                if structure_changed:
                    change_msg = []
                    if columns_added:
                        change_msg.append(f"Colunas criadas: {', '.join(columns_added)}")
                    if columns_removed:
                        change_msg.append(f"Colunas removidas: {', '.join(columns_removed)}")
                    
                    if change_msg:
                        messages.info(request, f"Estrutura do dataset atualizada. {' | '.join(change_msg)}")
                
                # Usar os dados do resultado direto da API de tratamento
                preview_data = result.get('preview', [])
                if preview_data:
                    request.session['df_preview'] = preview_data
                    print(f"DEBUG - Preview atualizado com {len(preview_data)} linhas")
                else:
                    # Fallback: tentar buscar dados atualizados da API
                    try:
                        from .utils import get_treated_dataset_preview
                        updated_preview = get_treated_dataset_preview(str(upload_id))
                        if updated_preview.get('success'):
                            request.session['df_preview'] = updated_preview.get('preview', [])
                            print(f"DEBUG - Preview obtido via fallback: {len(updated_preview.get('preview', []))} linhas")
                    except Exception as e:
                        print(f"DEBUG - Erro no fallback: {str(e)}")
            else:
                # Caso o processo tenha falhado, mostrar mensagem de erro
                error_msg = result.get('message', 'Erro desconhecido')
                execution_error = result.get('execution_error', '')
                if execution_error:
                    # Formatar erro para mostrar apenas as informações mais relevantes
                    error_lines = execution_error.splitlines()
                    short_error = error_lines[0] if error_lines else execution_error
                    error_msg = f"{error_msg} - {short_error}"
                
                messages.error(request, f"Erro ao processar regra: {error_msg}")
        
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Erro de comunicação com a API: {str(e)}")
        except Exception as e:
            messages.error(request, f"Erro inesperado: {str(e)}")
        
        return redirect('data_treatment', upload_id=upload_id)

@login_required
def get_dataset_columns(request, upload_id):
    """
    Endpoint para obter as colunas atuais do dataset via AJAX.
    """
    try:
        dataset = get_object_or_404(Dataset, upload_id=upload_id)
        
        # Garantir que as colunas estejam atualizadas
        from .utils import get_treated_dataset_preview
        current_data = get_treated_dataset_preview(str(upload_id))
        
        if current_data.get('success'):
            current_columns = current_data.get('columns', dataset.columns)
            
            # Atualizar o objeto do dataset se as colunas forem diferentes
            if set(current_columns) != set(dataset.columns):
                dataset.columns = current_columns
                dataset.save()
            
            return JsonResponse({
                'success': True,
                'columns': current_columns,
                'message': 'Colunas obtidas com sucesso'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': current_data.get('message', 'Erro ao obter colunas do dataset'),
                'columns': dataset.columns  # Retornar as colunas atuais do banco como fallback
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro: {str(e)}',
            'columns': []
        }, status=500)
