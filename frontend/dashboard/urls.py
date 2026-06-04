from django.urls import path
from .views import (
    HomeView,
    ProjectListView,
    ProjectCreateView,
    ProjectDetailView,
    ProjectEditView,
    ProjectDeleteView,
    set_current_project,
    DataUploadView,
    DefineVariablesView,
    RecommendationsView,
    ExecuteAnalysisView,
    ResultsView,
    AnalysisHistoryView,
    download_report,
    check_api_status,
    CompareAnalysesView,
    DataTreatmentView,
    get_dataset_columns
)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    
    # Project URLs
    path('projects/', ProjectListView.as_view(), name='project_list'),
    path('projects/create/', ProjectCreateView.as_view(), name='project_create'),
    path('projects/<uuid:project_id>/', ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<uuid:project_id>/edit/', ProjectEditView.as_view(), name='project_edit'),
    path('projects/<uuid:project_id>/delete/', ProjectDeleteView.as_view(), name='project_delete'),
    path('projects/<uuid:project_id>/set-current/', set_current_project, name='set_current_project'),
    
    # Dataset and Analysis URLs
    path('upload/', DataUploadView.as_view(), name='upload'),
    path('variables/<uuid:upload_id>/', DefineVariablesView.as_view(), name='define_variables'),
    path('recommendations/<uuid:upload_id>/', RecommendationsView.as_view(), name='recommendations'),
    path('execute/<uuid:upload_id>/', ExecuteAnalysisView.as_view(), name='execute'),
    path('results/<uuid:upload_id>/', ResultsView.as_view(), name='results'),
    path('history/', AnalysisHistoryView.as_view(), name='analysis_history'),
    path('download/<uuid:upload_id>/<str:format_type>/', download_report, name='download_report'),
    path('api/status/', check_api_status, name='api_status'),
    path('compare/<int:analysis1_id>/<int:analysis2_id>/', CompareAnalysesView.as_view(), name='compare_analyses'),
    path('data-treatment/<uuid:upload_id>/', DataTreatmentView.as_view(), name='data_treatment'),
    
    # AJAX endpoints
    path('api/dataset-columns/<uuid:upload_id>/', get_dataset_columns, name='get_dataset_columns'),
]
