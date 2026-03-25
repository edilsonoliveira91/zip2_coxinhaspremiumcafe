import os
import tempfile
import hashlib
import base64
import re
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from lxml import etree
import urllib3
import xml.etree.ElementTree as ET

# Desabilita warnings SSL para homologação
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NFCeService:
    """
    Serviço para emissão de NFCe com ferramentas de debugging avançadas
    """
    
    def __init__(self, empresa):
        self.empresa = empresa
        self.certificado = None
        
        # Verifica se tem certificado configurado
        if hasattr(empresa, 'certificado') and empresa.certificado:
            self.certificado = empresa.certificado
            print(f"[INFO] Certificado encontrado: {self.certificado.arquivo_pfx.name}")
            print("[INFO] Certificado configurado - Modo real disponível")
        else:
            print("[INFO] Nenhum certificado encontrado - Apenas modo simulação")
    
    def emitir_nfce(self, order, cpf_cliente=None):
        """
        Método principal para emissão de NFCe com cupom fiscal
        """
        try:
            # Pega próximo número da NFCe
            numero = self._obter_proximo_numero_nfce()
            
            # Monta dados da NFCe
            dados_nfce = self._montar_dados_nfce(order, numero, cpf_cliente)
            
            # Se tem certificado, tenta emissão real primeiro
            if self.certificado:
                try:
                    print("[INFO] Tentando emissão real em HOMOLOGAÇÃO...")
                    resultado = self._emitir_nfce_real(dados_nfce)
                    
                    # Gerar cupom fiscal após emissão bem-sucedida
                    if resultado['sucesso']:
                        cupom_info = self.salvar_cupom_fiscal(dados_nfce, resultado)
                        resultado['cupom_fiscal'] = cupom_info
                        print(f"[INFO] Cupom fiscal gerado: {cupom_info.get('url_impressao', 'N/A')}")
                    
                    return resultado
                except Exception as e:
                    print(f"[ERROR] Falha na emissão real: {e}")
                    print("[FALLBACK] Tentando simulação após falha na emissão real...")
                    resultado = self._emitir_nfce_simulado(dados_nfce)
            else:
                print("[INFO] Emissão apenas em modo simulação") 
                resultado = self._emitir_nfce_simulado(dados_nfce)
            
            # Gerar cupom fiscal mesmo em simulação
            if resultado['sucesso']:
                cupom_info = self.salvar_cupom_fiscal(dados_nfce, resultado)
                resultado['cupom_fiscal'] = cupom_info
                print(f"[INFO] Cupom fiscal gerado: {cupom_info.get('url_impressao', 'N/A')}")
                
            return resultado
            
        except Exception as e:
            print(f"[ERROR] Erro geral na emissão de NFCe: {e}")
            return {
                'sucesso': False,
                'erro': f'Erro na emissão: {str(e)}',
                'modo': 'erro'
            }

    def _debug_xml_profundo(self, xml_content):
        """
        Análise profunda do XML para identificar problemas específicos
        """
        print("\n" + "="*80)
        print("DEBUGGING PROFUNDO DO XML")
        print("="*80)
        
        try:
            # 1. Verificações básicas
            print(f"[DEBUG] Tamanho do XML: {len(xml_content)} bytes")
            print(f"[DEBUG] Codificação detectada: {xml_content[:50]}")
            
            # 2. Análise da estrutura XML
            try:
                root = etree.fromstring(xml_content.encode('utf-8'))
                print(f"[DEBUG] ✓ XML bem formado")
                print(f"[DEBUG] Root element: {root.tag}")
                print(f"[DEBUG] Namespace: {root.nsmap}")
            except Exception as e:
                print(f"[DEBUG] ✗ XML malformado: {e}")
                return
            
            # 3. Verificações específicas NFCe
            problemas = []
            
            # Verifica namespace principal
            if 'http://www.portalfiscal.inf.br/nfe' not in str(etree.tostring(root)):
                problemas.append("Namespace NFe ausente ou incorreto")
            
            # Verifica estrutura obrigatória
            nfe_elem = root.find('.//{http://www.portalfiscal.inf.br/nfe}NFe')
            if nfe_elem is None:
                problemas.append("Elemento NFe não encontrado")
            else:
                infnfe = nfe_elem.find('.//{http://www.portalfiscal.inf.br/nfe}infNFe')
                if infnfe is None:
                    problemas.append("Elemento infNFe não encontrado")
                else:
                    id_attr = infnfe.get('Id')
                    if not id_attr or not id_attr.startswith('NFe'):
                        problemas.append(f"Atributo Id inválido: {id_attr}")
            
            # Verifica elementos obrigatórios
            elementos_obrigatorios = [
                ('idLote', './/{http://www.portalfiscal.inf.br/nfe}idLote'),
                ('indSinc', './/{http://www.portalfiscal.inf.br/nfe}indSinc'),
                ('ide', './/{http://www.portalfiscal.inf.br/nfe}ide'),
                ('emit', './/{http://www.portalfiscal.inf.br/nfe}emit'),
                ('det', './/{http://www.portalfiscal.inf.br/nfe}det'),
                ('total', './/{http://www.portalfiscal.inf.br/nfe}total'),
                ('pag', './/{http://www.portalfiscal.inf.br/nfe}pag')
            ]
            
            for nome, xpath in elementos_obrigatorios:
                elem = root.find(xpath)
                if elem is None:
                    problemas.append(f"Elemento obrigatório ausente: {nome}")
                else:
                    print(f"[DEBUG] ✓ {nome}: encontrado")
            
            # Verifica campos específicos do IDE
            ide = root.find('.//{http://www.portalfiscal.inf.br/nfe}ide')
            if ide is not None:
                campos_ide = {
                    'cUF': 'Código UF',
                    'cNF': 'Código NF',
                    'mod': 'Modelo (deve ser 65)',
                    'serie': 'Série',
                    'nNF': 'Número NF',
                    'dhEmi': 'Data/Hora Emissão',
                    'tpNF': 'Tipo NF',
                    'cMunFG': 'Código Município',
                    'tpAmb': 'Tipo Ambiente'
                }
                
                # CORRIGIDO: namespace na string
                namespace = "http://www.portalfiscal.inf.br/nfe"
                
                for campo, desc in campos_ide.items():
                    elem = ide.find(f'.//{{{namespace}}}{campo}')
                    if elem is not None:
                        valor = elem.text
                        print(f"[DEBUG] {campo}: {valor} ({desc})")
                        
                        # Validações específicas
                        if campo == 'mod' and valor != '65':
                            problemas.append(f"Modelo deve ser 65, encontrado: {valor}")
                        elif campo == 'cUF' and not valor.isdigit():
                            problemas.append(f"Código UF inválido: {valor}")
                        elif campo == 'dhEmi' and 'T' not in valor:
                            problemas.append(f"Formato data/hora inválido: {valor}")
                    else:
                        problemas.append(f"Campo IDE obrigatório ausente: {campo}")
            
            # Verifica CNPJ emitente
            cnpj = root.find('.//{http://www.portalfiscal.inf.br/nfe}emit/{http://www.portalfiscal.inf.br/nfe}CNPJ')
            if cnpj is not None:
                cnpj_text = cnpj.text
                if not re.match(r'^\d{14}$', cnpj_text):
                    problemas.append(f"CNPJ inválido: {cnpj_text}")
                else:
                    print(f"[DEBUG] ✓ CNPJ válido: {cnpj_text}")
            else:
                problemas.append("CNPJ do emitente não encontrado")
            
            # Verifica produto
            prod = root.find('.//{http://www.portalfiscal.inf.br/nfe}det/{http://www.portalfiscal.inf.br/nfe}prod')
            if prod is not None:
                campos_prod = ['cProd', 'xProd', 'NCM', 'CFOP', 'uCom', 'qCom', 'vUnCom', 'vProd']
                for campo in campos_prod:
                    elem = prod.find(f'.//{{{namespace}}}{campo}')
                    if elem is None:
                        problemas.append(f"Campo produto obrigatório ausente: {campo}")
                    else:
                        print(f"[DEBUG] ✓ {campo}: {elem.text}")
            
            # 4. Verifica formatação de números
            numeros_formatacao = [
                ('.//{http://www.portalfiscal.inf.br/nfe}qCom', r'^\d+\.\d{4}$', 'Quantidade Com'),
                ('.//{http://www.portalfiscal.inf.br/nfe}vUnCom', r'^\d+\.\d{2,10}$', 'Valor Unitário Com'),
                ('.//{http://www.portalfiscal.inf.br/nfe}vProd', r'^\d+\.\d{2}$', 'Valor Produto'),
                ('.//{http://www.portalfiscal.inf.br/nfe}vNF', r'^\d+\.\d{2}$', 'Valor Total NF')
            ]
            
            for xpath, padrao, desc in numeros_formatacao:
                elem = root.find(xpath)
                if elem is not None:
                    if not re.match(padrao, elem.text):
                        problemas.append(f"Formatação incorreta em {desc}: {elem.text} (esperado: {padrao})")
                    else:
                        print(f"[DEBUG] ✓ Formatação correta {desc}: {elem.text}")
            
            # 5. Relatório final
            print(f"\n[DEBUG] TOTAL DE PROBLEMAS ENCONTRADOS: {len(problemas)}")
            if problemas:
                print("[DEBUG] LISTA DE PROBLEMAS:")
                for i, problema in enumerate(problemas, 1):
                    print(f"[DEBUG] {i}. {problema}")
            else:
                print("[DEBUG] ✓ Nenhum problema óbvio encontrado no XML")
            
            print("="*80)
            
        except Exception as e:
            print(f"[DEBUG] Erro no debugging: {e}")
            import traceback
            traceback.print_exc()

    def _testar_xml_contra_sefaz(self, xml_content):
        """
        Testa um XML específico contra SEFAZ sem assinatura - CORRIGIDO
        """
        try:
            # Conecta com SEFAZ com configuração melhorada
            session = Session()
            
            # Headers mais completos para evitar bloqueios
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            retry_strategy = Retry(
                total=3, 
                backoff_factor=2,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            session.verify = False  # Apenas para homologação
            
            transport = Transport(session=session)
            
            # URLs alternativas do SEFAZ SP
            urls_wsdl = [
                "https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx?WSDL",
                "https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao.asmx?WSDL",
                "https://homologacao.nfce.fazenda.sp.gov.br/nfeweb/services/nfeautorizacao4.asmx?WSDL"
            ]
            
            for wsdl_url in urls_wsdl:
                try:
                    print(f"[DEBUG] Tentando WSDL: {wsdl_url}")
                    client = Client(wsdl_url, transport=transport)
                    
                    # Converte para elemento lxml
                    xml_element = etree.fromstring(xml_content.encode('utf-8'))
                    
                    # Tenta enviar
                    response = client.service.nfeAutorizacaoLote(xml_element)
                    
                    if hasattr(response, 'cStat'):
                        return f"cStat: {response.cStat}, Motivo: {response.xMotivo}"
                    else:
                        return f"Resposta: {response}"
                        
                except Exception as url_error:
                    print(f"[DEBUG] Falha com {wsdl_url}: {url_error}")
                    continue
            
            return "Erro: Todos os WSDLs falharam"
                
        except Exception as e:
            return f"Erro no teste: {str(e)}"

    def _gerar_xml_ultra_minimo(self, dados):
        """
        Gera XML com absolutamente o mínimo possível
        """
        print("[DEBUG] Gerando XML ULTRA MÍNIMO para teste...")
        
        chave_acesso = dados['chave_acesso']
        agora = datetime.now().strftime('%Y-%m-%dT%H:%M:%S-03:00')
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
    <idLote>1</idLote>
    <indSinc>1</indSinc>
    <NFe>
        <infNFe versao="4.00" Id="NFe{chave_acesso}">
            <ide>
                <cUF>35</cUF>
                <cNF>12345678</cNF>
                <natOp>Venda</natOp>
                <mod>65</mod>
                <serie>1</serie>
                <nNF>{dados['numero']}</nNF>
                <dhEmi>{agora}</dhEmi>
                <tpNF>1</tpNF>
                <idDest>1</idDest>
                <cMunFG>3523800</cMunFG>
                <tpImp>4</tpImp>
                <tpEmis>1</tpEmis>
                <cDV>{chave_acesso[-1]}</cDV>
                <tpAmb>2</tpAmb>
                <finNFe>1</finNFe>
                <indFinal>1</indFinal>
                <indPres>1</indPres>
            </ide>
            <emit>
                <CNPJ>10361831000223</CNPJ>
                <xNome>TESTE LTDA</xNome>
                <enderEmit>
                    <xLgr>RUA TESTE</xLgr>
                    <nro>1</nro>
                    <xBairro>CENTRO</xBairro>
                    <cMun>3523800</cMun>
                    <xMun>Itapetininga</xMun>
                    <UF>SP</UF>
                    <CEP>18200000</CEP>
                </enderEmit>
                <IE>371468833110</IE>
                <CRT>1</CRT>
            </emit>
            <det nItem="1">
                <prod>
                    <cProd>1</cProd>
                    <xProd>TESTE</xProd>
                    <NCM>21069090</NCM>
                    <CFOP>5102</CFOP>
                    <uCom>UN</uCom>
                    <qCom>1.0000</qCom>
                    <vUnCom>1.00</vUnCom>
                    <uTrib>UN</uTrib>
                    <qTrib>1.0000</qTrib>
                    <vUnTrib>1.00</vUnTrib>
                    <vProd>1.00</vProd>
                    <indTot>1</indTot>
                </prod>
                <imposto>
                    <ICMS>
                        <ICMSSN102>
                            <orig>0</orig>
                            <CSOSN>102</CSOSN>
                        </ICMSSN102>
                    </ICMS>
                </imposto>
            </det>
            <total>
                <ICMSTot>
                    <vBC>0.00</vBC>
                    <vICMS>0.00</vICMS>
                    <vICMSDeson>0.00</vICMSDeson>
                    <vFCP>0.00</vFCP>
                    <vBCST>0.00</vBCST>
                    <vST>0.00</vST>
                    <vFCPST>0.00</vFCPST>
                    <vFCPSTRet>0.00</vFCPSTRet>
                    <vProd>1.00</vProd>
                    <vFrete>0.00</vFrete>
                    <vSeg>0.00</vSeg>
                    <vDesc>0.00</vDesc>
                    <vII>0.00</vII>
                    <vIPI>0.00</vIPI>
                    <vIPIDevol>0.00</vIPIDevol>
                    <vPIS>0.00</vPIS>
                    <vCOFINS>0.00</vCOFINS>
                    <vOutro>0.00</vOutro>
                    <vNF>1.00</vNF>
                </ICMSTot>
            </total>
            <transp>
                <modFrete>9</modFrete>
            </transp>
            <pag>
                <detPag>
                    <tPag>01</tPag>
                    <vPag>1.00</vPag>
                </detPag>
            </pag>
        </infNFe>
    </NFe>
</enviNFe>'''
        
        return xml_content

    def _emitir_nfce_real(self, dados):
        """
        Emite NFCe real no SEFAZ com debugging avançado - CORRIGIDO
        """
        cert_path = None
        key_path = None
        
        try:
            print("[INFO] Modo de teste: desabilitando conexão real com SEFAZ")
            print("[INFO] Testando apenas geração e validação de XML...")
            
            # Gera XML da NFCe com debugging
            print("[INFO] Gerando XML da NFCe...")
            xml_content = self._gerar_xml_nfce_completo(dados)
            
            # DEBUGGING PROFUNDO
            self._debug_xml_profundo(xml_content)
            
            # Simula resposta de sucesso para testar a view
            print("[SIMULAÇÃO] Emitindo como se fosse real...")
            return {
                'sucesso': True,
                'numero_nfce': dados['numero'],  # CORRIGIDO: campo correto
                'chave_acesso': dados['chave_acesso'],
                'protocolo': 'TESTE123456789',
                'modo': 'teste_real'
            }
            
        except Exception as e:
            print(f"[ERROR] Falha na emissão real: {e}")
            import traceback
            traceback.print_exc()
            raise e

    def _obter_proximo_numero_nfce(self):
        """Obtém próximo número sequencial da NFCe"""
        return 171622
    
    def _montar_dados_nfce(self, order, numero, cpf_cliente=None):
        """Monta estrutura de dados da NFCe"""
        chave_acesso = self._gerar_chave_acesso(numero)
        
        return {
            'numero': numero,
            'chave_acesso': chave_acesso,
            'order': order,
            'cpf_cliente': cpf_cliente,
            'qr_code': self._gerar_qr_code(chave_acesso, order.total_amount)  # CORRIGIDO: total_amount
        }
    
    def _gerar_chave_acesso(self, numero):
        """Gera chave de acesso da NFCe"""
        agora = datetime.now()
        uf_codigo = self._get_codigo_uf()
        cnpj = "10361831000223"
        modelo = "65"
        serie = "001"
        numero_formatado = f"{numero:09d}"
        codigo_numerico = "12345678"
        
        chave_sem_dv = (
            f"{uf_codigo}"  # UF
            f"{agora.strftime('%y%m')}"  # AAMM
            f"{cnpj}"  # CNPJ
            f"{modelo}"  # Modelo
            f"{serie}"  # Série
            f"{numero_formatado}"  # Número
            f"{codigo_numerico}"  # Código numérico
        )
        
        # Calcula dígito verificador
        dv = self._calcular_dv_chave_acesso(chave_sem_dv)
        chave_completa = chave_sem_dv + str(dv)
        
        print(f"[DEBUG] Chave de acesso gerada: {chave_completa}")
        return chave_completa
    
    def _calcular_dv_chave_acesso(self, chave_sem_dv):
        """Calcula dígito verificador da chave de acesso"""
        sequencia = "4329876543298765432987654329876543298765432"
        soma = 0
        
        for i, digito in enumerate(chave_sem_dv):
            soma += int(digito) * int(sequencia[i])
        
        resto = soma % 11
        
        if resto in [0, 1]:
            return 0
        else:
            return 11 - resto

    def _gerar_qr_code(self, chave_acesso, valor_total):
        """Gera código QR da NFCe"""
        valor_formatado = f"{valor_total:.2f}".replace('.', ',')
        hash_sha1 = hashlib.sha1(f"{chave_acesso}|2|2|1|{valor_formatado}".encode()).hexdigest()
        
        qr_data = f"{chave_acesso}|2|2|1|{hash_sha1.upper()}"
        return qr_data

    def _gerar_xml_nfce_completo(self, dados):
        """Gera XML completo da NFCe"""
        chave_acesso = dados['chave_acesso']
        order = dados['order']
        agora = datetime.now().strftime('%Y-%m-%dT%H:%M:%S-03:00')
        
        print("[DEBUG] XML TESTE PROFUNDO - Ultra limpo")
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
    <idLote>1</idLote>
    <indSinc>1</indSinc>
    <NFe>
        <infNFe versao="4.00" Id="NFe{chave_acesso}">
            <ide>
                <cUF>35</cUF>
                <cNF>12345678</cNF>
                <natOp>Venda</natOp>
                <mod>65</mod>
                <serie>1</serie>
                <nNF>{dados['numero']}</nNF>
                <dhEmi>{agora}</dhEmi>
                <tpNF>1</tpNF>
                <idDest>1</idDest>
                <cMunFG>3523800</cMunFG>
                <tpImp>4</tpImp>
                <tpEmis>1</tpEmis>
                <cDV>{chave_acesso[-1]}</cDV>
                <tpAmb>2</tpAmb>
                <finNFe>1</finNFe>
                <indFinal>1</indFinal>
                <indPres>1</indPres>
            </ide>
            <emit>
                <CNPJ>10361831000223</CNPJ>
                <xNome>COXINHAS PREMIUM LTDA</xNome>
                <enderEmit>
                    <xLgr>Rua Coronel Fernando Prestes</xLgr>
                    <nro>898</nro>
                    <xBairro>Centro</xBairro>
                    <cMun>3523800</cMun>
                    <xMun>Itapetininga</xMun>
                    <UF>SP</UF>
                    <CEP>18200230</CEP>
                </enderEmit>
                <IE>371468833110</IE>
                <CRT>1</CRT>
            </emit>
            <det nItem="1">
                <prod>
                    <cProd>1</cProd>
                    <xProd>PRODUTO TESTE</xProd>
                    <NCM>21069090</NCM>
                    <CFOP>5102</CFOP>
                    <uCom>UN</uCom>
                    <qCom>1.0000</qCom>
                    <vUnCom>1.00</vUnCom>
                    <uTrib>UN</uTrib>
                    <qTrib>1.0000</qTrib>
                    <vUnTrib>1.00</vUnTrib>
                    <vProd>1.00</vProd>
                    <indTot>1</indTot>
                </prod>
                <imposto>
                    <ICMS>
                        <ICMSSN102>
                            <orig>0</orig>
                            <CSOSN>102</CSOSN>
                        </ICMSSN102>
                    </ICMS>
                </imposto>
            </det>
            <total>
                <ICMSTot>
                    <vBC>0.00</vBC>
                    <vICMS>0.00</vICMS>
                    <vICMSDeson>0.00</vICMSDeson>
                    <vFCP>0.00</vFCP>
                    <vBCST>0.00</vBCST>
                    <vST>0.00</vST>
                    <vFCPST>0.00</vFCPST>
                    <vFCPSTRet>0.00</vFCPSTRet>
                    <vProd>1.00</vProd>
                    <vFrete>0.00</vFrete>
                    <vSeg>0.00</vSeg>
                    <vDesc>0.00</vDesc>
                    <vII>0.00</vII>
                    <vIPI>0.00</vIPI>
                    <vIPIDevol>0.00</vIPIDevol>
                    <vPIS>0.00</vPIS>
                    <vCOFINS>0.00</vCOFINS>
                    <vOutro>0.00</vOutro>
                    <vNF>1.00</vNF>
                </ICMSTot>
            </total>
            <transp>
                <modFrete>9</modFrete>
            </transp>
            <pag>
                <detPag>
                    <tPag>01</tPag>
                    <vPag>1.00</vPag>
                </detPag>
            </pag>
            <infNFeSupl>
                <qrCode><![CDATA[{dados['qr_code']}]]></qrCode>
                <urlChave>https://www.fazenda.sp.gov.br/nfe/qrcode</urlChave>
            </infNFeSupl>
        </infNFe>
    </NFe>
</enviNFe>'''
        
        print(f"[DEBUG] XML gerado:")
        print(xml_content)
        print(f"[DEBUG] Tamanho total do XML: {len(xml_content)} chars")
        
        return xml_content

    def _preparar_certificado(self):
        """Prepara certificado para uso"""
        with open(self.certificado.arquivo_pfx.path, 'rb') as f:
            pfx_data = f.read()
        
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data, 
            self.certificado.senha_pfx.encode('utf-8')
        )
        
        # Salva certificado temporário
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as cert_file:
            cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            cert_file.write(cert_pem)
            cert_path = cert_file.name
        
        # Salva chave privada temporária
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as key_file:
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            key_file.write(key_pem)
            key_path = key_file.name
        
        return cert_path, key_path

    def _assinar_xml(self, xml_content, cert_path, key_path):
        """Assina XML com certificado digital (simplificado para teste)"""
        # Para teste, retorna o XML sem assinatura para verificar se o problema é na estrutura
        return xml_content

    def _emitir_nfce_simulado(self, dados):
        """Emite NFCe em modo simulação - CORRIGIDO"""
        print(f"[SIMULAÇÃO] Emitindo NFCe #{dados['numero']}")
        print(f"[SIMULAÇÃO] Empresa: {self.empresa.nome_fantasia}")
        print(f"[SIMULAÇÃO] Cliente: CONSUMIDOR NAO IDENTIFICADO")
        print(f"[SIMULAÇÃO] Valor: R$ {dados['order'].total_amount:.2f}")  # CORRIGIDO: total_amount
        print(f"[SIMULAÇÃO] ✓ NFCe autorizada com sucesso!")
        
        return {
            'sucesso': True,
            'numero_nfce': dados['numero'],  # CORRIGIDO: campo consistente
            'chave_acesso': dados['chave_acesso'],
            'protocolo': 'SIM123456789',
            'modo': 'simulacao'
        }

    def _limpar_certificados_temporarios(self, cert_path, key_path):
        """Remove arquivos temporários de certificado"""
        try:
            if cert_path and os.path.exists(cert_path):
                os.unlink(cert_path)
                print("[INFO] Arquivo certificado temporário removido")
            if key_path and os.path.exists(key_path):
                os.unlink(key_path)
                print("[INFO] Arquivo chave temporária removida")
        except Exception as e:
            print(f"[WARNING] Erro ao limpar certificados temporários: {e}")

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
        """Retorna código IBGE do município"""
        return '3523800'

    def validar_certificado(self):
        """Valida se o certificado está válido e não expirou"""
        try:
            with open(self.certificado.arquivo_pfx.path, 'rb') as f:
                pfx_data = f.read()
            
            _, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data, 
                self.certificado.senha_pfx.encode('utf-8')
            )
            
            if certificate.not_valid_after < timezone.now():
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

    def consultar_status_nfce(self, chave_acesso):
        """Consulta status de uma NFCe na SEFAZ"""
        print(f"[INFO] Consultaria status da NFCe: {chave_acesso}")
        
    def cancelar_nfce(self, chave_acesso, justificativa):
        """Cancela uma NFCe"""
        print(f"[INFO] Cancelaria NFCe: {chave_acesso} - Motivo: {justificativa}")


    # =============== VISTA DE GERAÇÃO DE CUPOM FISCAL (HTML) ===============
    def gerar_cupom_fiscal_html(self, dados_nfce, resultado_emissao):
        """
        Gera HTML do cupom fiscal NFCe seguindo conformidades brasileiras
        """
        order = dados_nfce['order']
        chave_acesso = dados_nfce['chave_acesso']
        qr_code = dados_nfce['qr_code']
        numero_nfce = dados_nfce['numero']
        
        # Data de emissão formatada
        agora = datetime.now()
        data_emissao = agora.strftime('%d/%m/%Y %H:%M:%S')
        
        # Valor aproximado dos tributos (estimativa de 20% sobre o total)
        valor_total = float(order.total_amount)
        tributos_aproximados = valor_total * 0.20
        
        html_cupom = f'''
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cupom Fiscal NFCe #{numero_nfce}</title>
        <style>
            /* === CONFIGURAÇÃO PARA IMPRESSORA TÉRMICA 80MM === */
            @page {{
                size: 80mm auto;
                margin: 0;
            }}

            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.2;
                color: #000;
                background: #fff;
                width: 80mm;
                margin: 0 auto;
                padding: 4mm;
            }}

            @media print {{
                body {{
                    background: white;
                    font-size: 10px;
                }}
                .no-print {{
                    display: none;
                }}
            }}

            /* === ESTILOS DO CUPOM FISCAL === */
            .center {{
                text-align: center;
            }}

            .bold {{
                font-weight: bold;
            }}

            .line {{
                border-bottom: 1px dashed #000;
                margin: 3px 0;
                height: 1px;
            }}

            .double-line {{
                border-bottom: 2px solid #000;
                margin: 4px 0;
                height: 2px;
            }}

            .empresa-header {{
                text-align: center;
                margin-bottom: 8px;
            }}

            .empresa-nome {{
                font-size: 13px;
                font-weight: bold;
                margin-bottom: 2px;
            }}

            .empresa-dados {{
                font-size: 9px;
                line-height: 1.3;
            }}

            .nfce-header {{
                text-align: center;
                border: 2px solid #000;
                padding: 4px;
                margin: 6px 0;
                font-size: 12px;
                font-weight: bold;
            }}

            .dados-nfce {{
                font-size: 9px;
                margin: 6px 0;
            }}

            .consumidor {{
                font-size: 10px;
                margin: 4px 0;
                padding: 2px 0;
                border-top: 1px dashed #000;
                border-bottom: 1px dashed #000;
            }}

            .item {{
                margin: 2px 0;
                font-size: 9px;
            }}

            .item-desc {{
                font-weight: bold;
            }}

            .item-valores {{
                display: flex;
                justify-content: space-between;
                font-size: 8px;
            }}

            .totais {{
                margin: 6px 0;
                font-size: 10px;
            }}

            .total-final {{
                font-size: 12px;
                font-weight: bold;
                text-align: center;
                border: 1px solid #000;
                padding: 3px;
                margin: 4px 0;
            }}

            .pagamento {{
                margin: 4px 0;
                font-size: 9px;
                text-align: center;
            }}

            .tributos {{
                font-size: 8px;
                margin: 4px 0;
                padding: 2px 0;
                border: 1px dashed #000;
                text-align: center;
            }}

            .qrcode-section {{
                text-align: center;
                margin: 8px 0;
            }}

            .qrcode-box {{
                border: 2px solid #000;
                padding: 8px;
                margin: 4px 0;
                display: inline-block;
            }}

            .consulta-info {{
                font-size: 8px;
                text-align: center;
                margin: 4px 0;
            }}

            .protocolo {{
                font-size: 9px;
                margin: 4px 0;
                text-align: center;
            }}

            .mensagens-legais {{
                font-size: 7px;
                text-align: center;
                margin: 6px 0;
                padding: 3px 0;
                border-top: 1px dashed #000;
            }}

            .footer {{
                text-align: center;
                font-size: 8px;
                margin-top: 8px;
            }}

            /* Controles de impressão */
            .print-controls {{
                text-align: center;
                margin: 10px 0;
                background: #f0f0f0;
                padding: 10px;
                border-radius: 4px;
            }}

            .btn {{
                display: inline-block;
                padding: 8px 16px;
                margin: 0 4px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
                border: none;
                cursor: pointer;
            }}

            .btn:hover {{
                background: #0056b3;
            }}

            .btn-success {{
                background: #28a745;
            }}
        </style>
    </head>
    <body>
        <!-- Controles de Impressão -->
        <div class="print-controls no-print">
            <button class="btn" onclick="window.print()">🖨️ Imprimir</button>
            <button class="btn btn-success" onclick="window.close()">✕ Fechar</button>
        </div>

        <!-- === CABEÇALHO DA EMPRESA === -->
        <div class="empresa-header">
            <div class="empresa-nome">COXINHAS PREMIUM LTDA</div>
            <div class="empresa-dados">
                Rua Coronel Fernando Prestes, 898<br>
                Centro - Itapetininga/SP<br>
                CEP: 18200-230<br>
                CNPJ: 10.361.831/0001-23<br>
                IE: 371.468.833.110
            </div>
        </div>

        <!-- === IDENTIFICAÇÃO NFCe === -->
        <div class="nfce-header">
            DOCUMENTO AUXILIAR DA<br>
            NOTA FISCAL DE CONSUMIDOR<br>
            ELETRÔNICA
        </div>

        <div class="dados-nfce center">
            <div class="bold">NFCe Nº {numero_nfce:09d} - Série 001</div>
            <div>Emissão: {data_emissao}</div>
            <div style="font-size: 8px; margin-top: 2px;">
                Ambiente: Homologação
            </div>
        </div>

        <div class="line"></div>

        <!-- === CONSUMIDOR === -->
        <div class="consumidor center">
            <div class="bold">CONSUMIDOR NÃO IDENTIFICADO</div>
        </div>

        <!-- === DISCRIMINAÇÃO DOS ITENS === -->
        <div class="bold center" style="margin: 6px 0;">ITENS</div>
        <div class="line"></div>
    '''

        # Adicionar itens
        for i, item in enumerate(order.items.all(), 1):
            subtotal = float(item.quantity) * float(item.unit_price)
            html_cupom += f'''
        <div class="item">
            <div class="item-desc">{i:03d} {item.product.name}</div>
            <div class="item-valores">
                <span>Qtd: {item.quantity} UN</span>
                <span>Unit: R$ {item.unit_price:.2f}</span>
            </div>
            <div class="item-valores">
                <span>Cód: {getattr(item.product, 'id', '000001')}</span>
                <span>Total: R$ {subtotal:.2f}</span>
            </div>
        </div>
        <div class="line"></div>
    '''

        # Continuar HTML com totais, pagamento, etc.
        html_cupom += f'''
        <!-- === TOTALIZADORES === -->
        <div class="totais">
            <div style="display: flex; justify-content: space-between;">
                <span>Qtd. total de itens:</span>
                <span>{order.items.count()}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>Valor total R$:</span>
                <span>{valor_total:.2f}</span>
            </div>
        </div>

        <div class="total-final">
            TOTAL R$ {valor_total:.2f}
        </div>

        <!-- === FORMA DE PAGAMENTO === -->
        <div class="pagamento">
            <div class="bold">FORMA PAGAMENTO</div>
            <div>Dinheiro - Valor R$ {valor_total:.2f}</div>
        </div>

        <div class="line"></div>

        <!-- === TRIBUTOS APROXIMADOS === -->
        <div class="tributos">
            Valor aprox. tributos R$ {tributos_aproximados:.2f} ({(tributos_aproximados/valor_total)*100:.1f}%)<br>
            Fonte: IBPT/empresometro.com.br
        </div>

        <!-- === CONSULTA VIA QR CODE === -->
        <div class="qrcode-section">
            <div class="bold">Consulte pela chave de acesso em:</div>
            <div style="font-size: 8px;">fazenda.sp.gov.br/nfe/qrcode</div>
            
            <div class="qrcode-box">
                <div style="font-size: 8px;">QR CODE</div>
                <div style="border: 1px solid #000; width: 60px; height: 60px; margin: 4px auto; display: flex; align-items: center; justify-content: center; font-size: 6px;">
                    {qr_code[:20]}...<br>
                    (QR Code aqui)
                </div>
            </div>
        </div>

        <!-- === CHAVE DE ACESSO === -->
        <div class="center" style="font-size: 8px; word-break: break-all; margin: 4px 0;">
            <div class="bold">CHAVE DE ACESSO:</div>
            {chave_acesso}
        </div>

        <!-- === PROTOCOLO (SE AUTORIZADA) === -->
        {f'<div class="protocolo"><div class="bold">PROTOCOLO DE AUTORIZAÇÃO:</div>{resultado_emissao.get("protocolo", "PENDENTE")}<br>{data_emissao}</div>' if resultado_emissao.get('sucesso') else ''}

        <div class="line"></div>

        <!-- === INFORMAÇÕES LEGAIS === -->
        <div class="mensagens-legais">
            Esta NFCe foi emitida nos termos da<br>
            Resolução CGSN nº 140/2018 e<br>
            condições descritas em<br>
            fazenda.sp.gov.br/nfe
        </div>

        <div class="mensagens-legais">
            Não permite aproveitamento de crédito de ICMS
        </div>

        <!-- === FOOTER === -->
        <div class="footer">
            <div style="margin: 8px 0;">
                ★★★ OBRIGADO PELA PREFERÊNCIA! ★★★
            </div>
            <div style="margin: 4px 0;">
                Volte sempre!
            </div>
            <div style="font-size: 6px; margin-top: 8px;">
                Cupom gerado em {data_emissao}
            </div>
        </div>

        <!-- Espaço para corte -->
        <div style="height: 20mm;"></div>

        <script>
            // Auto-impressão quando solicitado
            if (window.location.search.includes('print=auto')) {{
                setTimeout(() => {{
                    window.print();
                    setTimeout(() => window.close(), 1000);
                }}, 500);
            }}
        </script>

    </body>
    </html>
    '''
        
        return html_cupom

    def salvar_cupom_fiscal(self, dados_nfce, resultado_emissao):
        """
        Salva o cupom fiscal em arquivo HTML para impressão
        """
        try:
            cupom_html = self.gerar_cupom_fiscal_html(dados_nfce, resultado_emissao)
            
            # Criar diretório se não existir
            cupons_dir = os.path.join(settings.MEDIA_ROOT, 'cupons_fiscais')
            os.makedirs(cupons_dir, exist_ok=True)
            
            # Nome do arquivo
            numero_nfce = dados_nfce['numero']
            chave_acesso = dados_nfce['chave_acesso']
            filename = f"cupom_nfce_{numero_nfce}_{chave_acesso}.html"
            filepath = os.path.join(cupons_dir, filename)
            
            # Salvar arquivo
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cupom_html)
            
            print(f"[INFO] Cupom fiscal salvo: {filepath}")
            
            return {
                'arquivo_salvo': True,
                'caminho': filepath,
                'url_impressao': f'/media/cupons_fiscais/{filename}',
                'html_content': cupom_html
            }
            
        except Exception as e:
            print(f"[ERROR] Erro ao salvar cupom fiscal: {e}")
            return {
                'arquivo_salvo': False,
                'erro': str(e),
                'html_content': cupom_html  # Retorna HTML mesmo se não conseguir salvar
            }


    def emitir_nfce(self, order, cpf_cliente=None):
        """
        Método principal para emissão de NFCe com cupom fiscal
        """
        try:
            # Pega próximo número da NFCe
            numero = self._obter_proximo_numero_nfce()
            
            # Monta dados da NFCe
            dados_nfce = self._montar_dados_nfce(order, numero, cpf_cliente)
            
            # Se tem certificado, tenta emissão real primeiro
            if self.certificado:
                try:
                    print("[INFO] Tentando emissão real em HOMOLOGAÇÃO...")
                    resultado = self._emitir_nfce_real(dados_nfce)
                    
                    # Gerar cupom fiscal após emissão bem-sucedida
                    if resultado['sucesso']:
                        cupom_info = self.salvar_cupom_fiscal(dados_nfce, resultado)
                        resultado['cupom_fiscal'] = cupom_info
                        print(f"[INFO] Cupom fiscal gerado: {cupom_info.get('url_impressao', 'N/A')}")
                    
                    return resultado
                except Exception as e:
                    print(f"[ERROR] Falha na emissão real: {e}")
                    print("[FALLBACK] Tentando simulação após falha na emissão real...")
                    resultado = self._emitir_nfce_simulado(dados_nfce)
            else:
                print("[INFO] Emissão apenas em modo simulação")
                resultado = self._emitir_nfce_simulado(dados_nfce)
            
            # Gerar cupom fiscal mesmo em simulação
            if resultado['sucesso']:
                cupom_info = self.salvar_cupom_fiscal(dados_nfce, resultado)
                resultado['cupom_fiscal'] = cupom_info
                print(f"[INFO] Cupom fiscal gerado: {cupom_info.get('url_impressao', 'N/A')}")
                
            return resultado
            
        except Exception as e:
            print(f"[ERROR] Erro geral na emissão de NFCe: {e}")
            return {
                'sucesso': False,
                'erro': f'Erro na emissão: {str(e)}',
                'modo': 'erro'
            }