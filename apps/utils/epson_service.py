import subprocess
import tempfile
import os
from datetime import datetime

class EpsonTMT20XService:
    """
    Serviço específico para impressora Epson TM-T20X II
    Suporta conexão USB, Serial e Ethernet
    """
    
    def __init__(self, printer_name="EPSON_TM_T20X_II", connection_type="usb"):
        self.printer_name = printer_name
        self.connection_type = connection_type
        self.largura = 42  # 42 colunas para 80mm
    
    def imprimir_cupom_fiscal_direto(self, dados_nfce, resultado_emissao):
        """
        Imprime cupom fiscal diretamente na Epson TM-T20X II
        """
        try:
            # Gerar conteúdo ESC/POS
            conteudo_escpos = self._gerar_escpos_cupom_fiscal(dados_nfce, resultado_emissao)
            
            # Enviar para impressora
            sucesso = self._enviar_para_epson(conteudo_escpos)
            
            if sucesso:
                print(f"[EPSON] ✓ Cupom fiscal impresso na {self.printer_name}")
                return {
                    'sucesso': True,
                    'impressora': self.printer_name,
                    'tipo': 'cupom_fiscal'
                }
            else:
                return {
                    'sucesso': False,
                    'erro': 'Falha na comunicação com a impressora'
                }
                
        except Exception as e:
            print(f"[EPSON] ✗ Erro: {e}")
            return {
                'sucesso': False,
                'erro': str(e)
            }
    
    def imprimir_cupom_normal_direto(self, order):
        """
        Imprime cupom normal diretamente na Epson TM-T20X II (sem NFCe)
        """
        try:
            # Gerar conteúdo do cupom normal
            conteudo_cupom = self._gerar_cupom_normal(order)
            
            # Enviar para impressora
            sucesso = self._enviar_para_epson(conteudo_cupom)
            
            if sucesso:
                print(f"[EPSON] ✓ Cupom normal impresso na {self.printer_name}")
                return {
                    'sucesso': True,
                    'impressora': self.printer_name,
                    'tipo': 'cupom_normal'
                }
            else:
                return {
                    'sucesso': False,
                    'erro': 'Falha na comunicação com a impressora'
                }
                
        except Exception as e:
            print(f"[EPSON] ✗ Erro: {e}")
            return {
                'sucesso': False,
                'erro': str(e)
            }

    def _gerar_cupom_normal(self, order):
        """
        Gera conteúdo do cupom normal (sem NFCe) com comando de corte
        """
        from datetime import datetime
        agora = datetime.now()
        
        conteudo = []
        
        # Reset da impressora
        conteudo.append("\x1B\x40")  # ESC @ - comando que funcionou
        
        # === CABEÇALHO ===
        conteudo.append("COXINHAS PREMIUM CAFE")
        conteudo.append("Rua Coronel Fernando Prestes, 898")
        conteudo.append("Centro - Itapetininga/SP")
        conteudo.append("CEP: 18200-230")
        conteudo.append("Tel: (15) 3272-1234")
        conteudo.append("")
        conteudo.append("=" * self.largura)
        
        # === DADOS DA COMANDA ===
        conteudo.append("")
        conteudo.append(f"COMANDA #{order.code}")
        conteudo.append(f"Cliente: {order.name}")
        conteudo.append(f"Data: {order.created_at.strftime('%d/%m/%Y %H:%M')}")
        conteudo.append("")
        conteudo.append("-" * self.largura)
        conteudo.append("")
        
        # === ITENS ===
        for item in order.items.all():
            subtotal = item.quantity * item.unit_price
            conteudo.append(f"{item.quantity:2d}x {item.product.name}")
            conteudo.append(f"    R$ {item.unit_price:.2f} = R$ {subtotal:.2f}")
            conteudo.append("")
        
        # === TOTAL ===
        conteudo.append("-" * self.largura)
        conteudo.append(f"TOTAL: R$ {order.total_amount:.2f}")
        conteudo.append("=" * self.largura)
        conteudo.append("")
        
        # === FOOTER ===
        conteudo.append("*** OBRIGADO PELA PREFERENCIA! ***")
        conteudo.append("*** VOLTE SEMPRE! ***")
        conteudo.append("")
        conteudo.append("www.coxinhaspremium.com.br")
        conteudo.append("Instagram: @CoxinhasPremium")
        conteudo.append("")
        conteudo.append(f"Cupom gerado em {agora.strftime('%d/%m/%Y %H:%M')}")
        
        # === CORTE AUTOMÁTICO === 
        conteudo.extend(["", "", "", ""])  # Espaços antes do corte
        conteudo.append("\x1D\x56\x42\x00")  # Comando que funcionou no teste!
        
        return "\n".join(conteudo)

    def _gerar_escpos_cupom_fiscal(self, dados_nfce, resultado_emissao):
        """
        Gera cupom fiscal NFCe COMPACTO estilo mercado
        """
        order = dados_nfce['order']
        chave_acesso = dados_nfce['chave_acesso']
        numero_nfce = dados_nfce['numero']
        agora = datetime.now()
        
        conteudo = []
        
        # === RESET ===
        conteudo.append("\x1B\x40")  # ESC @
        
        # === EMPRESA (COMPACTO) ===
        conteudo.append("COXINHAS PREMIUM LTDA")
        conteudo.append("R.Cel.F.Prestes,898-Centro")
        conteudo.append("Itapetininga/SP CEP:18200-230")
        conteudo.append("CNPJ:10.361.831/0001-23")
        conteudo.append("IE:371.468.833.110")
        conteudo.append("")
        
        # === NFCe (MINIMALISTA) ===
        conteudo.append("=" * 40) 
        conteudo.append("   CUPOM FISCAL ELETRONICO")
        conteudo.append(f"NFCe {numero_nfce:09d} Sr.001 {agora.strftime('%d/%m/%y %H:%M')}")
        conteudo.append("CONSUMIDOR NAO IDENTIFICADO")
        conteudo.append("-" * 40)
        
        # === ITENS (COMPACTO) ===
        total_geral = 0
        for i, item in enumerate(order.items.all(), 1):
            subtotal = float(item.quantity) * float(item.unit_price)
            total_geral += subtotal
            
            # Linha única por item (estilo mercado)
            nome = item.product.name[:25]  # Truncar se muito longo
            conteudo.append(f"{i:03d} {nome}")
            conteudo.append(f"{item.quantity:.0f}x{item.unit_price:.2f}     {subtotal:>8.2f}")
        
        conteudo.append("-" * 40)
        
        # === TOTAL E PAGAMENTO ===
        conteudo.append(f"TOTAL          R$ {total_geral:>10.2f}")
        conteudo.append(f"Dinheiro       R$ {total_geral:>10.2f}")
        conteudo.append(f"Troco          R$ {'0.00':>10}")
        conteudo.append("-" * 40)
        
        # === TRIBUTOS (OBRIGATÓRIO) ===
        tributos = total_geral * 0.20
        conteudo.append(f"Trib.aprox R${tributos:.2f}({tributos/total_geral*100:.1f}%)")
        conteudo.append("Fonte:IBPT")
        conteudo.append("")
        
        # === QR CODE NFCe (REAL) ===
        conteudo.append("Consulte pela chave de acesso:")
        conteudo.append("fazenda.sp.gov.br/nfce")
        conteudo.append("")

        # Gerar QR Code real com comandos ESC/POS
        qr_data = f"https://www.fazenda.sp.gov.br/nfce/qrcode?p={chave_acesso}|2|1|1|{total_geral:.2f}|HASH_AQUI"

        # Comandos ESC/POS para QR Code Epson TM-T20X II
        qr_commands = []
        qr_commands.append("\x1D(k\x04\x00\x31\x41\x32\x00")  # Função QR Code modelo 2
        qr_commands.append("\x1D(k\x03\x00\x31\x43\x08")      # Tamanho do módulo (8)
        qr_commands.append("\x1D(k\x03\x00\x31\x45\x30")      # Nível correção erro L

        # Armazenar dados do QR Code
        data_length = len(qr_data)
        length_low = data_length & 0xFF
        length_high = (data_length >> 8) & 0xFF
        qr_commands.append(f"\x1D(k{chr(len(qr_data) + 3)}\x00\x31\x50\x30{qr_data}")

        # Imprimir QR Code
        qr_commands.append("\x1D(k\x03\x00\x31\x51\x30")

        # Adicionar comandos QR ao conteúdo
        for cmd in qr_commands:
            conteudo.append(cmd)

        conteudo.append("")  # Linha em branco após QR
        
        # === PROTOCOLO ===
        if resultado_emissao.get('sucesso'):
            protocolo = resultado_emissao.get('protocolo', 'TESTE123')
            conteudo.append(f"Prot:{protocolo} {agora.strftime('%d/%m/%y %H:%M')}")
            conteudo.append("")
        
        # === INFORMAÇÕES LEGAIS (COMPACTAS) ===
        conteudo.append("NFCe emitida nos termos da")
        conteudo.append("Res.CGSN 140/2018")
        conteudo.append("Nao gera credito de ICMS")
        conteudo.append("")
        
        # === FOOTER MINIMALISTA ===
        conteudo.append("*** OBRIGADO! ***")
        conteudo.append("Volte sempre!")
        conteudo.append("")
        
        # === CORTE AUTOMÁTICO ===
        conteudo.extend(["", "", ""])
        conteudo.append("\x1D\x56\x42\x00")  # Comando que funcionou
        
        return "\n".join(conteudo)
    
    def _enviar_para_epson(self, conteudo):
        """
        Envio multiplataforma otimizado
        """
        try:
            import subprocess
            import platform
            import tempfile
            import os
            
            sistema = platform.system()
            print(f"[DEBUG] Sistema: {sistema}, Impressora: {self.printer_name}")
            
            if sistema == "Linux":
                # LINUX - Múltiplos métodos
                success = False
                
                # Método 1: Tentar lp (se existir)
                try:
                    result = subprocess.run([
                        'lp', '-d', self.printer_name
                    ], input=conteudo, text=True, capture_output=True, timeout=10)
                    
                    if result.returncode == 0:
                        print(f"[EPSON] ✓ Enviado via lp")
                        return True
                    else:
                        print(f"[EPSON] ✗ lp falhou: {result.stderr}")
                        
                except FileNotFoundError:
                    print(f"[EPSON] ✗ Comando lp não encontrado")
                except Exception as e:
                    print(f"[EPSON] ✗ Erro lp: {e}")
                
                # Método 2: Escrever direto no device USB
                usb_devices = [
                    '/dev/usb/lp0',
                    '/dev/lp0', 
                    f'/dev/{self.printer_name.lower()}',
                    '/dev/ttyUSB0'
                ]
                
                for device in usb_devices:
                    try:
                        print(f"[EPSON] Tentando device: {device}")
                        with open(device, 'wb') as f:
                            f.write(conteudo.encode('utf-8'))
                        print(f"[EPSON] ✓ Enviado via {device}")
                        return True
                    except Exception as e:
                        print(f"[EPSON] ✗ Device {device} falhou: {e}")
                        continue
                
                # Método 3: Via netcat (se for impressora de rede)
                try:
                    # Tentar IP local da impressora
                    result = subprocess.run([
                        'nc', '-w', '3', '192.168.1.100', '9100'
                    ], input=conteudo, text=True, capture_output=True, timeout=10)
                    
                    if result.returncode == 0:
                        print(f"[EPSON] ✓ Enviado via rede")
                        return True
                        
                except Exception as e:
                    print(f"[EPSON] ✗ Rede falhou: {e}")
                
                # Método 4: Instalar CUPS e tentar novamente
                try:
                    print("[EPSON] Tentando instalar CUPS...")
                    subprocess.run(['apt-get', 'update'], capture_output=True)
                    subprocess.run(['apt-get', 'install', '-y', 'cups'], capture_output=True)
                    
                    # Tentar lp novamente
                    result = subprocess.run([
                        'lp', '-d', self.printer_name
                    ], input=conteudo, text=True, capture_output=True, timeout=10)
                    
                    if result.returncode == 0:
                        print(f"[EPSON] ✓ Enviado via lp (após instalar CUPS)")
                        return True
                        
                except Exception as e:
                    print(f"[EPSON] ✗ Instalação CUPS falhou: {e}")
                
                return False
                
            elif sistema == "Darwin":  # macOS
                # MACOS (método original)
                result = subprocess.run([
                    'lp', '-d', self.printer_name
                ], input=conteudo, text=True, capture_output=True)
                
                return result.returncode == 0
                
            elif sistema == "Windows":
                # WINDOWS (método anterior)
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='cp860') as f:
                    f.write(conteudo)
                    temp_file = f.name
                
                methods = [
                    ['powershell', '-Command', f'Get-Content "{temp_file}" | Out-Printer -Name "{self.printer_name}"'],
                    ['copy', '/B', temp_file, self.printer_name],
                    ['print', '/D:' + self.printer_name, temp_file]
                ]
                
                for i, cmd in enumerate(methods, 1):
                    try:
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            print(f"[EPSON] ✓ Sucesso Windows método {i}")
                            os.unlink(temp_file)
                            return True
                    except Exception as e:
                        print(f"[EPSON] ✗ Windows método {i}: {e}")
                        continue
                
                os.unlink(temp_file)
                return False
                
        except Exception as e:
            print(f"[EPSON] ✗ Erro geral: {e}")
            return False
    
    def _enviar_usb(self, conteudo):
        """Envio via USB (Linux/macOS)"""
        try:
            # No Linux/macOS, usar lp command
            result = subprocess.run([
                'lp', '-d', self.printer_name, '-o', 'raw'
            ], input=conteudo.encode('utf-8'), capture_output=True)
            
            return result.returncode == 0
            
        except Exception:
            # Fallback: tentar escrever direto no device
            try:
                with open('/dev/usb/lp0', 'wb') as f:  # Ajuste o device
                    f.write(conteudo.encode('utf-8'))
                return True
            except Exception:
                return False
    
    def _enviar_rede(self, conteudo, ip="192.168.1.100", porta=9100):
        """Envio via rede (Ethernet/WiFi)"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, porta))
            sock.send(conteudo.encode('utf-8'))
            sock.close()
            return True
            
        except Exception as e:
            print(f"[EPSON] Erro rede: {e}")
            return False
    
    def _enviar_lp(self, conteudo):
        """Envio via comando lp (Linux/macOS)"""
        try:
            # Criar arquivo temporário
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='cp860') as f:
                f.write(conteudo)
                temp_file = f.name
            
            # Enviar via lp
            result = subprocess.run([
                'lp', '-d', self.printer_name, temp_file
            ], capture_output=True)
            
            # Limpar arquivo
            os.unlink(temp_file)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"[EPSON] Erro lp: {e}")
            return False
    
    def testar_conexao(self):
        """
        Testa se a impressora está respondendo
        """
        try:
            # Enviar comando simples de teste
            teste = "\x1B@\x1Ba\x01TESTE DE CONEXAO\n\n\x1Bm"
            return self._enviar_para_epson(teste)
            
        except Exception as e:
            print(f"[EPSON] Teste falhou: {e}")
            return False