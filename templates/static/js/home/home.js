/**
 * Script para funcionalidades da página home/dashboard
 * Inclui pesquisa de comandas em tempo real
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
    initializeFilterButtons();
});

/**
 * Inicializa a funcionalidade de pesquisa
 */
function initializeSearch() {
    const searchInput = document.getElementById('search-comandas');
    const clearButton = document.getElementById('clear-search');
    const searchResults = document.getElementById('search-results');
    const resultsCount = document.getElementById('results-count');
    const comandaCards = document.querySelectorAll('[data-comanda]');
    
    // Função de pesquisa em tempo real
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        let visibleCount = 0;
        
        // Mostrar/esconder botão de limpar
        toggleClearButton(searchTerm.length > 0);
        toggleSearchResults(searchTerm.length > 0);
        
        // Filtrar comandas
        comandaCards.forEach(card => {
            const shouldShow = filterComanda(card, searchTerm);
            
            if (shouldShow) {
                showComanda(card);
                visibleCount++;
            } else {
                hideComanda(card);
            }
        });
        
        // Atualizar contador
        updateResultsCount(visibleCount);
    });
    
    // Função para limpar pesquisa
    clearButton.addEventListener('click', function() {
        clearSearch();
    });
    
    // Esc para limpar pesquisa
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            clearSearch();
        }
    });
    
    /**
     * Verifica se uma comanda deve ser mostrada baseado no termo de pesquisa
     */
    function filterComanda(card, searchTerm) {
        if (searchTerm === '') return true;
        
        const comandaNumber = card.getAttribute('data-numero') || '';
        const mesa = card.getAttribute('data-mesa') || '';
        const cliente = card.getAttribute('data-cliente') || '';
        const itens = card.getAttribute('data-itens') || '';
        
        const searchText = `${comandaNumber} ${mesa} ${cliente} ${itens}`.toLowerCase();
        return searchText.includes(searchTerm);
    }
    
    /**
     * Mostra uma comanda com animação
     */
    function showComanda(card) {
        card.style.display = 'block';
        card.classList.remove('hidden');
        
        // Animação de entrada
        card.style.opacity = '0';
        card.style.transform = 'translateY(10px)';
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
            card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        }, 50);
    }
    
    /**
     * Esconde uma comanda com animação
     */
    function hideComanda(card) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(-10px)';
        card.style.transition = 'opacity 0.15s ease, transform 0.15s ease';
        
        setTimeout(() => {
            card.style.display = 'none';
            card.classList.add('hidden');
        }, 150);
    }
    
    /**
     * Mostra/esconde o botão de limpar
     */
    function toggleClearButton(show) {
        if (show) {
            clearButton.classList.remove('opacity-0');
            clearButton.classList.add('opacity-100');
        } else {
            clearButton.classList.add('opacity-0');
            clearButton.classList.remove('opacity-100');
        }
    }
    
    /**
     * Mostra/esconde os resultados da pesquisa
     */
    function toggleSearchResults(show) {
        if (show) {
            searchResults.classList.remove('opacity-0');
            searchResults.classList.add('opacity-100');
        } else {
            searchResults.classList.add('opacity-0');
            searchResults.classList.remove('opacity-100');
        }
    }
    
    /**
     * Atualiza o contador de resultados
     */
    function updateResultsCount(count) {
        resultsCount.textContent = count;
    }
    
    /**
     * Limpa a pesquisa
     */
    function clearSearch() {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
        searchInput.focus();
    }
}

/**
 * Inicializa os botões de filtro (Todas, Em Preparo, Prontas)
 */
function initializeFilterButtons() {
    const filterButtons = document.querySelectorAll('[data-filter]');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filter = this.getAttribute('data-filter');
            
            // Atualizar estado visual dos botões
            filterButtons.forEach(btn => {
                btn.classList.remove('bg-white', 'text-gray-900', 'shadow-sm');
                btn.classList.add('text-gray-600', 'hover:bg-white/50');
            });
            
            this.classList.add('bg-white', 'text-gray-900', 'shadow-sm');
            this.classList.remove('text-gray-600', 'hover:bg-white/50');
            
            // Aplicar filtro (implementar conforme necessário)
            applyStatusFilter(filter);
        });
    });
}

/**
 * Aplica filtro por status das comandas
 */
function applyStatusFilter(filter) {
    // Implementar lógica de filtro por status
    console.log('Filtro aplicado:', filter);
}

/**
 * Utilitários globais
 */
window.HomeDashboard = {
    clearSearch: function() {
        const event = new Event('input');
        document.getElementById('search-comandas').value = '';
        document.getElementById('search-comandas').dispatchEvent(event);
    }
};