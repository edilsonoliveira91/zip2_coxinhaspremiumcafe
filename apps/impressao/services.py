import subprocess
import tempfile
import os
import sys
from datetime import datetime

# Adicionar caminho para pasta PRINT
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'accounts', 'templates', 'print'))
from apps.accounts.templates.print.format_print import FormatadorCupom

class EpsonService:
    def __init__(self):
        self.printer_name = "EPSON_TM_T20X_II"
    
    def imprimir_comanda(self, comanda_data):
      """Imprime comanda na impressora térmica"""
      try:
          # Gerar conteúdo formatado
          conteudo = self._formatar_comanda(comanda_data)
          
          # Criar arquivo temporário
          with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
              f.write(conteudo)
              temp_file = f.name
          
          # Imprimir o arquivo COMPLETO primeiro
          result = subprocess.run([
              'lp', '-d', self.printer_name, temp_file
          ], capture_output=True, text=True)
          
          # Limpar arquivo
          os.unlink(temp_file)
          
          # AGUARDAR a impressão terminar completamente
          import time
          time.sleep(1)  # 3 segundos para garantir que terminou
          
          # DEPOIS fazer o corte
          if result.returncode == 0:
              self.enviar_corte()
          
          return result.returncode == 0
          
      except Exception as e:
          print(f"Erro na impressão: {e}")
          return False
    
    def enviar_corte(self):
        """Envia comando de corte para a impressora"""
        try:
            # Criar arquivo temporário com comando de corte
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
                f.write(b'\x1d\x56\x00')  # Comando GS V 0
                temp_file = f.name
            
            # Enviar comando
            subprocess.run(['lp', '-d', self.printer_name, '-o', 'raw', temp_file], 
                         capture_output=True)
            os.unlink(temp_file)
        except Exception as e:
            print(f"Erro no corte: {e}")
    
    def _formatar_cupom(self, data):
      """Usa a classe FormatadorCupom da pasta PRINT"""
      formatador = FormatadorCupom()
      return formatador.formatar_cupom(data)
    
    def _formatar_comanda(self, data):
      """Formata conteúdo da comanda (versão simples)"""
      linhas = []
      
      # Cabeçalho
      linhas.append("=" * 40)
      linhas.append("      COXINHAS PREMIUM CAFÉ")
      linhas.append("=" * 40)
      linhas.append("")
      
      # Dados da comanda
      linhas.append(f"Comanda: #{data['id']}")
      linhas.append(f"Mesa: {data['mesa']}")
      linhas.append(f"Data: {data['data']}")
      linhas.append("-" * 40)
      
      # Itens
      total = 0
      for item in data['itens']:
          linhas.append(f"{item['nome']}")
          linhas.append(f"{item['qtd']} x R$ {item['preco']:.2f} = R$ {item['subtotal']:.2f}")
          linhas.append("")
          total += item['subtotal']
      
      # Total
      linhas.append("-" * 40)
      linhas.append(f"TOTAL: R$ {total:.2f}")
      linhas.append("=" * 40)
      linhas.append("")
      
      # Espaçamento
      for i in range(5):
          linhas.append("")
      
      return "\n".join(linhas)
    
    def testar_corte(self):
        """Testa diferentes comandos de corte"""
        print("🧪 Testando comandos de corte...")
        
        comandos = {
            'ESC i': b'\x1B\x69',
            'ESC m': b'\x1B\x6D', 
            'GS V 0': b'\x1D\x56\x00',
            'GS V 1': b'\x1D\x56\x01',
            'FF': b'\x0C'
        }
        
        for nome, comando in comandos.items():
            try:
                print(f"Tentando: {nome}")
                with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
                    f.write(b"TESTE DE CORTE\n")
                    f.write(comando)
                    temp_file = f.name
                
                result = subprocess.run([
                    'lp', '-d', self.printer_name, '-o', 'raw', temp_file
                ], capture_output=True, text=True)
                
                print(f"Resultado: {result.returncode}")
                if result.stderr:
                    print(f"Erro: {result.stderr}")
                    
                os.unlink(temp_file)
                
            except Exception as e:
                print(f"Erro em {nome}: {e}")

    def imprimir_cupom(self, cupom_data):
        """Imprime cupom fiscal/recibo na impressora térmica"""
        try:
            # Gerar conteúdo formatado para cupom
            conteudo = self._formatar_cupom(cupom_data)
            
            # Criar arquivo temporário
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(conteudo)
                temp_file = f.name
            
            # Imprimir o arquivo
            result = subprocess.run([
                'lp', '-d', self.printer_name, temp_file
            ], capture_output=True, text=True)
            
            # Aguardar impressão e fazer corte
            if result.returncode == 0:
                import time
                time.sleep(1)
                self.enviar_corte()
            
            # Limpar arquivo
            os.unlink(temp_file)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Erro na impressão do cupom: {e}")
            return False

    def _formatar_cupom(self, data):
      """Usa a classe FormatadorCupom da pasta PRINT"""
      formatador = FormatadorCupom()
      return formatador.formatar_cupom(data)
    
# Instância global
epson_service = EpsonService()
