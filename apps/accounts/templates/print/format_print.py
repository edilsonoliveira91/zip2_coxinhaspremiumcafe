# PRINT/format_print.py
from datetime import datetime
from django.utils import timezone as dj_timezone

class FormatadorCupom:
    """
    Formatação para impressora térmica 80mm
    Com caracteres especiais funcionando
    """
    
    def __init__(self):
        self.largura = 42
        
    def formatar_cupom(self, dados):
        """Formata cupom com caracteres especiais corretos"""
        linhas = []
        
        # COMANDOS SIMPLIFICADOS PARA COMPATIBILIDADE
        linhas.append("\x1B\x40")        # Reset printer
        linhas.append("\x1B\x21\x00")    # Fonte normal apenas
        
        # Header 
        linhas.extend(self._header_limpo())
        
        # Info comanda
        linhas.extend(self._info_limpa(dados))
        
        # Itens (manter)
        linhas.extend(self._itens_medio(dados['itens']))
        
        # Total
        linhas.extend(self._total_limpo(dados))
        
        # Footer
        linhas.extend(self._footer_limpo())
        
        linhas.extend([""] * 3)
        
        return '\n'.join(linhas)
    
    def _limpar_caracteres(self, texto):
        """Remove/substitui caracteres especiais problemáticos"""
        # Mapa de substituições para impressora térmica
        substituicoes = {
            'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
            'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
            'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
            'ç': 'c', 'ñ': 'n',
            'Á': 'A', 'À': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A',
            'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
            'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
            'Ó': 'O', 'Ò': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O',
            'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
            'Ç': 'C', 'Ñ': 'N',
            '★': '*', '♪': '*', '♫': '*',
            '–': '-', '—': '-', ''': "'", ''': "'", '"': '"', '"': '"'
        }
        
        for original, substituto in substituicoes.items():
            texto = texto.replace(original, substituto)
        return texto
    
    def _centralizar_limpo(self, texto):
        """Centraliza texto limpo"""
        texto_limpo = self._limpar_caracteres(texto)
        return texto_limpo.center(self.largura)
    
    def _header_limpo(self):
        """Header sem caracteres especiais"""
        return [
            "=" * self.largura,
            self._centralizar_limpo("COXINHAS PREMIUM CAFE"),
            self._centralizar_limpo("Cafeteria & Salgados"),
            self._centralizar_limpo("Tel: (11) 9999-9999"),
            "=" * self.largura,
            ""
        ]
    
    def _info_limpa(self, dados):
        """Info limpa"""
        return [
            self._centralizar_limpo(f"COMANDA:{dados['cliente']}"),
            self._centralizar_limpo(dados['data']),
            ""
        ]
    
    def _itens_medio(self, itens):
        """Itens com caracteres limpos"""
        linhas = [
            "-" * self.largura,
            self._centralizar_limpo("ITENS DO PEDIDO"),
            "-" * self.largura
        ]
        
        for item in itens:
            qtd = f"{item['qtd']}x"
            # Limpar nome do produto
            nome = self._limpar_caracteres(item['nome'][:15])
            # VALORES COM VÍRGULA
            preco_unit = f"R${item['preco']:.2f}".replace('.', ',')
            total = f"R${item['subtotal']:.2f}".replace('.', ',')
            
            inicio = f"{qtd} {nome} {preco_unit}"
            espacos = self.largura - len(inicio) - len(total)
            if espacos < 1:
                espacos = 1
                
            linha = inicio + " " * espacos + total
            linhas.append(linha)
            
            # Observações limpas
            if item.get('observacoes'):
                obs_limpa = self._limpar_caracteres(item['observacoes'][:32])
                obs = f"  Obs: {obs_limpa}"
                linhas.append(obs)
        
        return linhas

    def _total_limpo(self, dados):
        """Total limpo com vírgula"""
        # TOTAL COM VÍRGULA
        total_formatado = dados['total'].replace('.', ',')
        
        return [
            "=" * self.largura,
            self._centralizar_limpo(f"TOTAL: {total_formatado}"),
            "=" * self.largura
        ]
    
    def _footer_limpo(self):
        """Footer sem caracteres especiais"""
        agora = dj_timezone.localtime(dj_timezone.now()).strftime("%d/%m/%Y %H:%M")
        
        return [
            "",
            self._centralizar_limpo("Obrigado pela preferencia!"),
            self._centralizar_limpo("*** Volte sempre! ***"),
            "",
            self._centralizar_limpo(agora),
            ""
        ]