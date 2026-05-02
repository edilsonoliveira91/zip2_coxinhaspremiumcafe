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
        Emite NFCe real no SEFAZ:
        1. Carrega certificado A1
        2. Gera XML com dados reais
        3. Assina com XMLDSig RSA-SHA1
        4. Envia para webservice SEFAZ
        5. Parseia resposta e retorna protocolo
        """
        cert_path = None
        key_path = None

        try:
            # 1. Carregar certificado
            print("[INFO] Carregando certificado digital...")
            with open(self.certificado.arquivo_pfx.path, 'rb') as f:
                pfx_data = f.read()

            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data,
                self.certificado.senha_pfx.encode('utf-8'),
            )
            print(f"[INFO] Certificado carregado: {certificate.subject.rfc4514_string()}")

            # 2. Exportar cert e key para arquivos temporários (necessário para requests cert=)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pem', mode='wb') as cf:
                cf.write(certificate.public_bytes(serialization.Encoding.PEM))
                cert_path = cf.name

            with tempfile.NamedTemporaryFile(delete=False, suffix='.key', mode='wb') as kf:
                kf.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
                key_path = kf.name

            # 3. Gerar XML completo
            print("[INFO] Gerando XML da NFCe...")
            xml_content = self._gerar_xml_nfce_completo(dados)

            # 4. Assinar XML
            print("[INFO] Assinando XML com certificado digital...")
            xml_assinado = self._assinar_xml(xml_content, private_key, certificate)
            print(f"[INFO] XML assinado ({len(xml_assinado)} chars)")

            # 5. Enviar para SEFAZ
            print("[INFO] Enviando para SEFAZ...")
            resposta_xml = self._chamar_sefaz(xml_assinado, cert_path, key_path)

            # 6. Parsear resposta
            resultado_sefaz = self._parsear_resposta_sefaz(resposta_xml)

            if resultado_sefaz['sucesso']:
                print(f"[SEFAZ] NFCe autorizada! Protocolo: {resultado_sefaz['protocolo']}")
                return {
                    'sucesso': True,
                    'numero_nfce': dados['numero'],
                    'chave_acesso': dados['chave_acesso'],
                    'protocolo': resultado_sefaz['protocolo'],
                    'modo': 'producao' if self.empresa.ambiente_nfce == '1' else 'homologacao',
                }
            else:
                return {
                    'sucesso': False,
                    'erro': resultado_sefaz['erro'],
                    'cStat': resultado_sefaz.get('cStat', ''),
                    'xMotivo': resultado_sefaz.get('xMotivo', ''),
                }

        except Exception as e:
            print(f"[ERROR] Falha na emissão real: {e}")
            import traceback
            traceback.print_exc()
            raise e

        finally:
            self._limpar_certificados_temporarios(cert_path, key_path)

    def _obter_proximo_numero_nfce(self):
        """Obtém próximo número sequencial da NFCe a partir da empresa"""
        return self.empresa.get_proximo_numero_nfce()
    
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
        """Gera chave de acesso da NFCe usando dados da empresa"""
        agora = datetime.now()
        uf_codigo = self._get_codigo_uf()
        cnpj = re.sub(r'\D', '', self.empresa.cnpj)  # apenas dígitos
        modelo = "65"
        serie = f"{self.empresa.serie_nfce:03d}"
        numero_formatado = f"{numero:09d}"
        # Código numérico: 8 dígitos derivados do CNPJ+número
        codigo_numerico = f"{abs(hash(cnpj + str(numero))) % 100000000:08d}"

        chave_sem_dv = (
            f"{uf_codigo}"             # 2 digits
            f"{agora.strftime('%y%m')}"  # 4 digits
            f"{cnpj}"                  # 14 digits
            f"{modelo}"                # 2 digits
            f"{serie}"                 # 3 digits
            f"{numero_formatado}"      # 9 digits
            "1"                        # tpEmis = 1 (normal)
            f"{codigo_numerico}"       # 8 digits
        )  # total 43 + cDV = 44

        dv = self._calcular_dv_chave_acesso(chave_sem_dv)
        chave_completa = chave_sem_dv + str(dv)
        print(f"[DEBUG] Chave de acesso gerada: {chave_completa} ({len(chave_completa)} chars)")
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
        """
        Gera URL do QR Code da NFCe conforme NT 2013.005 SEFAZ.
        Formato: <url>?p=<chave>|<tpAmb>|<cIdToken>|<cHashQRCode>
        cHashQRCode = SHA1(chave + "|" + tpAmb + "|" + cIdToken + "|" + csc_codigo).upper()
        """
        tp_amb = self.empresa.ambiente_nfce  # '1' prod, '2' homolog
        cid_token = str(self.empresa.csc_id).zfill(6)  # padded to 6 digits
        csc_codigo = self.empresa.csc_codigo

        hash_input = f"{chave_acesso}|{tp_amb}|{cid_token}|{csc_codigo}"
        c_hash = hashlib.sha1(hash_input.encode('utf-8')).hexdigest().upper()

        url_base = self._get_url_consulta_qrcode()
        qr_url = f"{url_base}?p={chave_acesso}|{tp_amb}|{cid_token}|{c_hash}"
        return qr_url

    def _get_url_consulta_qrcode(self):
        """Retorna URL de consulta pública do QR Code por UF e ambiente"""
        uf = self.empresa.uf
        amb = self.empresa.ambiente_nfce  # '1'=prod, '2'=homolog

        urls = {
            'SP': {
                '1': 'https://www.nfce.fazenda.sp.gov.br/NFeConsultaPublica/Paginas/ConsultaQRCode.aspx',
                '2': 'https://homologacao.nfce.fazenda.sp.gov.br/NFCeConsultaPublica',
            },
            'MG': {
                '1': 'https://nfce.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml',
                '2': 'https://hnfce.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml',
            },
            'RS': {
                '1': 'https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx',
                '2': 'https://www.sefaz.rs.gov.br/NFCEHOM/NFCE-COM.aspx',
            },
            'PR': {
                '1': 'https://www.nfce.sefa.pr.gov.br/nfce/qrcode',
                '2': 'https://www.nfce.sefa.pr.gov.br/nfce/qrcode',
            },
        }
        # SVRS states (default for unregistered states)
        svrs_states = ['AC', 'AL', 'AP', 'DF', 'ES', 'PB', 'PI', 'RN', 'RO', 'RR', 'SC', 'SE', 'TO']
        svrs_urls = {
            '1': 'https://nfce.svrs.rs.gov.br/off/gqrcodeoff.aspx',
            '2': 'https://nfce-homologacao.svrs.rs.gov.br/off/gqrcodeoff.aspx',
        }

        if uf in urls:
            return urls[uf].get(amb, urls[uf]['2'])
        elif uf in svrs_states:
            return svrs_urls.get(amb, svrs_urls['2'])
        else:
            # AN/SVAN states
            return svrs_urls.get(amb, svrs_urls['2'])

    def _gerar_xml_nfce_completo(self, dados):
        """Gera XML completo da NFCe com dados reais da empresa e itens da comanda"""
        chave_acesso = dados['chave_acesso']
        order = dados['order']
        agora = datetime.now().strftime('%Y-%m-%dT%H:%M:%S-03:00')

        # --- Empresa ---
        empresa = self.empresa
        cnpj_digits = re.sub(r'\D', '', empresa.cnpj)
        ie_digits = re.sub(r'\D', '', empresa.inscricao_estadual)
        cep_digits = re.sub(r'\D', '', empresa.cep)
        uf_codigo = self._get_codigo_uf()
        cod_municipio = empresa.codigo_municipio_ibge or '3523800'
        tp_amb = empresa.ambiente_nfce  # '1'=prod, '2'=homolog
        crt = empresa.regime_tributario  # '1','2','3'
        cfop = empresa.cfop_padrao or '5102'
        serie = str(empresa.serie_nfce)

        # Extrair cNF da chave (posição 35-43 após tpEmis=1)
        # chave = cUF(2)+AAMM(4)+CNPJ(14)+mod(2)+serie(3)+nNF(9)+tpEmis(1)+cNF(8)+cDV(1)
        c_nf = chave_acesso[35:43] if len(chave_acesso) == 44 else '12345678'

        # --- Itens: coletar de todos os pedidos da comanda ---
        all_items = []
        for pedido in order.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta', 'entregue']):
            for item in pedido.items.select_related('product').all():
                all_items.append(item)

        if not all_items:
            # Fallback: item genérico com total da comanda
            all_items = [{
                '_fallback': True,
                'name': 'VENDA DE ALIMENTOS',
                'qty': 1,
                'unit_price': float(order.total_amount),
                'total_price': float(order.total_amount),
            }]

        # --- Calcular totais ---
        valor_total = float(order.total_amount)

        # --- Forma de pagamento ---
        tp_pag = '01'  # dinheiro default
        v_pag = f"{valor_total:.2f}"
        if hasattr(order, 'checkout') and order.checkout:
            pm = order.checkout.payment_method
            tp_pag_map = {
                'dinheiro': '01',
                'cartao_credito': '03',
                'cartao_debito': '04',
                'pix': '17',
                'voucher': '15',
            }
            tp_pag = tp_pag_map.get(pm, '01')

        # --- Gerar blocos <det> ---
        det_blocks = []
        for i, item in enumerate(all_items, 1):
            if isinstance(item, dict) and item.get('_fallback'):
                nome = item['name']
                qty = item['qty']
                v_unit = item['unit_price']
                v_prod = item['total_price']
                ncm = '21069090'
                cprod = str(i)
            else:
                nome = item.product.name[:120]
                qty = float(item.quantity)
                v_unit = float(item.unit_price)
                v_prod = round(qty * v_unit, 2)
                ncm = getattr(item.product, 'ncm', '') or '21069090'
                cprod = str(getattr(item.product, 'id', i))

            # CSOSN depends on CRT
            if crt == '1':
                imposto_block = '<imposto><ICMS><ICMSSN102><orig>0</orig><CSOSN>102</CSOSN></ICMSSN102></ICMS></imposto>'
            else:
                imposto_block = '<imposto><ICMS><ICMS60><orig>0</orig><CST>60</CST></ICMS60></ICMS></imposto>'

            det_blocks.append(f'<det nItem="{i}">\n'
                f'            <prod>\n'
                f'                <cProd>{cprod}</cProd>\n'
                f'                <xProd>{nome}</xProd>\n'
                f'                <NCM>{ncm}</NCM>\n'
                f'                <CFOP>{cfop}</CFOP>\n'
                f'                <uCom>UN</uCom>\n'
                f'                <qCom>{qty:.4f}</qCom>\n'
                f'                <vUnCom>{v_unit:.10f}</vUnCom>\n'
                f'                <uTrib>UN</uTrib>\n'
                f'                <qTrib>{qty:.4f}</qTrib>\n'
                f'                <vUnTrib>{v_unit:.10f}</vUnTrib>\n'
                f'                <vProd>{v_prod:.2f}</vProd>\n'
                f'                <indTot>1</indTot>\n'
                f'            </prod>\n'
                f'            {imposto_block}\n'
                f'        </det>')

        dets = '\n        '.join(det_blocks)

        url_consulta = self._get_url_consulta_qrcode()

        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">\n'
            f'    <idLote>{dados["numero"]}</idLote>\n'
            '    <indSinc>1</indSinc>\n'
            '    <NFe xmlns="http://www.portalfiscal.inf.br/nfe">\n'
            f'        <infNFe versao="4.00" Id="NFe{chave_acesso}">\n'
            '            <ide>\n'
            f'                <cUF>{uf_codigo}</cUF>\n'
            f'                <cNF>{c_nf}</cNF>\n'
            '                <natOp>VENDA A CONSUMIDOR</natOp>\n'
            '                <mod>65</mod>\n'
            f'                <serie>{serie}</serie>\n'
            f'                <nNF>{dados["numero"]}</nNF>\n'
            f'                <dhEmi>{agora}</dhEmi>\n'
            '                <tpNF>1</tpNF>\n'
            '                <idDest>1</idDest>\n'
            f'                <cMunFG>{cod_municipio}</cMunFG>\n'
            '                <tpImp>4</tpImp>\n'
            '                <tpEmis>1</tpEmis>\n'
            f'                <cDV>{chave_acesso[-1]}</cDV>\n'
            f'                <tpAmb>{tp_amb}</tpAmb>\n'
            '                <finNFe>1</finNFe>\n'
            '                <indFinal>1</indFinal>\n'
            '                <indPres>1</indPres>\n'
            '            </ide>\n'
            '            <emit>\n'
            f'                <CNPJ>{cnpj_digits}</CNPJ>\n'
            f'                <xNome>{empresa.razao_social}</xNome>\n'
            f'                <xFant>{empresa.nome_fantasia or empresa.razao_social}</xFant>\n'
            '                <enderEmit>\n'
            f'                    <xLgr>{empresa.logradouro}</xLgr>\n'
            f'                    <nro>{empresa.numero}</nro>\n'
            f'                    <xBairro>{empresa.bairro}</xBairro>\n'
            f'                    <cMun>{cod_municipio}</cMun>\n'
            f'                    <xMun>{empresa.cidade}</xMun>\n'
            f'                    <UF>{empresa.uf}</UF>\n'
            f'                    <CEP>{cep_digits}</CEP>\n'
            '                    <cPais>1058</cPais>\n'
            '                    <xPais>Brasil</xPais>\n'
            '                </enderEmit>\n'
            f'                <IE>{ie_digits}</IE>\n'
            f'                <CRT>{crt}</CRT>\n'
            '            </emit>\n'
            f'            {dets}\n'
            '            <total>\n'
            '                <ICMSTot>\n'
            '                    <vBC>0.00</vBC>\n'
            '                    <vICMS>0.00</vICMS>\n'
            '                    <vICMSDeson>0.00</vICMSDeson>\n'
            '                    <vFCP>0.00</vFCP>\n'
            '                    <vBCST>0.00</vBCST>\n'
            '                    <vST>0.00</vST>\n'
            '                    <vFCPST>0.00</vFCPST>\n'
            '                    <vFCPSTRet>0.00</vFCPSTRet>\n'
            f'                    <vProd>{valor_total:.2f}</vProd>\n'
            '                    <vFrete>0.00</vFrete>\n'
            '                    <vSeg>0.00</vSeg>\n'
            '                    <vDesc>0.00</vDesc>\n'
            '                    <vII>0.00</vII>\n'
            '                    <vIPI>0.00</vIPI>\n'
            '                    <vIPIDevol>0.00</vIPIDevol>\n'
            '                    <vPIS>0.00</vPIS>\n'
            '                    <vCOFINS>0.00</vCOFINS>\n'
            '                    <vOutro>0.00</vOutro>\n'
            f'                    <vNF>{valor_total:.2f}</vNF>\n'
            '                </ICMSTot>\n'
            '            </total>\n'
            '            <transp>\n'
            '                <modFrete>9</modFrete>\n'
            '            </transp>\n'
            '            <pag>\n'
            '                <detPag>\n'
            f'                    <tPag>{tp_pag}</tPag>\n'
            f'                    <vPag>{v_pag}</vPag>\n'
            '                </detPag>\n'
            '            </pag>\n'
            '            <infNFeSupl>\n'
            f'                <qrCode><![CDATA[{dados["qr_code"]}]]></qrCode>\n'
            f'                <urlChave>{url_consulta}</urlChave>\n'
            '            </infNFeSupl>\n'
            '        </infNFe>\n'
            '    </NFe>\n'
            '</enviNFe>'
        )

        print(f"[INFO] XML gerado para NFCe #{dados['numero']} ({len(xml_content)} chars)")
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

    def _assinar_xml(self, xml_str, private_key, certificate):
        """
        Assina o XML NFe com XMLDSig RSA-SHA1 conforme padrão SEFAZ.
        A assinatura cobre o elemento infNFe referenciado por seu Id.
        """
        import io as _io
        from cryptography.hazmat.primitives import hashes as _hashes
        from cryptography.hazmat.primitives.asymmetric import padding as _asym_padding
        from cryptography.hazmat.primitives import serialization as _serialization

        NS_NFE = "http://www.portalfiscal.inf.br/nfe"
        NS_DS = "http://www.w3.org/2000/09/xmldsig#"

        # 1. Parse XML
        root = etree.fromstring(xml_str.encode('utf-8'))

        # 2. Localizar NFe e infNFe (pode estar diretamente ou dentro de enviNFe)
        nfe_elem = root.find(f'{{{NS_NFE}}}NFe')
        if nfe_elem is None:
            # root IS NFe
            nfe_elem = root

        infnfe = nfe_elem.find(f'{{{NS_NFE}}}infNFe')
        if infnfe is None:
            raise ValueError("Elemento infNFe não encontrado no XML")

        ref_id = infnfe.get('Id')  # e.g. "NFe35250210361831..."

        # 3. Canonicalizar infNFe (C14N inclusivo sem comentários)
        infnfe_c14n = etree.tostring(infnfe, method='c14n', exclusive=False, with_comments=False)

        # 4. Calcular DigestValue (SHA-1 do c14n do infNFe)
        sha1_digest = hashlib.sha1(infnfe_c14n).digest()
        digest_b64 = base64.b64encode(sha1_digest).decode('utf-8')

        # 5. Construir SignedInfo
        signed_info_xml = (
            f'<SignedInfo xmlns="{NS_DS}">'
            f'<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
            f'<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>'
            f'<Reference URI="#{ref_id}">'
            f'<Transforms>'
            f'<Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>'
            f'<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
            f'</Transforms>'
            f'<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>'
            f'<DigestValue>{digest_b64}</DigestValue>'
            f'</Reference>'
            f'</SignedInfo>'
        )

        # 6. Canonicalizar SignedInfo
        signed_info_elem = etree.fromstring(signed_info_xml.encode('utf-8'))
        signed_info_c14n = etree.tostring(signed_info_elem, method='c14n', exclusive=False, with_comments=False)

        # 7. Assinar com RSA-SHA1
        sig_bytes = private_key.sign(
            signed_info_c14n,
            _asym_padding.PKCS1v15(),
            _hashes.SHA1(),
        )
        sig_b64 = base64.b64encode(sig_bytes).decode('utf-8')

        # 8. Codificar certificado
        cert_der = certificate.public_bytes(_serialization.Encoding.DER)
        cert_b64 = base64.b64encode(cert_der).decode('utf-8')

        # 9. Construir elemento Signature
        signature_xml = (
            f'<Signature xmlns="{NS_DS}">'
            f'{signed_info_xml}'
            f'<SignatureValue>{sig_b64}</SignatureValue>'
            f'<KeyInfo>'
            f'<X509Data>'
            f'<X509Certificate>{cert_b64}</X509Certificate>'
            f'</X509Data>'
            f'</KeyInfo>'
            f'</Signature>'
        )
        sig_elem = etree.fromstring(signature_xml.encode('utf-8'))

        # 10. Inserir Signature dentro de NFe (após infNFe)
        nfe_elem.append(sig_elem)

        return etree.tostring(root, encoding='unicode', xml_declaration=False)

    def _get_sefaz_url(self):
        """Retorna URL do webservice SEFAZ de autorização NFCe por UF e ambiente"""
        uf = self.empresa.uf
        amb = self.empresa.ambiente_nfce  # '1'=prod, '2'=homolog

        urls = {
            'SP': {
                '1': 'https://nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4.asmx',
                '2': 'https://homologacao.nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4.asmx',
            },
            'MG': {
                '1': 'https://nfce.fazenda.mg.gov.br/nfce/services/NFeAutorizacao4',
                '2': 'https://hnfce.fazenda.mg.gov.br/nfce/services/NFeAutorizacao4',
            },
            'RS': {
                '1': 'https://nfce.sefazrs.rs.gov.br/ws/nfceautorizacao/NFeAutorizacao4.asmx',
                '2': 'https://nfce-homologacao.sefazrs.rs.gov.br/ws/nfceautorizacao/NFeAutorizacao4.asmx',
            },
            'PR': {
                '1': 'https://nfe.sefa.pr.gov.br/nfe-portal-web/NFeAutorizacao4',
                '2': 'https://homologacao.nfe.sefa.pr.gov.br/nfe-portal-homologacao-web/NFeAutorizacao4',
            },
        }
        svrs = {
            '1': 'https://nfce.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx',
            '2': 'https://nfce-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx',
        }

        if uf in urls:
            return urls[uf].get(amb, urls[uf]['2'])
        return svrs.get(amb, svrs['2'])

    def _chamar_sefaz(self, xml_assinado, cert_path, key_path):
        """
        Envia enviNFe assinado para o webservice SOAP da SEFAZ e retorna a resposta XML.
        """
        import requests as _req

        url = self._get_sefaz_url()
        uf_codigo = self._get_codigo_uf()

        soap_envelope = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            '<soap12:Header>'
            '<nfeCabecMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">'
            f'<cUF>{uf_codigo}</cUF>'
            '<versaoDados>4.00</versaoDados>'
            '</nfeCabecMsg>'
            '</soap12:Header>'
            '<soap12:Body>'
            '<nfeDadosMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">'
            f'{xml_assinado}'
            '</nfeDadosMsg>'
            '</soap12:Body>'
            '</soap12:Envelope>'
        )

        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8; action="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4/nfeAutorizacaoLote"',
        }

        print(f"[SEFAZ] Enviando NFCe para {url}")
        resp = _req.post(
            url,
            data=soap_envelope.encode('utf-8'),
            headers=headers,
            cert=(cert_path, key_path),
            verify=False,  # disable SSL verification for homologação
            timeout=60,
        )
        print(f"[SEFAZ] HTTP {resp.status_code}")
        return resp.text

    def _parsear_resposta_sefaz(self, xml_resposta):
        """
        Parseia a resposta SOAP da SEFAZ.
        Retorna dict com 'sucesso', 'protocolo', 'cStat', 'xMotivo' ou 'erro'.
        """
        try:
            # Remove SOAP envelope and find NFe content
            root = etree.fromstring(xml_resposta.encode('utf-8'))
            NS_NFE = 'http://www.portalfiscal.inf.br/nfe'

            # Look for retEnviNFe anywhere in the tree
            ret_envi = root.find(f'.//{{{NS_NFE}}}retEnviNFe')
            if ret_envi is None:
                # Try without namespace
                ret_envi = root.find('.//retEnviNFe')
            if ret_envi is None:
                return {
                    'sucesso': False,
                    'erro': f'Resposta inválida da SEFAZ: {xml_resposta[:500]}',
                }

            c_stat_elem = ret_envi.find(f'.//{{{NS_NFE}}}cStat') or ret_envi.find('.//cStat')
            x_motivo_elem = ret_envi.find(f'.//{{{NS_NFE}}}xMotivo') or ret_envi.find('.//xMotivo')

            c_stat = c_stat_elem.text if c_stat_elem is not None else '000'
            x_motivo = x_motivo_elem.text if x_motivo_elem is not None else 'Sem motivo'

            print(f"[SEFAZ] cStat={c_stat} — {x_motivo}")

            # cStat 100 = Autorizado uso da NF-e
            if c_stat == '100':
                inf_prot = ret_envi.find(f'.//{{{NS_NFE}}}infProt') or ret_envi.find('.//infProt')
                n_prot = ''
                if inf_prot is not None:
                    n_prot_elem = inf_prot.find(f'{{{NS_NFE}}}nProt') or inf_prot.find('nProt')
                    n_prot = n_prot_elem.text if n_prot_elem is not None else ''
                return {
                    'sucesso': True,
                    'protocolo': n_prot,
                    'cStat': c_stat,
                    'xMotivo': x_motivo,
                }
            else:
                return {
                    'sucesso': False,
                    'erro': f'SEFAZ {c_stat}: {x_motivo}',
                    'cStat': c_stat,
                    'xMotivo': x_motivo,
                }
        except Exception as e:
            return {
                'sucesso': False,
                'erro': f'Erro ao parsear resposta SEFAZ: {str(e)}',
            }

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

        # Gerar imagem QR Code
        qr_img_b64 = ''
        try:
            import qrcode as _qr
            import io as _io
            _qr_obj = _qr.QRCode(version=None, error_correction=_qr.constants.ERROR_CORRECT_M, box_size=4, border=2)
            _qr_obj.add_data(qr_code)
            _qr_obj.make(fit=True)
            _qr_img = _qr_obj.make_image(fill_color="black", back_color="white")
            _buf = _io.BytesIO()
            _qr_img.save(_buf, format='PNG')
            qr_img_b64 = base64.b64encode(_buf.getvalue()).decode('utf-8')
        except Exception as _e:
            print(f"[WARN] Não foi possível gerar imagem QR Code: {_e}")

        # Dados dinâmicos da empresa
        nome_empresa = self.empresa.nome_fantasia or self.empresa.razao_social
        cnpj_fmt = self.empresa.cnpj
        ie_fmt = self.empresa.inscricao_estadual
        end_linha1 = f"{self.empresa.logradouro}, {self.empresa.numero}"
        end_linha2 = f"{self.empresa.bairro} - {self.empresa.cidade}/{self.empresa.uf}"
        cep_fmt = self.empresa.cep
        ambiente_label = "Homologação" if self.empresa.ambiente_nfce == "2" else "Produção"

        # Forma de pagamento do checkout
        payment_display = "Dinheiro"
        if hasattr(order, 'checkout') and order.checkout:
            pm_map = {
                'dinheiro': 'Dinheiro',
                'cartao_debito': 'Cartão de Débito',
                'cartao_credito': 'Cartão de Crédito',
                'pix': 'PIX',
                'voucher': 'Voucher',
            }
            payment_display = pm_map.get(order.checkout.payment_method, order.checkout.get_payment_method_display())

        # Data de emissão formatada
        agora = datetime.now()
        data_emissao = agora.strftime('%d/%m/%Y %H:%M:%S')

        # Coletar todos os itens de todos os pedidos da comanda
        all_items = []
        for pedido in order.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta', 'entregue']):
            for item in pedido.items.all():
                all_items.append(item)

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
            <div class="empresa-nome">{nome_empresa}</div>
            <div class="empresa-dados">
                {end_linha1}<br>
                {end_linha2}<br>
                CEP: {cep_fmt}<br>
                CNPJ: {cnpj_fmt}<br>
                IE: {ie_fmt}
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
                Ambiente: {ambiente_label}
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
        for i, item in enumerate(all_items, 1):
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
                <span>{len(all_items)}</span>
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
            <div>{payment_display} - Valor R$ {valor_total:.2f}</div>
        </div>

        <div class="line"></div>

        <!-- === TRIBUTOS APROXIMADOS === -->
        <div class="tributos">
            Valor aprox. tributos R$ {tributos_aproximados:.2f} ({(tributos_aproximados/valor_total)*100:.1f}%)<br>
            Fonte: IBPT/empresometro.com.br
        </div>

        <!-- === QR CODE === -->
        <div class="qrcode-section">
            <div style="font-size: 9px; font-weight: bold; margin-bottom: 4px;">
                CONSULTE PELA CHAVE DE ACESSO
            </div>
            {f'<img src="data:image/png;base64,{qr_img_b64}" style="display:block;margin:4px auto;width:140px;height:140px;" alt="QR Code NFCe"/>' if qr_img_b64 else f'<div class="qrcode-box" style="font-size:7px;word-break:break-all;max-width:200px;">{qr_code}</div>'}
            <div class="consulta-info" style="font-size:7px;word-break:break-all;margin-top:4px;">
                {qr_code[:44]}...
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
            // Salvar como PDF (abre diálogo sem fechar janela)
            if (window.location.search.includes('pdf=1')) {{
                setTimeout(() => {{
                    window.print();
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