import time
from requests_ntlm import HttpNtlmAuth
import re

import os, sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import pandas as pd
from datetime import datetime
#from .scm import *

from .scm import *
sys.path.append("..") # Adds higher directory to python modules path.
from web.htmlscrap import *

class wPage(wPage): # overwrites original class for ntlm authentication
    def __init__(self, user, passwd):
        """ntlm auth user and pass"""
        self.session = requests.Session()
        self.session.auth = HttpNtlmAuth(user, passwd)

def getEventosSimples(wpage, processo_number, processo_year):
    """ Retorna tabela de eventos simples para processo especificado
    wpage : class wPage
    processo_number : str
    processo_year : str
    return : (Pandas DataFrame)"""
    wpage.get(('http://sigareas.dnpm.gov.br/Paginas/Usuario/ListaEvento.aspx?processo='+
          processo_number+'_'+processo_year))
    htmltxt = wpage.response.content
    soup = BeautifulSoup(htmltxt, features="lxml")
    eventstable = soup.find("table", {'class': "BordaTabela"})
    rows = tableDataText(eventstable)
    return pd.DataFrame(rows[1:], columns=rows[0])

class Form1(Processo):
    """Analise de Formulario 1"""
    def __init__(self, processostr, wpage):
        """
        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        super().__init__(processostr, wpage)
        # pasta padrao salvar processos formulario 1
        self.secorpath = r"D:\Users\andre.ferreira\Documents\Controle de Áreas"
        # pasta deste processo
        self.processo_path = os.path.join(self.secorpath,
                    self.processo_number+'-'+self.processo_year )
        if not os.path.exists(self.processo_path): # cria a pasta  se nao existir
            os.mkdir(self.processo_path)

    def salvaDadosGeraisSCM(self):
        # entra na pagina dados básicos do Processo do Cadastro  Mineiro
        self.dadosBasicosRetrieve()
        dadosgeraisfname = 'scm_dados_'+self.processo_number+self.processo_year
        # sobrescreve
        self.wpage.save(os.path.join(self.processo_path, dadosgeraisfname))

    def salvaDadosGeraisSCMPoligonal(self):
        # entra na pagina dados básicos do Processo do Cadastro  Mineiro (Poligonal)
        self.dadosPoligonalRetrieve()
        # sobrescreve
        dadosgeraisfname = 'scm_dados_poligonal_'+self.processo_number+self.processo_year
        self.wpage.save(os.path.join(self.processo_path, dadosgeraisfname))

    def salvaRetiradaInterferencia(self):
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1')
        formcontrols = {
            'ctl00$cphConteudo$txtNumProc': self.processo_number,
            'ctl00$cphConteudo$txtAnoProc': self.processo_year,
            'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # must be timout 50
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1',
                data=formdata, timeout=50)
        if not ( self.wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'):
            #print("Falhou salvar Retirada de Interferencia",  file=sys.stderr)
            # provavelmente estudo aberto
            return False
        #wpage.response.url # response url deve ser 'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'
        fname = 'sigareas_rinterferencia_'+self.processo_number+self.processo_year
        self.wpage.save(os.path.join(self.processo_path, fname))
        return True

    def cancelaUltimoEstudoInterferencia(self):
        """Danger Zone - cancela ultimo estudo em aberto sem perguntar mais nada"""
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx')
        #self.wpage.save('cancelar_estudo')
        formcontrols = {
            'ctl00$cphConteudo$txtNumero': self.processo_number,
            'ctl00$cphConteudo$txtAno': self.processo_year,
            'ctl00$cphConteudo$btnConsultar': 'Consultar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # Consulta
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        # wpage.save('cancelar_estudo')
        # Cancela
        formcontrols = {
            'ctl00$cphConteudo$txtNumero': self.processo_number,
            'ctl00$cphConteudo$txtAno': self.processo_year,
            'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.x': '12',
            'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.y': '12'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        if self.wpage.response.text.find(r'Estudo excluído com sucesso.') == -1:
            return False
        return True

    def getTabelaInterf(self):
        os.chdir(self.processo_path)
        interf_html = 'sigareas_rinterferencia_'+self.processo_number+self.processo_year+'.html'
        with open(interf_html, 'r') as f:
            htmltxt = f.read()
        soup = BeautifulSoup(htmltxt, features="lxml")
        mastertable = soup.find("td", {"class" : "TabelaGeral", "valign" : "top"})
        mastertable = mastertable.findChild("table", style="width: 100%; border: none;").find("td", align="right")
        interf_table = mastertable.find_all('tr')[1]
        rows = tableDataText(interf_table)
        self.tabela_interf = pd.DataFrame(rows[1:], columns=rows[0])
        return self.tabela_interf

    def getTabelaInterfEventosTodos(self):
        """
          Baixa todas as tabelas de eventos processos interferentes:
            - concatena em tabela única
            - converte data texto para datetime
            - converte numero evento para np.int
            - cria index ordem eventos para
        """
        self.tabela_interf_eventos = pd.DataFrame()
        for proc in self.tabela_interf.Processo:
            processo_number, processo_year = proc.split('/')
            #print(processo_number, processo_year)
            processo_events = getEventosSimples(self.wpage, processo_number, processo_year)
            #processo_events.drop(columns='Processo', axis=0, inplace=True)
            processo_events['ProAno'] = int(processo_year)
            processo_events['ProNum'] = int(processo_number)
            processo_events['EvSeq'] = len(processo_events)-processo_events.index.values.astype(int) # set correct order of events
            processo_events['Evento'] = processo_events['Evento'].astype(int)
            self.tabela_interf_eventos = self.tabela_interf_eventos.append(processo_events)
        # strdate to datetime
        self.tabela_interf_eventos.Data = self.tabela_interf_eventos.Data.apply(
                 lambda strdate: datetime.strptime(strdate, "%d/%m/%Y %H:%M:%S"))
        self.tabela_interf_eventos.reset_index(inplace=True,drop=True)
        # rearrange collumns in more meaningfully viewing
        columns_order = ['Processo', 'ProAno', 'ProNum', 'Evento', 'EvSeq', 'Descrição', 'Data']
        self.tabela_interf_eventos = self.tabela_interf_eventos[columns_order]
        return self.tabela_interf_eventos

    def recebeSICOP(self):
        """
        1. Must be authenticated with a aspnet Session Id
        2. Be aware that Fiddler causes problems with SSL authenthication making 1 impossible
        """
        self.wpage.get('https://sistemas.dnpm.gov.br/sicopii/SICOP.asp') # must be here to get Asp Cookie for SICOP
        formdata = {
            'CodProcessoAno': self.processo_year,
            'CodProcessoOrgao': '',
            'CodProcessoSeq': self.processo_number,
            'Pesquisar.x': '31',
            'Pesquisar.y': '9'
        }
        # consulta
        self.wpage.post('https://sistemas.dnpm.gov.br/sicopii/P/Receber/ReceberProcesso.asp?go=S', data=formdata)

        if not self.wpage.response.text.find(self.processo_number+'-'+self.processo_year):
            print('Nao achou, provavelmente não autenticado em sistemas.dnpm.gov.br')
            return False

        formdata = { 'chk1': 'on',
        'Botao.x': '37',
        'Botao.y': '8'}

        self.wpage.post('https://sistemas.dnpm.gov.br/sicopii/P/Receber/ReceberProcesso.asp?go=S', data=formdata)

        if not self.wpage.response.text.find('NAME="CodProcessoAno"'):
            return False
        else:
            return True
