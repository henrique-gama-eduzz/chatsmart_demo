from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views import View
from django.urls import reverse
from .forms import SignUpForm, UserProfileForm, LoginForm, DatabaseConnectionForm
from .models import UserProfile, DatabaseConnection
import sqlalchemy
import pandas as pd

class SignUpView(View):
    template_name = 'accounts/register.html'
    
    def get(self, request):
        form = SignUpForm()
        return render(request, self.template_name, {'form': form})
        
    def post(self, request):
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=user.username, password=raw_password)
            login(request, user)
            messages.success(request, "Conta criada com sucesso! Bem-vindo ao ChatSmart.")
            return redirect('home')
        return render(request, self.template_name, {'form': form})

class LoginView(View):
    template_name = 'accounts/login.html'
    
    def get(self, request):
        form = LoginForm()
        return render(request, self.template_name, {'form': form})
        
    def post(self, request):
        form = LoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Bem-vindo de volta, {username}!")
                # Redirect to the page the user was trying to access
                next_page = request.GET.get('next', 'home')
                return redirect(next_page)
        # Invalid login
        messages.error(request, "Nome de usuário ou senha inválidos.")
        return render(request, self.template_name, {'form': form})

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user.profile)
    
    # Get the user's datasets
    from dashboard.models import Dataset
    user_datasets = Dataset.objects.all()  # Later filter by user
    
    # Get user's database connections
    database_connections = DatabaseConnection.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'form': form,
        'user': request.user,
        'datasets': user_datasets,
        'database_connections': database_connections
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def database_connections_view(request):
    """View to manage database connections"""
    connections = DatabaseConnection.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'connections': connections,
    }
    return render(request, 'accounts/database_connections.html', context)

@login_required
def add_database_connection(request):
    """View to add a new database connection"""
    if request.method == 'POST':
        form = DatabaseConnectionForm(request.POST)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.user = request.user
            
            # Test connection if requested
            if 'test_connection' in request.POST:
                success, message = test_database_connection(form.cleaned_data)
                if success:
                    messages.success(request, f"Connection test successful: {message}")
                else:
                    messages.error(request, f"Connection test failed: {message}")
                    return render(request, 'accounts/add_database_connection.html', {'form': form})
            
            connection.save()
            messages.success(request, "Database connection added successfully!")
            return redirect('database_connections')
    else:
        form = DatabaseConnectionForm()
    
    return render(request, 'accounts/add_database_connection.html', {'form': form})

@login_required
def edit_database_connection(request, connection_id):
    """View to edit an existing database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    if request.method == 'POST':
        form = DatabaseConnectionForm(request.POST, instance=connection)
        if form.is_valid():
            # Test connection if requested
            if 'test_connection' in request.POST:
                success, message = test_database_connection(form.cleaned_data)
                if success:
                    messages.success(request, f"Connection test successful: {message}")
                else:
                    messages.error(request, f"Connection test failed: {message}")
                    return render(request, 'accounts/edit_database_connection.html', 
                                  {'form': form, 'connection': connection})
            
            form.save()
            messages.success(request, "Database connection updated successfully!")
            return redirect('database_connections')
    else:
        form = DatabaseConnectionForm(instance=connection)
    
    return render(request, 'accounts/edit_database_connection.html', 
                  {'form': form, 'connection': connection})

@login_required
def delete_database_connection(request, connection_id):
    """View to delete a database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    if request.method == 'POST':
        connection_name = connection.name
        connection.delete()
        messages.success(request, f"Database connection '{connection_name}' deleted successfully!")
        return redirect('database_connections')
    
    return render(request, 'accounts/delete_database_connection.html', {'connection': connection})

@login_required
def test_connection_view(request, connection_id):
    """View to test a database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    # Extract connection details
    connection_data = {
        'database_type': connection.database_type,
        'host': connection.host,
        'port': connection.port,
        'database_name': connection.database_name,
        'username': connection.username,
        'password': connection.password,
        'connection_string': connection.connection_string,
        'ssl_enabled': connection.ssl_enabled
    }
    
    success, message = test_database_connection(connection_data)
    
    if success:
        messages.success(request, f"Connection test successful: {message}")
    else:
        messages.error(request, f"Connection test failed: {message}")
    
    return redirect(reverse('edit_database_connection', args=[connection_id]))

def test_database_connection(connection_data):
    """Test database connection using SQLAlchemy"""
    try:
        db_type = connection_data.get('database_type')
        connection_string = connection_data.get('connection_string')
        
        # Use direct connection string if provided
        if connection_string:
            engine_url = connection_string
        else:
            # Build connection URL based on database type
            if db_type == 'postgresql':
                engine_url = f"postgresql://{connection_data.get('username')}:{connection_data.get('password')}@{connection_data.get('host')}:{connection_data.get('port')}/{connection_data.get('database_name')}"
            elif db_type == 'mysql':
                engine_url = f"mysql+pymysql://{connection_data.get('username')}:{connection_data.get('password')}@{connection_data.get('host')}:{connection_data.get('port')}/{connection_data.get('database_name')}"
            elif db_type == 'sqlserver':
                engine_url = f"mssql+pyodbc://{connection_data.get('username')}:{connection_data.get('password')}@{connection_data.get('host')}:{connection_data.get('port')}/{connection_data.get('database_name')}?driver=ODBC+Driver+17+for+SQL+Server"
            elif db_type == 'oracle':
                engine_url = f"oracle+cx_oracle://{connection_data.get('username')}:{connection_data.get('password')}@{connection_data.get('host')}:{connection_data.get('port')}/{connection_data.get('database_name')}"
            elif db_type == 'sqlite':
                engine_url = f"sqlite:///{connection_data.get('database_name')}"
            else:
                return False, "Unsupported database type"
            
            # Add SSL if enabled
            if connection_data.get('ssl_enabled') and db_type in ('postgresql', 'mysql'):
                engine_url += "?ssl=true"
        
        # Create engine and test connection
        engine = sqlalchemy.create_engine(engine_url)
        connection = engine.connect()
        connection.close()
        engine.dispose()
        
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)

def convert_df_to_serializable(df):
    """Convert pandas DataFrame to JSON serializable format"""
    # Convert to records, with timestamp objects converted to strings
    records = []
    for record in df.to_dict('records'):
        serializable_record = {}
        for key, value in record.items():
            # Convert pandas Timestamp or datetime objects to strings
            if pd.api.types.is_datetime64_any_dtype(type(value)) or hasattr(value, 'strftime'):
                serializable_record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                serializable_record[key] = value
        records.append(serializable_record)
    return records

def sanitize_column_names(df):
    """Clean column names by removing backticks and other problematic characters"""
    # Create a mapping of original columns to cleaned columns
    column_map = {}
    for col in df.columns:
        # Remove backticks, brackets, and quotes
        clean_col = col.replace('`', '')
        column_map[col] = clean_col
    
    # Rename the columns in the dataframe
    return df.rename(columns=column_map)

@login_required
def import_from_database(request, connection_id):
    """View to import data from a database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    # Get current project from session
    current_project = None
    current_project_id = request.session.get('current_project_id')
    
    if current_project_id:
        from dashboard.models import Project
        try:
            current_project = Project.objects.get(id=current_project_id, owner=request.user)
        except Project.DoesNotExist:
            current_project = None
    
    if request.method == 'POST':
        # Check if we have a current project
        if not current_project:
            messages.error(request, "No active project selected. Please select a project first.")
            return render(request, 'accounts/import_from_database.html', {
                'connection': connection,
                'current_project': None
            })
            
        # Get query from form
        sql_query = request.POST.get('sql_query')
        if not sql_query:
            messages.error(request, "SQL query is required")
            return render(request, 'accounts/import_from_database.html', {
                'connection': connection, 
                'current_project': current_project
            })
        
        try:
            # Connect to database
            connection_data = {
                'database_type': connection.database_type,
                'host': connection.host,
                'port': connection.port,
                'database_name': connection.database_name,
                'username': connection.username,
                'password': connection.password,
                'connection_string': connection.connection_string,
                'ssl_enabled': connection.ssl_enabled
            }
            
            # Build connection URL based on database type or use connection string
            if connection.connection_string:
                engine_url = connection.connection_string
            else:
                if connection.database_type == 'postgresql':
                    engine_url = f"postgresql://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
                elif connection.database_type == 'mysql':
                    engine_url = f"mysql+pymysql://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
                elif connection.database_type == 'sqlserver':
                    engine_url = f"mssql+pyodbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver=ODBC+Driver+17+for+SQL+Server"
                elif connection.database_type == 'oracle':
                    engine_url = f"oracle+cx_oracle://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
                elif connection.database_type == 'sqlite':
                    engine_url = f"sqlite:///{connection.database_name}"
                
                # Add SSL if enabled
                if connection.ssl_enabled and connection.database_type in ('postgresql', 'mysql'):
                    engine_url += "?ssl=true"
            
            # Execute query and load data
            engine = sqlalchemy.create_engine(engine_url)
            df = pd.read_sql(sql_query, engine)
            
            # Clean column names by removing backticks
            df = sanitize_column_names(df)
            
            # Create a Dataset record in the database
            from dashboard.models import Dataset
            import uuid
            import tempfile
            
            # Generate a unique upload ID
            upload_id = uuid.uuid4()
            
            # Create a temporary CSV file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
                df.to_csv(temp_file.name, index=False)
                temp_file_path = temp_file.name
            
            # Process the file with the API
            from dashboard.utils import upload_file
            with open(temp_file_path, 'rb') as f:
                from django.core.files.uploadedfile import SimpleUploadedFile
                file_name = f"db_import_{connection.name}_{upload_id}.csv"
                file = SimpleUploadedFile(file_name, f.read(), content_type='text/csv')
                api_response = upload_file(file)
            
            # Clean up temporary file
            import os
            os.unlink(temp_file_path)
            
            if not api_response.get("success", False):
                messages.error(request, f"Error processing data: {api_response.get('message', 'Unknown error')}")
                return render(request, 'accounts/import_from_database.html', 
                             {'connection': connection, 'current_project': current_project})
                
            # Create dataset in database using the current project
            dataset = Dataset.objects.create(
                project=current_project,
                upload_id=api_response.get("upload_id", str(upload_id)),
                name=file_name,
                columns=api_response.get("columns", list(df.columns)),
                rows=len(df),
                file=None  # No physical file saved
            )
            
            # Store dataset context in session with clean column names
            request.session['upload_id'] = str(dataset.upload_id)
            request.session['current_project_id'] = str(dataset.project.id)
            request.session['df_preview'] = convert_df_to_serializable(df.head(10))
            request.session['columns'] = list(df.columns)
            
            messages.success(request, f"Successfully imported data: {len(df)} rows, {len(df.columns)} columns")
            
            # Go to preview page
            return redirect('database_import_preview')
            
        except Exception as e:
            messages.error(request, f"Error importing data: {str(e)}")
    
    return render(request, 'accounts/import_from_database.html', {
        'connection': connection,
        'current_project': current_project
    })

@login_required
def database_import_preview(request):
    """Preview data imported from database"""
    preview_data = request.session.get('df_preview', [])
    columns = request.session.get('columns', [])
    upload_id = request.session.get('upload_id')
    
    context = {
        'preview': preview_data,
        'columns': columns,
        'upload_id': upload_id
    }
    return render(request, 'accounts/database_import_preview.html', context)
