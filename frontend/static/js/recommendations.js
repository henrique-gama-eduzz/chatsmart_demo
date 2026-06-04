/**
 * JavaScript para a página de recomendações de análise
 * Gerencia seleção de variáveis, contadores e interações da UI
 */

// Variáveis globais
let uploadId = null;

// Script para garantir que o indicador de salvamento NUNCA seja mostrado
// Este script é executado antes de qualquer outro JavaScript
(function() {
    // Limpar qualquer indicador de salvamento persistente
    localStorage.removeItem('saveInProgress');
    sessionStorage.removeItem('formJustSubmitted');
    
    // Ocultar permanentemente o indicador de salvamento
    window.addEventListener('load', function() {
        const saveStatus = document.getElementById('saveStatus');
        if (saveStatus) {
            saveStatus.style.display = 'none';
            saveStatus.style.visibility = 'hidden';
            saveStatus.classList.remove('visible');
        }
    });
    
    // Sobrescrever qualquer função que possa mostrar o indicador
    const originalAddClass = Element.prototype.classList.add;
    Element.prototype.classList.add = function() {
        if (this.id === 'saveStatus' && arguments[0] === 'visible') {
            // Não faça nada - bloqueia tentativas de tornar o indicador visível
            return;
        }
        return originalAddClass.apply(this, arguments);
    };
})();

// Garantir que o estado de salvamento é limpo em todos os armazenamentos
function clearSaveState() {
    // Limpar todos os possíveis estados de salvamento
    localStorage.removeItem('saveInProgress');
    sessionStorage.removeItem('formJustSubmitted');
    
    // Limpar visualmente o indicador de salvamento
    const saveBtn = document.getElementById('saveEditsBtn');
    const saveStatus = document.getElementById('saveStatus');
    if (saveBtn) saveBtn.classList.remove('loading');
    if (saveStatus) {
        saveStatus.style.display = 'none';
        saveStatus.style.visibility = 'hidden';
        saveStatus.classList.remove('visible');
    }
}

// Função para inicializar os seletores de variáveis
function initializeVariableSelectors() {
    console.log("=== Inicializando seletores de variáveis ===");
    
    // Verificar se existem elementos
    const variableItems = document.querySelectorAll('.variable-item');
    console.log(`Encontrados ${variableItems.length} itens de variável`);
    
    if (variableItems.length === 0) {
        console.warn("Nenhum item de variável encontrado!");
        return;
    }
    
    // Adicionar event listeners para cada item de variável
    variableItems.forEach((item, index) => {
        const dataValue = item.getAttribute('data-value');
        const dataTarget = item.getAttribute('data-target');
        
        console.log(`Configurando item ${index}: ${dataValue} -> ${dataTarget}`);
        
        // Remover listeners anteriores se existirem (sem referência a função inexistente)
        // item.removeEventListener('click', handleVariableClick);
        
        // Adicionar novo listener
        item.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log("=== Item clicado ===");
            console.log("Valor:", dataValue);
            console.log("Target:", dataTarget);
            console.log("Item atual:", this);
            
            // Toggle classe selecionada
            const wasSelected = this.classList.contains('selected');
            this.classList.toggle('selected');
            const isNowSelected = this.classList.contains('selected');
            
            console.log(`Status: ${wasSelected} -> ${isNowSelected}`);
            
            // Atualizar campo select oculto
            const selectElement = document.getElementById(dataTarget);
            
            if (selectElement) {
                console.log("Select element encontrado:", selectElement.id);
                
                // Encontrar a opção correspondente
                let option = null;
                for (let i = 0; i < selectElement.options.length; i++) {
                    if (selectElement.options[i].value === dataValue) {
                        option = selectElement.options[i];
                        break;
                    }
                }
                
                // Se a opção não existir, criar uma nova
                if (!option) {
                    console.log("Criando nova opção para:", dataValue);
                    option = document.createElement('option');
                    option.value = dataValue;
                    option.text = dataValue;
                    selectElement.appendChild(option);
                }
                
                // Definir seleção baseada na classe do item
                option.selected = isNowSelected;
                console.log("Opção definida como selecionada:", option.selected);
                
                // Atualizar contador
                updateCounter(dataTarget);
            } else {
                console.error(`Elemento select com ID ${dataTarget} não encontrado`);
            }
        });
    });
    
    console.log("=== Inicialização concluída ===");
    
    // Atualizar contadores iniciais após um pequeno delay
    setTimeout(() => {
        updateAllCounters();
    }, 100);
}

// Função para atualizar contador de variáveis selecionadas
function updateCounter(fieldName) {
    console.log("=== Atualizando contador ===");
    console.log("Field name:", fieldName);
    
    const selectElement = document.getElementById(fieldName);
    if (!selectElement) {
        console.error(`Select element não encontrado: ${fieldName}`);
        return;
    }
    
    const selectedCount = Array.from(selectElement.selectedOptions).length;
    console.log("Selected count:", selectedCount);
    
    // Determinar qual é o contador correspondente
    let counterId;
    
    if (fieldName.startsWith('dep_')) {
        // Para análises existentes - dependentes
        const analysisNumber = fieldName.split('_')[1];
        counterId = `dep-vars-count-${analysisNumber}`;
    } else if (fieldName.startsWith('indep_')) {
        // Para análises existentes - independentes
        const analysisNumber = fieldName.split('_')[1];
        counterId = `indep-vars-count-${analysisNumber}`;
    } else if (fieldName === 'new_analysis_dep_vars') {
        // Para nova análise - dependentes
        counterId = 'new-dep-vars-count';
    } else if (fieldName === 'new_analysis_indep_vars') {
        // Para nova análise - independentes
        counterId = 'new-indep-vars-count';
    }
    
    console.log("Counter ID:", counterId);
    
    if (counterId) {
        const counterElement = document.getElementById(counterId);
        if (counterElement) {
            counterElement.textContent = `${selectedCount} selecionada(s)`;
            console.log("Contador atualizado:", counterElement.textContent);
        } else {
            console.error(`Elemento contador não encontrado: ${counterId}`);
        }
    }
    
    console.log("=== Fim atualização contador ===");
}

// Função para atualizar todos os contadores
function updateAllCounters() {
    console.log("=== Atualizando todos os contadores ===");
    
    // Atualizar contadores para todas as análises existentes
    const selects = document.querySelectorAll('select[multiple]');
    console.log(`Encontrados ${selects.length} elementos select`);
    
    selects.forEach((select, index) => {
        console.log(`Atualizando contador para select ${index}: ${select.id}`);
        updateCounter(select.id);
    });
    
    console.log("=== Fim atualização de todos os contadores ===");
}

// Função para garantir que o estado inicial esteja correto
function syncInitialState() {
    console.log("=== Sincronizando estado inicial ===");
    
    // Para cada seletor de variáveis, sincronizar com o select correspondente
    document.querySelectorAll('.variable-selector').forEach(selector => {
        const firstItem = selector.querySelector('.variable-item');
        if (!firstItem) return;
        
        const targetId = firstItem.getAttribute('data-target');
        const selectElement = document.getElementById(targetId);
        
        if (!selectElement) return;
        
        console.log(`Sincronizando seletor para: ${targetId}`);
        
        // Para cada item no seletor
        selector.querySelectorAll('.variable-item').forEach(item => {
            const value = item.getAttribute('data-value');
            const isVisuallySelected = item.classList.contains('selected');
            
            // Encontrar a opção correspondente no select
            const option = Array.from(selectElement.options).find(opt => opt.value === value);
            
            if (option) {
                // Sincronizar estado
                if (isVisuallySelected !== option.selected) {
                    console.log(`Sincronizando ${value}: visual=${isVisuallySelected}, select=${option.selected}`);
                    
                    if (isVisuallySelected) {
                        option.selected = true;
                    } else {
                        item.classList.add('selected');
                    }
                }
            }
        });
    });
    
    console.log("=== Fim sincronização estado inicial ===");
}

// Função para debug - verificar se todos os elementos necessários existem  
function debugElements() {
    console.log("=== DEBUG DOS ELEMENTOS ===");
    
    const variableItems = document.querySelectorAll('.variable-item');
    const variableSelectors = document.querySelectorAll('.variable-selector');
    const selectElements = document.querySelectorAll('select[multiple]');
    const counters = document.querySelectorAll('[id*="vars-count"]');
    
    console.log(`Total de elementos encontrados:`);
    console.log(`- Variable items: ${variableItems.length}`);
    console.log(`- Variable selectors: ${variableSelectors.length}`);
    console.log(`- Select elements: ${selectElements.length}`);
    console.log(`- Counters: ${counters.length}`);
    
    // Verificar se cada variable-item tem os atributos necessários
    variableItems.forEach((item, index) => {
        const value = item.getAttribute('data-value');
        const target = item.getAttribute('data-target');
        const hasClass = item.classList.contains('selected');
        
        console.log(`Item ${index}: value="${value}", target="${target}", selected=${hasClass}`);
        
        // Verificar se o target select existe
        const targetSelect = document.getElementById(target);
        if (!targetSelect) {
            console.error(`  -> Target select "${target}" NÃO encontrado!`);
        } else {
            console.log(`  -> Target select "${target}" encontrado, ${targetSelect.options.length} opções`);
        }
    });
    
    // Verificar selects
    selectElements.forEach((select, index) => {
        const selectedCount = Array.from(select.selectedOptions).length;
        console.log(`Select ${index} (${select.id}): ${selectedCount} opções selecionadas de ${select.options.length} total`);
    });
    
    console.log("=== FIM DEBUG ===");
}

// Função para download de dados
function downloadData(format) {
    if (!uploadId) {
        console.error('Upload ID não definido');
        return;
    }
    
    const downloadUrl = `http://localhost:8000/api/data-treatment/download/${uploadId}?format=${format}`;
    
    // Criar elemento de link temporário para o download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `dados_tratados_${uploadId}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Mostrar mensagem de sucesso
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.innerHTML = `
        <i class="fas fa-check-circle"></i>
        Download iniciado! Os dados tratados estão sendo baixados em formato ${format.toUpperCase()}.
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Inserir alerta no topo da página, após as outras notificações
    const firstCard = document.querySelector('.mb-4');
    if (firstCard && firstCard.parentNode) {
        firstCard.parentNode.insertBefore(alertDiv, firstCard);
    }
    
    // Auto-remove o alerta após 4 segundos
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 4000);
}

// Função para recarregar variáveis via AJAX
function reloadVariables() {
    if (!uploadId) {
        console.error('Upload ID não definido');
        return;
    }
    
    const apiUrl = `/api/dataset-columns/${uploadId}/`;
    
    // Mostrar indicador de carregamento
    const reloadBtn = document.getElementById('reloadVariablesBtn');
    if (reloadBtn) {
        const originalText = reloadBtn.innerHTML;
        reloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Carregando...';
        reloadBtn.disabled = true;
    }
    
    // Fazer requisição AJAX
    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Atualizar os seletores de variáveis com as novas colunas
                updateVariableSelectors(data.columns);
                
                // Mostrar mensagem de sucesso
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-success alert-dismissible fade show';
                alertDiv.innerHTML = `
                    <i class="fas fa-check-circle me-2"></i>
                    Variáveis atualizadas com sucesso! Agora você pode selecionar novas colunas.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Inserir alerta no topo da página
                const messages = document.getElementById('django-messages') || document.querySelector('.mb-4');
                if (messages) {
                    messages.appendChild(alertDiv);
                }
                
                // Auto-remove o alerta após 4 segundos
                setTimeout(() => {
                    if (alertDiv.parentNode) {
                        alertDiv.remove();
                    }
                }, 4000);
            } else {
                // Mostrar mensagem de erro
                alert('Erro ao atualizar variáveis: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Erro na requisição:', error);
            alert('Erro ao comunicar com o servidor. Por favor, tente novamente.');
        })
        .finally(() => {
            // Restaurar botão
            if (reloadBtn) {
                reloadBtn.innerHTML = '<i class="fas fa-redo-alt"></i> Recarregar Variáveis';
                reloadBtn.disabled = false;
            }
        });
}

// Função para atualizar os seletores de variáveis com as novas colunas
function updateVariableSelectors(columns) {
    // Selecionar todos os seletores de variáveis
    const selectors = document.querySelectorAll('.variable-selector');
    
    selectors.forEach(selector => {
        const targetId = selector.querySelector('.variable-item')?.getAttribute('data-target');
        if (!targetId) return;
        
        // Limpar o conteúdo atual do seletor
        selector.innerHTML = '';
        
        // Selecionar o elemento select correspondente
        const selectElement = document.getElementById(targetId);
        if (!selectElement) return;
        
        // Coletar valores selecionados anteriormente
        const selectedValues = Array.from(selectElement.selectedOptions).map(opt => opt.value);
        
        // Limpar o select
        selectElement.innerHTML = '';
        
        // Para cada coluna, adicionar um item no seletor e uma opção no select
        columns.forEach(column => {
            // Criar item de variável clicável
            const isSelected = selectedValues.includes(column);
            const itemDiv = document.createElement('div');
            itemDiv.className = `variable-item ${isSelected ? 'selected' : ''}`;
            itemDiv.setAttribute('data-value', column);
            itemDiv.setAttribute('data-target', targetId);
            itemDiv.textContent = column;
            selector.appendChild(itemDiv);
            
            // Adicionar opção ao select
            const option = new Option(column, column, false, isSelected);
            selectElement.add(option);
        });
    });
    
    // Reinicializar seletores de variáveis
    initializeVariableSelectors();
}

// Função para configurar event listeners adicionais
function setupEventListeners() {
    // Adicionar funcionalidade ao botão de atualizar colunas
    const refreshButton = document.querySelector('a[href*="refresh=1"]');
    if (refreshButton) {
        refreshButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Mostrar indicador de carregamento
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Atualizando...';
            this.disabled = true;
            
            // Fazer uma chamada AJAX para atualizar as colunas
            fetch(this.href)
                .then(response => window.location.reload())
                .catch(error => {
                    console.error('Erro ao atualizar colunas:', error);
                    this.innerHTML = originalText;
                    this.disabled = false;
                    alert('Erro ao atualizar colunas. Por favor, tente novamente.');
                });
        });
    }
    
    // Adicionar loader ao salvar edições (SEM mostrar o indicador de salvamento)
    const form = document.getElementById('recommendationsForm');
    const saveBtn = document.getElementById('saveEditsBtn');
    
    if (form && saveBtn) {
        form.addEventListener('submit', function(e) {
            // Verificar se o botão pressionado foi o de salvar edições
            if (e.submitter && e.submitter.name === 'save_all_edits') {
                saveBtn.classList.add('loading');
                // NÃO exibe mais o indicador de salvamento
            }
        });
    }
    
    // Adicionar evento ao botão de recarregar variáveis
    const reloadBtn = document.getElementById('reloadVariablesBtn');
    if (reloadBtn) {
        reloadBtn.addEventListener('click', reloadVariables);
    }
}

// Função para inicializar a página
function initializePage(datasetUploadId) {
    uploadId = datasetUploadId;
    
    console.log("=== Inicializando página de recomendações ===");
    console.log("Upload ID:", uploadId);
    
    // Limpar imediatamente qualquer estado de salvamento residual
    clearSaveState();
    
    // Executar debug dos elementos
    debugElements();
    
    // Verificar se os elementos básicos existem
    const variableItems = document.querySelectorAll('.variable-item');
    const variableSelectors = document.querySelectorAll('.variable-selector');
    const selectElements = document.querySelectorAll('select[multiple]');
    
    console.log(`Elementos encontrados:`);
    console.log(`- Variable items: ${variableItems.length}`);
    console.log(`- Variable selectors: ${variableSelectors.length}`);
    console.log(`- Select elements: ${selectElements.length}`);
    
    // Aguardar um pouco para garantir que tudo está renderizado
    setTimeout(() => {
        console.log("Executando inicialização após timeout");
        
        // Primeiro sincronizar o estado inicial
        syncInitialState();
        
        // Depois inicializar todos os seletores de variáveis
        initializeVariableSelectors();
        
        // Por fim, exibir contagens atualizadas
        updateAllCounters();
        
        // Configurar event listeners adicionais
        setupEventListeners();
        
        // Tornar função downloadData global para uso nos links
        window.downloadData = downloadData;
    }, 100);
}

// Configuração inicial quando a página carrega
document.addEventListener('DOMContentLoaded', function() {
    // A função initializePage será chamada do template HTML com o upload_id
    console.log("DOM carregado, aguardando inicialização...");
});
