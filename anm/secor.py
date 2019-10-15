import time
from requests_ntlm import HttpNtlmAuth
import re

import os, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import numpy as np
import pandas as pd
from datetime import datetime
#from .scm import *

from .scm import *
sys.path.append("..") # Adds higher directory to python modules path.
from web.htmlscrap import *

from enum import Enum

class wPage(wPage): # overwrites original class for ntlm authentication
    def __init__(self, user, passwd):
        """ntlm auth user and pass"""
        self.session = requests.Session()
        self.session.auth = HttpNtlmAuth(user, passwd)


# def copy_format(book, fmt):
#     """xlsxwriter cell-format 'clone' function"""
#     properties = [f[4:] for f in dir(fmt) if f[0:4] == 'set_']
#     dft_fmt = book.add_format()
#     return book.add_format({k : v for k, v in fmt.__dict__.items() if k in properties and dft_fmt.__dict__[k] != v})

def getEventosSimples(wpage, processostr):
    """ Retorna tabela de eventos simples para processo especificado
    wpage : class wPage
    processostr : str
    return : (Pandas DataFrame)"""
    processo_number, processo_year = numberyearPname(processostr)
    wpage.get(('http://sigareas.dnpm.gov.br/Paginas/Usuario/ListaEvento.aspx?processo='+
          processo_number+'_'+processo_year))
    htmltxt = wpage.response.content
    soup = BeautifulSoup(htmltxt, features="lxml")
    eventstable = soup.find("table", {'class': "BordaTabela"})
    rows = tableDataText(eventstable)
    return pd.DataFrame(rows[1:], columns=rows[0])


userhome = str(Path.home()) # get userhome folder
# eventos que inativam or ativam processo
__secor_path__ = os.path.join(userhome, r'Documents\Controle_Areas')
__eventos_scm__ = os.path.join(__secor_path__,
                        r'Secorpy\eventos_scm_09102019.xls')

class Estudo(Processo):
    """
    - Analise de Requerimento de Pesquisa - opcao 0
    - Analise de Formulario 1 - opcao 1
    - Analise de Opcao de Area - opcao 2
    """
    def __init__(self, processostr, wpage, option="Requerimento"):
        """
        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        super().__init__(processostr, wpage)
        # pasta padrao salvar processos formulario 1
        if option == "Requerimento":
            self.secorpath = os.path.join(__secor_path__, 'Requerimento')
        elif option == "Formulario1":
            self.secorpath = os.path.join(__secor_path__, 'Formulario1')
        elif option == "Opcao":
            self.secorpath = os.path.join(__secor_path__, 'Opcao')
        # pasta deste processo
        self.processo_path = os.path.join(self.secorpath,
                    self.processo_number+'-'+self.processo_year )
        if not os.path.exists(self.processo_path): # cria a pasta  se nao existir
            os.mkdir(self.processo_path)

    def salvaDadosGeraisSCM(self):
        # entra na pagina dados básicos do Processo do Cadastro  Mineiro
        if not self.dadosBasicosRetrieve():
            return False
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
            return False             # Falhou salvar Retirada de Interferencia # provavelmente estudo aberto
        fname = 'sigareas_rinterferencia_'+self.processo_number+self.processo_year
        self.wpage.save(os.path.join(self.processo_path, fname))
        return True

    def salvaEstudoOpcaoDeArea(self):
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=8')
        formcontrols = {
            'ctl00$cphConteudo$txtNumProc': self.processo_number,
            'ctl00$cphConteudo$txtAnoProc': self.processo_year,
            'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # must be timout 50
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=8',
                data=formdata, timeout=50)
        if not ( self.wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=8'):
            #print("Falhou salvar Retirada de Interferencia",  file=sys.stderr)
            # provavelmente estudo aberto
            return False
        #wpage.response.url # response url deve ser 'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'
        fname = 'sigareas_opcao_'+self.processo_number+self.processo_year
        self.wpage.save(os.path.join(self.processo_path, fname))
        return True

    def cancelaUltimoEstudo(self):
        """Danger Zone - cancela ultimo estudo em aberto sem perguntar mais nada:
        - estudo de retirada de Interferencia
        - estudo de opcao de area
        """
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

    def getTabelaInterferencia(self):
        if hasattr(self, 'tabela_interf'):
            return self.tabela_interf
        os.chdir(self.processo_path)
        interf_html = 'sigareas_rinterferencia_'+self.processo_number+self.processo_year+'.html'
        with open(interf_html, 'r') as f:
            htmltxt = f.read()
        soup = BeautifulSoup(htmltxt, features="lxml")
        # check connection failure (this table must allways be here)
        if htmltxt.find("ctl00_cphConteudo_gvLowerLeft") == -1:
            raise ConnectionError('Did not connect to sigareas r-interferencia')
        interf_table = soup.find("table", {"id" : "ctl00_cphConteudo_gvLowerRight"})
        if interf_table is None: # possible no interferencia at all
            return False # nenhuma interferencia SHOW!!
        rows = tableDataText(interf_table)
        self.tabela_interf = pd.DataFrame(rows[1:], columns=rows[0])
        # instert list of processos associados for each processo interferente
        self.tabela_interf['Assoc'] = None
        data_tag = self.specifyData(['associados'])
        for row in self.tabela_interf.iterrows(): # takes some time
            processo = Processo(row[1].Processo, self.wpage)
            if not processo.dadosBasicosGet(data_tag):
                printf('getTabelaInterferencia - failed dadosBasicosGet', file=sys.stderr)
                return
            if not (processo.dados['associados'][0][0] == 'Nenhum processo associado.'):
                print(processo.dados['associados'][1:])
                self.tabela_interf.loc[row[0], 'Assoc'] = processo.dados['associados'][1:]
            del processo
        return True

    def getTabelaInterferenciaTodos(self):
        """
          Baixa todas as tabelas de eventos processos interferentes:
            - concatena em tabela única
            - converte data texto para datetime
            - converte numero evento para np.int
            - cria index ordem eventos para
        """
        if not hasattr(self, 'tabela_interf'):
            if not self.getTabelaInterferencia(): # there is no interference !
                return False

        if hasattr(self, 'tabela_interf_eventos'):
            return self.tabela_interf_eventos

        self.tabela_interf_eventos = pd.DataFrame()
        for row in self.tabela_interf.iterrows():
            processo_events = getEventosSimples(self.wpage, row[1][1])
            #processo_events['ProAno'] = int(processo_year)
            #processo_events['ProNum'] = int(processo_number)
            processo_events['EvSeq'] = len(processo_events)-processo_events.index.values.astype(int) # set correct order of events
            processo_events['Evento'] = processo_events['Evento'].astype(int)
            # put count of associados
            processo_events['Assoc']  = 0 if row[1]['Assoc'] is None else len(row[1]['Assoc'])
            self.tabela_interf_eventos = self.tabela_interf_eventos.append(processo_events)

        # strdate to datetime comparacao prioridade
        self.tabela_interf_eventos.Data = self.tabela_interf_eventos.Data.apply(
                 lambda strdate: datetime.strptime(strdate, "%d/%m/%Y %H:%M:%S"))
        self.tabela_interf_eventos.reset_index(inplace=True,drop=True)
        # rearrange collumns in more meaningfully viewing
        columns_order = ['Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 'Assoc']
        self.tabela_interf_eventos = self.tabela_interf_eventos[columns_order]
        ### Todos os eventos posteriores a data de prioridade são marcados
        # como 0 na coluna Prioridade otherwise 1
        if not hasattr(self, 'prioridade'):
            self.prioridade = self.getPrioridade()
        self.tabela_interf_eventos['DataPrior'] = self.prioridade
        self.tabela_interf_eventos['EvPrior'] = True
        self.tabela_interf_eventos['EvPrior'] = self.tabela_interf_eventos.apply(
            lambda row: True if row['Data'] < self.prioridade else False, axis=1)
        ### fill-in column with inativam or ativam processo for each event
        ### using excel 'eventos_scm_09102019.xls'
        eventos = pd.read_excel(__eventos_scm__)
        eventos.drop(columns=['nome'],inplace=True)
        eventos.columns = ['Evento', 'Inativ'] # rename columns
        # join Inativ column -1/1 inativam or ativam processo
        self.tabela_interf_eventos = self.tabela_interf_eventos.join(eventos.set_index('Evento'), on='Evento')
        self.tabela_interf_eventos.Inativ = self.tabela_interf_eventos.Inativ.fillna(0) # not an important event
        #### processos associados não 300 baixar
        return True

    def excelInterferencia(self):
        if not hasattr(self, 'tabela_interf_eventos'):
            self.getTabelaInterferenciaTodos()
        interf_eventos = self.tabela_interf_eventos.copy() # needed due to str conversion
        dataformat = (lambda x: x.strftime("%d/%m/%Y %H:%M:%S"))
        interf_eventos.Data = interf_eventos.Data.apply(dataformat)
        interf_eventos.DataPrior = interf_eventos.DataPrior.apply(dataformat)
        excelname = ('eventos_prioridade_' + self.processo_number
                            + self.processo_year+'.xlsx')
        # Get max string size each collum for setting excel width column
        txt_table = interf_eventos.values.astype(str).T
        minsize = np.apply_along_axis(lambda array: np.max([ len(string) for string in array ] ),
                            arr=txt_table, axis=-1) # maximum string size in each column
        headers = np.array([ len(string) for string in interf_eventos.columns ]) # maximum string size each header
        colwidths = np.maximum(minsize, headers) + 5 # 5 characters of space more
        # number of rows
        nrows = len(interf_eventos)
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(excelname, engine='xlsxwriter')
        # Convert the dataframe to an XlsxWriter Excel object.
        interf_eventos.to_excel(writer, sheet_name='Sheet1', index=False)
        # Get the xlsxwriter workbook and worksheet objects.
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']
        # Add a background color format.
        fmt_ok1 = workbook.add_format( # ligh blue from GIMP
                {'bg_color': '#78B0DE', 'font_color': 'black',
                'align' : 'center'})
        fmt_ok2 = workbook.add_format(  # white
                {'bg_color': '#FFFFFF', 'font_color': 'black',
                'align' : 'center'})
        # dont have clone method (copy)
        fmt_dead1 = workbook.add_format(
                {'bg_color': '#78B0DE', 'font_color': 'red',
                'align' : 'center'})
        fmt_dead2 = workbook.add_format(
                {'bg_color': '#FFFFFF', 'font_color': 'red',
                'align' : 'center'})
        #bg_fmt_dead = workbook.add_format({'bg_color': '#FFFFFF'}) # nao prioritario
        #bg_fmt_dead.set_font_color('#FF0000')
        i=0 # each process row share the same bg color
        for processo in interf_eventos.groupby('Processo', sort=False):
            # odd or even color change by process
            cell_fmt = (fmt_ok1 if i%2==0 else fmt_ok2)
            # dead or alive check summing eventos inativam/ativam
            alive = np.sum(processo[1].Inativ.values)
            if alive < 0:
                cell_fmt = (fmt_dead1 if i%2==0 else fmt_dead2)
            for row in processo[1].index:
                worksheet.set_row(row+1, None, cell_fmt)
            i += 1
        # Set column width
        for i in range(len(colwidths)):
            # set_column(first_col, last_col, width, cell_format, options)
            worksheet.set_column(i, i, colwidths[i])
        # Close the Pandas Excel writer and output the Excel file.
        writer.save()

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
