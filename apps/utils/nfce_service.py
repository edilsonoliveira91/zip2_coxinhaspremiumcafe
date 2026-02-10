import os
import tempfile
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
import hashlib
import base64

class NFCeService:
    """Serviço para emissão de NFCe usando certificado digital"""
    
    def __init__(self, empresa):
        self.empresa = empresa
        
        # Verifica certificado de forma segura
        try:
            if hasattr(empresa, 'certificado') and empresa.certificado.exists():
                self.certificado = empresa.certificado.first()
            else:
                self.certificado = None
        except:
            self.certificado = None
            
        self.modo_simulacao = not self.certificado
        
        if self.modo_simulacao:
            print("[INFO] Modo simulação ativado - Certificado não configurado")
    
    def emitir_nfce(self, order, cpf_cliente=None):
        """Emite NFCe"""
        try:
            # Gera próximo número
            numero_nfce = self.empresa.get_proximo_numero_nfce()
            
            # Monta dados da NFCe
            dados_nfce = self._montar_dados_nfce(order, numero_nfce, cpf_cliente)
            
            # Se tem certificado, tenta emissão real, senão simula
            if self.modo_simulacao:
                emissao_ok = self._simular_emissao_nfce(dados_nfce)
            else:
                # Aqui seria a emissão real com certificado
                emissao_ok = self._simular_emissao_nfce(dados_nfce)  # Por enquanto simula mesmo com certificado
            
            if emissao_ok:
                # Incrementa número
                self.empresa.proximo_numero_nfce = numero_nfce + 1
                self.empresa.save()
                
                # Gera chave de acesso
                chave_acesso = self._gerar_chave_acesso(numero_nfce)
                
                return {
                    'success': True,
                    'dados_nfce': {
                        'numero': numero_nfce,
                        'serie': self.empresa.serie_nfce,
                        'chave_acesso': chave_acesso,
                        'protocolo': f"PRO{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        'data_emissao': datetime.now(),
                        'valor_total': order.total_amount,
                        'cpf_cliente': cpf_cliente,
                        'modo_simulacao': self.modo_simulacao
                    }
                }
            else:
                return {
                    'success': False,
                    'erro': 'Falha na comunicação com a SEFAZ'
                }
        
        except Exception as e:
            return {
                'success': False,
                'erro': f"Erro na emissão: {str(e)}"
            }
    
    def _montar_dados_nfce(self, order, numero, cpf_cliente=None):
        """Monta estrutura de dados da NFCe"""
        return {
            'numero': numero,
            'serie': self.empresa.serie_nfce,
            'data_emissao': datetime.now(),
            'emissor': {
                'cnpj': self.empresa.cnpj.replace('.', '').replace('/', '').replace('-', ''),
                'razao_social': self.empresa.razao_social,
                'nome_fantasia': self.empresa.nome_fantasia or self.empresa.razao_social,
                'endereco': self.empresa.logradouro,
                'numero': self.empresa.numero,
                'bairro': self.empresa.bairro,
                'cidade': self.empresa.cidade,
                'uf': self.empresa.uf,
                'cep': self.empresa.cep.replace('-', ''),
                'inscricao_estadual': self.empresa.inscricao_estadual or ''
            },
            'cliente': {
                'cpf': cpf_cliente.replace('.', '').replace('-', '') if cpf_cliente else None,
                'nome': 'CONSUMIDOR' if cpf_cliente else 'CONSUMIDOR NAO IDENTIFICADO'
            },
            'itens': [
                {
                    'codigo': str(item.product.id),
                    'descricao': item.product.name,
                    'quantidade': float(item.quantity),
                    'valor_unitario': float(item.unit_price),
                    'valor_total': float(item.quantity * item.unit_price),
                    'cfop': '5102',  # Venda no estado
                    'ncm': '00000000'  # Definir NCM adequado
                }
                for item in order.items.all()
            ],
            'totais': {
                'valor_total': float(order.total_amount)
            },
            'csc': {
                'id': self.empresa.csc_id,
                'codigo': self.empresa.csc_codigo
            }
        }
    
    def _simular_emissao_nfce(self, dados_nfce):
        """
        Simula emissão da NFCe
        TODO: Implementar integração real com SEFAZ
        """
        # Por enquanto retorna sucesso para desenvolvimento
        print(f"[SIMULAÇÃO] Emitindo NFCe #{dados_nfce['numero']}")
        print(f"[SIMULAÇÃO] Empresa: {dados_nfce['emissor']['razao_social']}")
        print(f"[SIMULAÇÃO] Cliente: {dados_nfce['cliente']['nome']}")
        if dados_nfce['cliente']['cpf']:
            print(f"[SIMULAÇÃO] CPF: {dados_nfce['cliente']['cpf']}")
        print(f"[SIMULAÇÃO] Valor: R$ {dados_nfce['totais']['valor_total']:.2f}")
        print("[SIMULAÇÃO] ✓ NFCe autorizada com sucesso!")
        
        return True
    
    def _gerar_chave_acesso(self, numero):
        """Gera chave de acesso da NFCe"""
        # Formato: AAMM + CNPJ + Modelo + Serie + Numero + Tipo_Emissao + Código_Numérico + DV
        aamm = datetime.now().strftime('%y%m')
        cnpj = self.empresa.cnpj.replace('.', '').replace('/', '').replace('-', '')
        modelo = '65'  # NFCe
        serie = f"{self.empresa.serie_nfce:03d}"
        numero_formatado = f"{numero:09d}"
        tipo_emissao = '1'  # Normal
        codigo_numerico = '12345678'  # Código aleatório (implementar geração real)
        
        # Calcula dígito verificador (simplificado)
        chave_base = f"{aamm}{cnpj}{modelo}{serie}{numero_formatado}{tipo_emissao}{codigo_numerico}"
        dv = str(sum(int(d) for d in chave_base) % 10)
        
        return chave_base + dv
    
    def _preparar_certificado(self):
        """Prepara certificado PFX para uso na comunicação com SEFAZ"""
        try:
            # Lê o arquivo PFX
            with open(self.certificado.arquivo_pfx.path, 'rb') as f:
                pfx_data = f.read()
            
            # Extrai certificado e chave privada
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                pfx_data, 
                self.certificado.senha_pfx.encode('utf-8')
            )
            
            # Salva em arquivos temporários
            cert_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
            key_file = tempfile.NamedTemporaryFile(delete=False, suffix='.key')
            
            # Escreve certificado
            cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))
            cert_file.close()
            
            # Escreve chave privada
            key_file.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            key_file.close()
            
            return cert_file.name, key_file.name
            
        except Exception as e:
            raise ValueError(f"Erro ao processar certificado PFX: {str(e)}")
    
    def _limpar_certificados_temporarios(self, cert_path, key_path):
        """Remove arquivos temporários do certificado"""
        try:
            if cert_path and os.path.exists(cert_path):
                os.unlink(cert_path)
            if key_path and os.path.exists(key_path):
                os.unlink(key_path)
        except:
            pass
    
    def _gerar_xml_nfce(self, dados_nfce):
        """Gera XML da NFCe (estrutura básica)"""
        # TODO: Implementar geração completa do XML conforme layout da SEFAZ
        xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
    <NFe>
        <infNFe Id="NFe{dados_nfce['chave_acesso']}">
            <ide>
                <cUF>{self._get_codigo_uf()}</cUF>
                <cNF>{dados_nfce['numero']}</cNF>
                <natOp>VENDA</natOp>
                <mod>65</mod>
                <serie>{dados_nfce['serie']}</serie>
                <nNF>{dados_nfce['numero']}</nNF>
                <dhEmi>{dados_nfce['data_emissao'].isoformat()}</dhEmi>
                <tpNF>1</tpNF>
                <idDest>1</idDest>
                <cMunFG>{self._get_codigo_municipio()}</cMunFG>
                <tpImp>4</tpImp>
                <tpEmis>1</tpEmis>
                <cDV>{dados_nfce['chave_acesso'][-1]}</cDV>
                <tpAmb>{self.empresa.ambiente_nfce}</tpAmb>
                <finNFe>1</finNFe>
                <indFinal>1</indFinal>
                <indPres>1</indPres>
            </ide>
            <emit>
                <CNPJ>{dados_nfce['emissor']['cnpj']}</CNPJ>
                <xNome>{dados_nfce['emissor']['razao_social']}</xNome>
                <xFant>{dados_nfce['emissor']['nome_fantasia']}</xFant>
                <enderEmit>
                    <xLgr>{dados_nfce['emissor']['endereco']}</xLgr>
                    <nro>{dados_nfce['emissor']['numero']}</nro>
                    <xBairro>{dados_nfce['emissor']['bairro']}</xBairro>
                    <cMun>{self._get_codigo_municipio()}</cMun>
                    <xMun>{dados_nfce['emissor']['cidade']}</xMun>
                    <UF>{dados_nfce['emissor']['uf']}</UF>
                    <CEP>{dados_nfce['emissor']['cep']}</CEP>
                    <cPais>1058</cPais>
                    <xPais>Brasil</xPais>
                </enderEmit>
                <IE>{dados_nfce['emissor']['inscricao_estadual']}</IE>
                <CRT>1</CRT>
            </emit>
            <!-- Aqui viriam os itens, totais, etc -->
        </infNFe>
    </NFe>
</nfeProc>"""
        return xml_template
    
    def _get_codigo_uf(self):
        """Retorna código IBGE da UF"""
        codigos_uf = {
            'SP': '35', 'RJ': '33', 'MG': '31', 'RS': '43', 'PR': '41',
            'SC': '42', 'GO': '52', 'MT': '51', 'MS': '50', 'BA': '29',
            'PE': '26', 'CE': '23', 'MA': '21', 'PA': '15', 'PB': '25',
            'RN': '24', 'AL': '27', 'SE': '28', 'PI': '22', 'TO': '17',
            'AC': '12', 'AM': '13', 'AP': '16', 'RO': '11', 'RR': '14',
            'DF': '53', 'ES': '32'
        }
        return codigos_uf.get(self.empresa.uf, '35')
    
    def _get_codigo_municipio(self):
        """Retorna código IBGE do município (simplificado)"""
        # TODO: Implementar busca real do código IBGE
        return '3550308'  # São Paulo (exemplo)
    
    def enviar_para_sefaz(self, xml_nfce):
        """
        Envia NFCe para SEFAZ (implementação futura)
        TODO: Implementar comunicação real com SEFAZ
        """
        # URLs dos webservices da SEFAZ por UF (exemplo SP)
        urls_sefaz = {
            'homologacao': {
                'autorizacao': 'https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx',
                'consulta': 'https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeconsultaprotocolo4.asmx'
            },
            'producao': {
                'autorizacao': 'https://nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx',
                'consulta': 'https://nfce.fazenda.sp.gov.br/ws/nfeconsultaprotocolo4.asmx'
            }
        }
        
        ambiente = 'homologacao' if self.empresa.ambiente_nfce == '2' else 'producao'
        url_servico = urls_sefaz[ambiente]['autorizacao']
        
        print(f"[INFO] Enviaria para SEFAZ: {url_servico}")
        # Aqui seria implementada a comunicação SOAP com a SEFAZ
        
    def consultar_status_nfce(self, chave_acesso):
        """
        Consulta status de uma NFCe na SEFAZ (implementação futura)
        """
        # TODO: Implementar consulta de status
        print(f"[INFO] Consultaria status da NFCe: {chave_acesso}")
        
    def cancelar_nfce(self, chave_acesso, justificativa):
        """
        Cancela uma NFCe (implementação futura)
        """
        # TODO: Implementar cancelamento
        print(f"[INFO] Cancelaria NFCe: {chave_acesso} - Motivo: {justificativa}")
        
    def validar_certificado(self):
        """Valida se o certificado está válido e não expirou"""
        try:
            with open(self.certificado.arquivo_pfx.path, 'rb') as f:
                pfx_data = f.read()
            
            _, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data, 
                self.certificado.senha_pfx.encode('utf-8')
            )
            
            # Verifica se o certificado não expirou
            if certificate.not_valid_after < datetime.now():
                return {
                    'valido': False,
                    'erro': f'Certificado expirou em {certificate.not_valid_after.strftime("%d/%m/%Y")}'
                }
            
            return {
                'valido': True,
                'valido_ate': certificate.not_valid_after
            }
            
        except Exception as e:
            return {
                'valido': False,
                'erro': f'Erro ao validar certificado: {str(e)}'
            }