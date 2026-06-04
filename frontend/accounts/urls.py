from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.SignUpView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Database connection URLs
    path('database-connections/', views.database_connections_view, name='database_connections'),
    path('database-connections/add/', views.add_database_connection, name='add_database_connection'),
    path('database-connections/edit/<int:connection_id>/', views.edit_database_connection, name='edit_database_connection'),
    path('database-connections/delete/<int:connection_id>/', views.delete_database_connection, name='delete_database_connection'),
    path('database-connections/test/<int:connection_id>/', views.test_connection_view, name='test_database_connection'),
    path('database-connections/import/<int:connection_id>/', views.import_from_database, name='import_from_database'),
    path('database-connections/import-preview/', views.database_import_preview, name='database_import_preview'),
]
