// Main JavaScript for ChatSmart application

document.addEventListener('DOMContentLoaded', function() {
    // API Status Check
    checkApiStatus();
    
    // Initialize tooltips
    initializeTooltips();
    
    // Add auto-refresh for analyses in "running" state
    refreshRunningAnalyses();
    
    // Initialize workflow tabs
    initializeWorkflowTabs();
    
    // Clear progress data if needed
    clearStoredProgressData();
});

function checkApiStatus() {
    const statusElement = document.getElementById('api-status');
    if (!statusElement) return;
    
    fetch('/api/status/')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'connected') {
                statusElement.innerHTML = '<div class="text-success"><i class="fas fa-check-circle"></i> Conectado</div>';
            } else {
                statusElement.innerHTML = '<div class="text-danger"><i class="fas fa-times-circle"></i> Serviço indisponível</div>';
            }
        })
        .catch(error => {
            statusElement.innerHTML = '<div class="text-danger"><i class="fas fa-times-circle"></i> Erro de conexão</div>';
        });
}

function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function refreshRunningAnalyses() {
    // Find any elements with a running status
    const runningElements = document.querySelectorAll('.analysis-running');
    
    if (runningElements.length > 0) {
        // If we have running analyses, refresh the page after 10 seconds
        setTimeout(function() {
            window.location.reload();
        }, 10000);
    }
}

function initializeWorkflowTabs() {
    // Highlight completed steps
    const workflowTabs = document.querySelectorAll('.workflow-tabs .nav-link');
    let activeFound = false;
    
    workflowTabs.forEach((tab) => {
        if (tab.classList.contains('active')) {
            activeFound = true;
        } else if (!activeFound && !tab.classList.contains('disabled')) {
            // Add a "completed" indicator to steps before the active step
            tab.classList.add('completed');
            // Add a check mark to the icon
            const icon = tab.querySelector('.tab-icon');
            if (icon) {
                icon.innerHTML += '<span class="completion-check"><i class="fas fa-check-circle text-success"></i></span>';
            }
        }
    });
}

// Função para limpar dados de progresso armazenados se a página for recarregada
function clearStoredProgressData() {
    // Always clear the save status indicators for recommendations page
    if (window.location.pathname.includes('/recommendations/')) {
        localStorage.removeItem('saveInProgress');
        sessionStorage.removeItem('formJustSubmitted');
        
        // Esconder visualmente o indicador de salvamento se existir
        const saveStatus = document.getElementById('saveStatus');
        const saveBtn = document.getElementById('saveEditsBtn');
        
        if (saveStatus) {
            saveStatus.style.display = 'none';
            saveStatus.style.visibility = 'hidden';
            saveStatus.classList.remove('visible');
        }
        
        if (saveBtn) {
            saveBtn.classList.remove('loading');
        }
    }
    
    // Verificar se estamos em uma página de resultados (o que significa que o processamento terminou)
    const isResultPage = window.location.pathname.includes('/results/');
    
    if (isResultPage) {
        localStorage.removeItem('executionInProgress');
        localStorage.removeItem('executionTimeInterval');
        localStorage.removeItem('executionSeconds');
        localStorage.removeItem('executionType');
        localStorage.removeItem('processingTimeInterval');
        localStorage.removeItem('operationInProgress');
        localStorage.removeItem('operationSeconds');
        localStorage.removeItem('saveInProgress');
    }
}
