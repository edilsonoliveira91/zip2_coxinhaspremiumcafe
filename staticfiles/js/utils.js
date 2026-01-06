// utils.js - Funções utilitárias para o sistema

/**
 * Formatar valor para moeda brasileira (R$)
 * @param {number} value - Valor numérico
 * @returns {string} - Valor formatado como moeda
 */
function formatCurrency(value) {
    if (isNaN(value) || value === null || value === undefined) {
        return 'R$ 0,00';
    }
    
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

/**
 * Aplicar máscara de dinheiro em tempo real
 * @param {HTMLInputElement} input - Campo de input
 */
function applyMoneyMask(input) {
    if (!input) return;
    
    input.addEventListener('input', function(e) {
        let value = e.target.value;
        
        // Remove todos os caracteres não numéricos
        value = value.replace(/\D/g, '');
        
        // Converte para número e divide por 100 para ter centavos
        value = (parseInt(value) || 0) / 100;
        
        // Formata como moeda brasileira
        const formatted = value.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        // Atualiza o valor do campo
        e.target.value = formatted;
    });
    
    // Validação quando o campo perde o foco
    input.addEventListener('blur', function(e) {
        let value = e.target.value;
        
        if (value === '' || value === '0,00') {
            e.target.value = '';
            return;
        }
        
        // Remove caracteres não numéricos e vírgulas
        value = value.replace(/\D/g, '');
        value = (parseInt(value) || 0) / 100;
        
        // Formata novamente
        e.target.value = value.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    });
}

/**
 * Aplicar máscara simples de dinheiro (apenas números com vírgula)
 * @param {HTMLInputElement} input - Campo de input
 */
function applySimpleMoneyMask(input) {
    if (!input) return;
    
    input.addEventListener('input', function(e) {
        let value = e.target.value;
        
        // Remove tudo exceto números e vírgula
        value = value.replace(/[^\d,]/g, '');
        
        // Garante apenas uma vírgula
        const parts = value.split(',');
        if (parts.length > 2) {
            value = parts[0] + ',' + parts.slice(1).join('');
        }
        
        // Limita a 2 casas decimais após a vírgula
        if (parts.length === 2 && parts[1].length > 2) {
            value = parts[0] + ',' + parts[1].substring(0, 2);
        }
        
        e.target.value = value;
    });
}

/**
 * Converter valor formatado para número decimal
 * @param {string} formattedValue - Valor formatado (ex: "1.234,56")
 * @returns {number} - Valor numérico
 */
function parseFormattedCurrency(formattedValue) {
    if (!formattedValue || formattedValue === '') return 0;
    
    // Remove pontos de milhar e substitui vírgula por ponto
    return parseFloat(formattedValue.replace(/\./g, '').replace(',', '.')) || 0;
}

/**
 * Inicializar máscaras de dinheiro em todos os campos com classe 'money-mask'
 */
function initMoneyMasks() {
    const moneyFields = document.querySelectorAll('.money-mask');
    moneyFields.forEach(field => {
        applyMoneyMask(field);
    });
    
    const simpleMoneyFields = document.querySelectorAll('.simple-money-mask');
    simpleMoneyFields.forEach(field => {
        applySimpleMoneyMask(field);
    });
}

/**
 * Máscara especial para campos de preço de produto
 * @param {HTMLInputElement} input - Campo de input
 */
function applyProductPriceMask(input) {
    if (!input) return;
    
    // Remove o atributo step para evitar conflitos
    input.removeAttribute('step');
    
    input.addEventListener('input', function(e) {
        let value = e.target.value;
        
        // Remove todos os caracteres não numéricos
        value = value.replace(/\D/g, '');
        
        // Se estiver vazio, deixa vazio
        if (value === '') {
            e.target.value = '';
            return;
        }
        
        // Converte para centavos
        let numValue = parseInt(value) || 0;
        
        // Converte de volta para reais
        numValue = numValue / 100;
        
        // Formata com vírgula
        e.target.value = numValue.toFixed(2).replace('.', ',');
    });
    
    // Quando o campo perde o foco, converte para formato do backend (com ponto)
    input.addEventListener('blur', function(e) {
        let value = e.target.value;
        
        if (value === '') return;
        
        // Converte vírgula para ponto para o backend
        const numValue = parseFloat(value.replace(',', '.'));
        if (!isNaN(numValue)) {
            // Mantém formato com vírgula na tela
            e.target.value = numValue.toFixed(2).replace('.', ',');
            
            // Cria um campo hidden com valor em formato americano para envio
            let hiddenInput = input.parentNode.querySelector('input[type="hidden"]');
            if (!hiddenInput) {
                hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = input.name;
                input.name = input.name + '_display';
                input.parentNode.appendChild(hiddenInput);
            }
            hiddenInput.value = numValue.toFixed(2);
        }
    });
    
    // Antes de enviar o form, converte o valor para formato americano
    const form = input.closest('form');
    if (form) {
        form.addEventListener('submit', function() {
            let value = input.value;
            if (value !== '') {
                // Converte para formato americano antes de enviar
                input.value = parseFloat(value.replace(',', '.')).toFixed(2);
            }
        });
    }
}

// Inicializar quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    initMoneyMasks();
    
    // Aplicar máscara específica para campos de preço de produto
    const priceFields = document.querySelectorAll('input[name="price"]');
    priceFields.forEach(field => {
        applyProductPriceMask(field);
    });
});

// Exportar funções para uso global
window.formatCurrency = formatCurrency;
window.applyMoneyMask = applyMoneyMask;
window.applySimpleMoneyMask = applySimpleMoneyMask;
window.parseFormattedCurrency = parseFormattedCurrency;
window.applyProductPriceMask = applyProductPriceMask;