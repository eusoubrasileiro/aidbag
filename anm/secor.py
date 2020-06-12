import time
from requests_ntlm import HttpNtlmAuth
import re

import os, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# threading
import copy
from multiprocessing.dummy import Pool as ThreadPool
import itertools

import numpy as np
import pandas as pd
from datetime import datetime
#from .scm import *

from .scm import *
sys.path.append("..") # Adds higher directory to python modules path.
from web.htmlscrap import *
from .SEI import *

from enum import Enum

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
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df.Processo = df.Processo.apply(lambda x: fmtPname(x)) # standard names
    return df


docs_externos_sei_tipo = [ 'Estudo',
        'Minuta', 'Minuta', 'Estudo']

docs_externos_sei_txt = [ 'de Retirada de Interferência', # Nome na Arvore
        'Pré de Alvará', 'de Licenciamento', 'de Opção' ]

def IncluiDocumentoExternoSEI(sei, ProcessoNUP, doc=0, pdf_path=None):
    """
    Inclui pdf como documento externo no SEI

    doc :
        0 - Estudo - 'de Retirada de Interferência'
        1 - Minuta - 'Pré de Alvará'
        2 - Minuta - 'de Licenciamento'
        3 - Estudo - 'de Opção'

    pdf_path :
        if None cria sem anexo
    """
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(0) # Inclui Externo
    # Preenchendo
    sei.driver.find_element_by_id('selSerie').send_keys(docs_externos_sei_tipo[doc]) # Tipo de Documento
    # Data do Documento
    sei.driver.find_element_by_id('txtDataElaboracao').send_keys(datetime.today().strftime('%d/%m/%Y')) # put TODAY
    sei.driver.find_element_by_id('txtNumero').send_keys(docs_externos_sei_txt[doc]) # Nome na Arvore
    sei.driver.find_element_by_id('optNato').click() #   Nato-digital
    sei.driver.find_element_by_id('lblPublico').click() # Publico
    if pdf_path is not None: # existe documento para anexar
        file = sei.driver.find_element_by_id('filArquivo') # Upload PDF
        file.send_keys(pdf_path)
    # save = sei.driver.find_element_by_id('btnSalvar')
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

userhome = str(Path.home()) # get userhome folder
# eventos que inativam or ativam processo
__secor_path__ = os.path.join(userhome, r'Documents\Controle_Areas')
__eventos_scm__ = os.path.join(__secor_path__,
                        r'Secorpy\eventos_scm_12032020.xls')

class Estudo:
    """
    - Analise de Requerimento de Pesquisa - opcao 0
    - Analise de Formulario 1 - opcao 1
    - Analise de Opcao de Area - opcao 2
    - Batch Requerimento de Pesquisa - opcao 3
    """
    def __init__(self, processostr, wpage, option=3, dados=3, verbose=True):
        """
        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        self.processo = GetProcesso(processostr, wpage, dados, verbose)
        self.wpage = wpage
        self.verbose = verbose
        # pasta padrao salvar processos formulario 1
        if option == 0:
            self.secorpath = os.path.join(__secor_path__, 'Requerimento')
        elif option ==  1:
            self.secorpath = os.path.join(__secor_path__, 'Formulario1')
        elif option == 2:
            self.secorpath = os.path.join(__secor_path__, 'Opcao')
        elif option == 3:
            self.secorpath = os.path.join(__secor_path__, r'Requerimento\Batch')
        # pasta deste processo
        self.processo_path = os.path.join(self.secorpath,
                    self.processo.number+'-'+self.processo.year )
        if not os.path.exists(self.processo_path): # cria a pasta  se nao existir
            os.mkdir(self.processo_path)

    def salvaDadosBasicosSCM(self):
        # entra na pagina dados básicos do Processo do Cadastro  Mineiro
        if not hasattr(self, 'scm_dadosbasicosmain_response'):
            self.processo._dadosBasicosRetrieve()
        dadosbasicosfname = 'scm_basicos_'+self.processo.number+self.processo.year
        # sobrescreve
        self.processo.wpage.save(os.path.join(self.processo_path, dadosbasicosfname))

    def salvaDadosPoligonalSCM(self):
        # entra na pagina dados básicos do Processo do Cadastro  Mineiro (Poligonal)
        if not hasattr(self, 'scm_dadosbasicospoli_response'):
            self.processo._dadosPoligonalRetrieve()
        # sobrescreve
        dadospolyfname = 'scm_poligonal_'+self.processo.number+self.processo.year
        self.processo.wpage.save(os.path.join(self.processo_path, dadospolyfname))

    def salvaRetiradaInterferencia(self):
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1')
        formcontrols = {
            'ctl00$cphConteudo$txtNumProc': self.processo.number,
            'ctl00$cphConteudo$txtAnoProc': self.processo.year,
            'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # must be timout 2 minutes
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1',
                data=formdata, timeout=(2*60))
        if not ( self.wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'):
            return False             # Falhou salvar Retirada de Interferencia # provavelmente estudo aberto
        fname = 'sigareas_rinterferencia_'+self.processo.number+self.processo.year
        self.wpage.save(os.path.join(self.processo_path, fname))
        return True

    def salvaEstudoOpcaoDeArea(self):
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=8')
        formcontrols = {
            'ctl00$cphConteudo$txtNumProc': self.processo.number,
            'ctl00$cphConteudo$txtAnoProc': self.processo.year,
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
        fname = 'sigareas_opcao_'+self.processo.number+self.processo.year
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
            'ctl00$cphConteudo$txtNumero': self.processo.number,
            'ctl00$cphConteudo$txtAno': self.processo.year,
            'ctl00$cphConteudo$btnConsultar': 'Consultar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # Consulta
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        # wpage.save('cancelar_estudo')
        # Cancela
        formcontrols = {
            'ctl00$cphConteudo$txtNumero': self.processo.number,
            'ctl00$cphConteudo$txtAno': self.processo.year,
            'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.x': '12',
            'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.y': '12'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        if self.wpage.response.text.find(r'Estudo excluído com sucesso.') == -1:
            return False
        return True

    def getTabelaInterferencia(self):
        self.tabela_interf = None
        os.chdir(self.processo_path)
        interf_html = 'sigareas_rinterferencia_'+self.processo.number+self.processo.year+'.html'
        with open(interf_html, 'r') as f:
            htmltxt = f.read()
        soup = BeautifulSoup(htmltxt, features="lxml")
        # check connection failure (this table must allways be here)
        if htmltxt.find("ctl00_cphConteudo_gvLowerLeft") == -1:
            raise ConnectionError('Did not connect to sigareas r-interferencia')
        interf_table = soup.find("table", {"id" : "ctl00_cphConteudo_gvLowerRight"})
        if interf_table is None: # possible! no interferencia at all
            return self.tabela_interf # nenhuma interferencia SHOW!!
        rows = tableDataText(interf_table)
        self.tabela_interf = pd.DataFrame(rows[1:], columns=rows[0])
        # instert list of processos associados for each processo interferente
        self.tabela_interf['Dads'] = 0
        self.tabela_interf['Sons'] = 0
        self.tabela_interf['Ativo'] = 'Sim'
        # POOL OF THREADS
        # due many calls to python.requests taking much time
        processos_interferentes = [fmtPname(row[1]['Processo'])
                                    for row in self.tabela_interf.iterrows()]
        # Unique Process Only
        processos_interferentes = list(set(processos_interferentes))
        # cannot have this here for now ...
        # hack to workaround
        # create multiple python requests sessions
        # self.processes_interf = None
        # with ThreadPool(len(processos_interferentes)) as pool:
        #     # Open the URLs in their own threads and return the results
        #     #processo = Processo(row[1].Processo, self.wpage, verbose=self.verbose)
        #     self.processes_interf = pool.starmap(Processo,
        #                                 zip(processos_interferentes,
        #                                     itertools.repeat(self.wpage),
        #                                     itertools.repeat(3),
        #                                     itertools.repeat(self.verbose)))
        # # create dict of key process name , value process objects
        # self.processes_interf = dict(zip(list(map(lambda p: p.processostr, self.processes_interf)),
        #                                 self.processes_interf))
        self.processes_interf = {}
        for process_name in processos_interferentes:
            processo = GetProcesso(process_name, self.wpage, 3, self.verbose)
            self.processes_interf[process_name] = processo

        # self.processes_interf[processo_name] = processo # save on interf process object list
        # tabela c/ processos associadoas # aos processos interferentes
        self.tabela_assoc = pd.DataFrame(columns=['Main', 'Prior', 'Processo',  'Titular', 'Tipo',
                'Assoc', 'DesAssoc', 'Original', 'Obs'])
        for row in self.tabela_interf.iterrows():
            # it seams excel writer needs every process name have same length string 000.000/xxxx (12)
            # so reformat process name
            processo_name = fmtPname(row[1]['Processo'])
            processo = self.processes_interf[processo_name]
            self.tabela_interf.loc[row[0], 'Processo'] = processo_name
            self.tabela_interf.loc[row[0], 'Ativo'] = processo.dados['ativo']
            if processo.associados:
                assoc_items = pd.DataFrame(processo.dados['associados'][1:],
                        columns=self.tabela_assoc.columns[2:])
                assoc_items['Main'] = processo.processostr
                assoc_items['Prior'] = (processo.prioridadec if hasattr(processo, 'prioridadec') else processo.prioridade)
                # number of direct sons/ ancestors
                self.tabela_interf.loc[row[0], 'Sons'] = len(processo.dsons)
                self.tabela_interf.loc[row[0], 'Dads'] = len(processo.anscestors)
                self.tabela_assoc = self.tabela_assoc.append(assoc_items, sort=False, ignore_index=True)
        return self.tabela_interf

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
            # TODO remove getEventosSimples and extract everything from dados basicos
            processo_events = getEventosSimples(self.wpage, row[1][1])
            # get columns 'Publicação D.O.U' & 'Observação' from dados_basicos
            processo_dados = self.processes_interf[fmtPname(row[1][1])].dados
            dfbasicos = pd.DataFrame(processo_dados['eventos'][1:],
                        columns=processo_dados['eventos'][0])

            processo_events['EvSeq'] = len(processo_events)-processo_events.index.values.astype(int) # set correct order of events
            processo_events['Evento'] = processo_events['Evento'].astype(int)
            # put count of associados father and sons
            processo_events['Dads'] = row[1]['Dads']
            processo_events['Sons'] =row[1]['Sons']
            processo_events['Ativo'] = row[1]['Ativo']
            processo_events['Obs'] = dfbasicos['Observação']
            processo_events['DOU'] = dfbasicos['Publicação D.O.U']
            self.tabela_interf_eventos = self.tabela_interf_eventos.append(processo_events)

        # strdate to datetime comparacao prioridade
        self.tabela_interf_eventos.Data = self.tabela_interf_eventos.Data.apply(
                 lambda strdate: datetime.strptime(strdate, "%d/%m/%Y %H:%M:%S"))
        self.tabela_interf_eventos.reset_index(inplace=True,drop=True)
        # rearrange collumns in more meaningfully viewing
        columns_order = ['Ativo','Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 'Dads', 'Sons', 'Obs', 'DOU']
        self.tabela_interf_eventos = self.tabela_interf_eventos[columns_order]
        ### Todos os eventos posteriores a data de prioridade são marcados
        # como 0 na coluna Prioridade otherwise 1
        self.tabela_interf_eventos['DataPrior'] = self.processo.prioridade
        self.tabela_interf_eventos['EvPrior'] = 0 # 1 prioritario 0 otherwise
        self.tabela_interf_eventos['EvPrior'] = self.tabela_interf_eventos.apply(
            lambda row: 1 if row['Data'] < self.processo.prioridade else 0, axis=1)
        ### fill-in column with inativam or ativam processo for each event
        ### using excel 'eventos_scm_09102019.xls'
        eventos = pd.read_excel(__eventos_scm__)
        eventos.drop(columns=['nome'],inplace=True)
        eventos.columns = ['Evento', 'Inativ'] # rename columns
        # join Inativ column -1/1 inativam or ativam processo
        self.tabela_interf_eventos = self.tabela_interf_eventos.join(eventos.set_index('Evento'), on='Evento')
        self.tabela_interf_eventos.Inativ = self.tabela_interf_eventos.Inativ.fillna(0) # not an important event
        # Add a 'Prior' (Prioridade) Collumn At the Beggining
        self.tabela_interf_eventos['Prior'] = 1
        for name, events in self.tabela_interf_eventos.groupby('Processo'):
            self.tabela_interf_eventos.loc[self.tabela_interf_eventos.Processo == name, 'Prior'] = (
            1*(events.EvPrior.sum() > 0 and events.Inativ.sum() > -1))
        # re-rearrange columns
        newcolumns = ['Prior'] + self.tabela_interf_eventos.columns[:-1].tolist()
        self.tabela_interf_eventos = self.tabela_interf_eventos[newcolumns]
        # place Observação/DOU in the end (last columns)
        newcolumns = self.tabela_interf_eventos.columns.tolist()
        newcolumns = [e for e in newcolumns if e not in ('Obs', 'DOU')] + ['Obs', 'DOU']
        self.tabela_interf_eventos = self.tabela_interf_eventos[newcolumns]

    def excelInterferencia(self):
        if not hasattr(self, 'tabela_interf_eventos'):
            self.getTabelaInterferenciaTodos()
        interf_eventos = self.tabela_interf_eventos.copy() # needed due to str conversion
        dataformat = (lambda x: x.strftime("%d/%m/%Y %H:%M:%S"))
        interf_eventos.Data = interf_eventos.Data.apply(dataformat)
        interf_eventos.DataPrior = interf_eventos.DataPrior.apply(dataformat)
        excelname = ('eventos_prioridade_' + self.processo.number
                            + self.processo.year+'.xlsx')
        # Get max string size each collum for setting excel width column
        txt_table = interf_eventos.values.astype(str).T
        minsize = np.apply_along_axis(lambda array: np.max([ len(string) for string in array ] ),
                            arr=txt_table, axis=-1) # maximum string size in each column
        headers = np.array([ len(string) for string in interf_eventos.columns ]) # maximum string size each header
        colwidths = np.maximum(minsize, headers) + 5 # 5 characters of space more
        # Observação / DOU set size to header size - due a lot of text
        colwidths[-1] = headers[-1] + 10 # Observação
        colwidths[-2] = headers[-2] + 10 # DOU
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
        writer.close()
        self.excelInterferenciaAssociados()

    def excelInterferenciaAssociados(self):
        """Processos interferentes com processos associados"""
        if not hasattr(self, 'tabela_assoc'):
            return
        excelname = ('eventos_prioridade_assoc_' + self.processo.number
                            + self.processo.year+'.xlsx')
        self.tabela_assoc.to_excel(excelname, index=False)

    def recebeSICOP(self):
        """
        1. Must be authenticated with a aspnet Session Id
        2. Be aware that Fiddler causes problems with SSL authenthication making 1 impossible
        """
        self.wpage.get('https://sistemas.anm.gov.br/sicopii/SICOP.asp') # must be here to get Asp Cookie for SICOP
        formdata = {
            'CodProcessoAno': self.processo.year,
            'CodProcessoOrgao': '',
            'CodProcessoSeq': self.processo.number,
            'Pesquisar.x': '31',
            'Pesquisar.y': '9'
        }
        # consulta
        self.wpage.post('https://sistemas.anm.gov.br/sicopii/P/Receber/ReceberProcesso.asp?go=S', data=formdata)

        if not self.wpage.response.text.find(self.processo.number+'-'+self.processo.year):
            print('Nao achou, provavelmente não autenticado em sistemas.anm.gov.br')
            return False

        formdata = { 'chk1': 'on',
        'Botao.x': '37',
        'Botao.y': '8'}

        self.wpage.post('https://sistemas.anm.gov.br/sicopii/P/Receber/ReceberProcesso.asp?go=S', data=formdata)

        if not self.wpage.response.text.find('NAME="CodProcessoAno"'):
            return False
        else:
            return True

    def incluiDocumentoExternoSEI(self, doc=0, pdf_path=None):
        """
        Loga no SEI (se já não estiver logado) e
        inclui pdf como documento externo

        doc :
            0 - Estudo - 'de Retirada de Interferência'
            1 - Minuta - 'Pré de Alvará'
            2 - Minuta - 'de Licenciamento'
            3 - Estudo - 'de Opção'

        pdf_path :
            if None cria sem anexo
        """
        if not hasattr(self, 'sei'):
            user = self.wpage.user
            passwd = self.wpage.passwd
            self.sei = SEI.SEI(user, passwd)

        IncluiDocumentoExternoSEI(self.sei, self.Processo.NUP, doc, pdf_path)

def EstudoBatchRun(wpage, processos):
    for processo in processos:
        estudo = Estudo(processo, wpage, 0)
        estudo.salvaDadosBasicosSCM()
        if not estudo.salvaRetiradaInterferencia():
            raise Exception('didnt download retirada de interferencia')
        if not estudo.cancelaUltimoEstudo():
            raise Exception('couldnt cancel ultimo estudo')
        if estudo.getTabelaInterferencia() is not None:
            estudo.getTabelaInterferenciaTodos()
            estudo.excelInterferencia()
            estudo.excelInterferenciaAssociados()



### Inclui todos os pdfs nas pastas specificadas no SEI
# Seguindo nome se é licença ou minuta
from anm import secor
from anm import SEI
from anm import scm
from web import htmlscrap
import tqdm
import importlib
import glob
import os
import re
from bs4 import BeautifulSoup

def IncluiDocumentosSEIFolders(sei, nfirst=1, tipo='Requerimento', path="Batch"):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI.
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    - Estudo
    - Minuta
    - Marca Acompanhamento Especial

    TODO:
        - Despacho
    """
    os.chdir(__secor_path__)
    os.chdir(tipo)
    os.chdir(path)

    process_folders = glob.glob('*')
    process_folders = process_folders[:nfirst]

    for process_folder in process_folders:
        process_path = os.path.join(os.getcwd(), process_folder)
        os.chdir(process_folder) # enter on process folder
        #  GET NUP and tipo from html
        scm_html = glob.glob('*.html')[0] # first html file on folder
        with open(scm_html, 'r') as f: # get NUP by html scm
            html = f.read()
        os.chdir('..') # go back from process folder
        soup = BeautifulSoup(html, features="lxml")
        data = htmlscrap.dictDataText(soup, scm.scm_data_tags)
        NUP = data['NUP'].strip()
        tipo = data['tipo'].strip()
        # Estudo de Interferência deve chamar 'R.pdf'
        pdf_interferencia = os.path.join(process_path, 'R.pdf')
        # Inclui Estudo pdf como Doc Externo no SEI
        IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)
        # pdf adicional Minuta de Licenciamento ou Pré Minuta de Alvará deve chamar 'Imprimir.pdf'
        pdf_adicional = os.path.join(process_path, 'Imprimir.pdf')
        if os.path.isfile(pdf_adicional):
            if tipo == 'Requerimento de Registro de Licença':
                # 2 - Minuta - 'de Licenciamento'
                IncluiDocumentoExternoSEI(sei, NUP, 2, pdf_adicional)
            elif tipo == 'Requerimento de Autorização de Pesquisa':
                # 1 - Minuta - 'Pré de Alvará'
                IncluiDocumentoExternoSEI(sei, NUP, 1, pdf_adicional)
            # IncluiDespacho(sei, NUP, 6) - Recomenda análise de plano
        else: # Despacho diferente se não existe segundo pdf
            pass
        sei.ProcessoIncluiAEspecial(1) # 1 - me
