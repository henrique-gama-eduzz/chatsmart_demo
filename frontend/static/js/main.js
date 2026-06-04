// Main JavaScript for ChatSmart application

document.addEventListener('DOMContentLoaded', function() {
    updateDarkModeIcon(localStorage.getItem('theme') || 'light');
    initToasts();
    checkApiStatus();
    initializeTooltips();
    refreshRunningAnalyses();
    initializeWorkflowTabs();
    clearStoredProgressData();
});

// ============================================================
// DARK MODE
// ============================================================
function updateDarkModeIcon(theme) {
    const btn = document.getElementById('dark-mode-toggle');
    if (!btn) return;
    btn.innerHTML = theme === 'dark'
        ? '<i class="fas fa-sun"></i>'
        : '<i class="fas fa-moon"></i>';
    btn.title = theme === 'dark' ? 'Modo claro' : 'Modo escuro';
}

function toggleDarkMode() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateDarkModeIcon(next);
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
const TOAST_ICONS = {
    success: 'fa-check-circle',
    danger:  'fa-times-circle',
    warning: 'fa-exclamation-triangle',
    info:    'fa-info-circle'
};

function showToast(message, type) {
    type = type || 'info';
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icon = TOAST_ICONS[type] || TOAST_ICONS.info;
    const toast = document.createElement('div');
    toast.className = 'cs-toast cs-toast-' + type;
    toast.innerHTML =
        '<i class="fas ' + icon + '" style="flex-shrink:0;margin-top:2px"></i>' +
        '<span style="flex:1">' + message + '</span>' +
        '<button class="cs-toast-close" onclick="this.closest(\'.cs-toast\').remove()">×</button>';

    container.appendChild(toast);

    requestAnimationFrame(function() {
        requestAnimationFrame(function() { toast.classList.add('show'); });
    });

    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() { toast.remove(); }, 300);
    }, 5000);
}

function initToasts() {
    document.querySelectorAll('.django-message').forEach(function(el) {
        showToast(el.dataset.message, el.dataset.type || 'info');
    });
}

// ============================================================
// API STATUS
// ============================================================
function checkApiStatus() {
    const statusElement = document.getElementById('api-status');
    if (!statusElement) return;

    fetch('/api/status/')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.status === 'connected') {
                statusElement.innerHTML = '<div class="text-success"><i class="fas fa-check-circle"></i> Conectado</div>';
            } else {
                statusElement.innerHTML = '<div class="text-danger"><i class="fas fa-times-circle"></i> Serviço indisponível</div>';
            }
        })
        .catch(function() {
            statusElement.innerHTML = '<div class="text-danger"><i class="fas fa-times-circle"></i> Erro de conexão</div>';
        });
}

// ============================================================
// TOOLTIPS
// ============================================================
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// ============================================================
// AUTO-REFRESH RUNNING ANALYSES
// ============================================================
function refreshRunningAnalyses() {
    const runningElements = document.querySelectorAll('.analysis-running');
    if (runningElements.length > 0) {
        setTimeout(function() { window.location.reload(); }, 10000);
    }
}

// ============================================================
// WORKFLOW TABS
// ============================================================
function initializeWorkflowTabs() {
    const workflowTabs = document.querySelectorAll('.workflow-tabs .nav-link');
    let activeFound = false;

    workflowTabs.forEach(function(tab) {
        if (tab.classList.contains('active')) {
            activeFound = true;
        } else if (!activeFound && !tab.classList.contains('disabled')) {
            tab.classList.add('completed');
            const icon = tab.querySelector('.tab-icon');
            if (icon) {
                icon.innerHTML += '<span class="completion-check"><i class="fas fa-check-circle text-success"></i></span>';
            }
        }
    });
}

// ============================================================
// CLEAR STORED PROGRESS DATA
// ============================================================
function clearStoredProgressData() {
    if (window.location.pathname.includes('/recommendations/')) {
        localStorage.removeItem('saveInProgress');
        sessionStorage.removeItem('formJustSubmitted');

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
