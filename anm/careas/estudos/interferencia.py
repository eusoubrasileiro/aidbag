import os
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
from datetime import datetime

from ..constants import config, processPathSecor
from ..scm import *
from ....web import htmlscrap 
from ..SEI import *

# fases necessarias e obrigatorias para retirada de interferencia 
interferencia_fases = ['Requerimento de Pesquisa', 'Direito de Requerer a Lavra', 
'Requerimento de Lavra', 'Requerimento de Licenciamento', 'Requerimento de Lavra Garimpeira'] 

def inFaseRInterferencia(fase_str):
    for fase in interferencia_fases:
        if fase.find(fase_str.strip()) != -1:
            return True
    return False 

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
    rows = htmlscrap.tableDataText(eventstable)
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df.Processo = df.Processo.apply(lambda x: fmtPname(x)) # standard names
    return df

class CancelaUltimoEstudoFailed(Exception):
    """could not cancel ultimo estudo sigareas"""
    pass

class DownloadRetiradaInterferenciaFailed(Exception):
    """could not download retirada de interferencia"""
    pass 

class Interferencia:
    """Estudo de Retirada de InterferĂȘncia SIGAREAS"""
    def __init__(self, wpage, processostr, dados=SCM_SEARCH.PRIORIDADE, verbose=True):
        """        
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        processostr : numero processo format xxx.xxx/ano
        """
        self.processo = Processo.Get(processostr, wpage, dados, verbose)
        self.wpage = wpage
        self.verbose = verbose       
        self.processo_path = processPathSecor(self.processo)

    @staticmethod
    def make(wpage, processostr, verbose=False, download=True):
        """
        make folders and spreadsheets for specified process
        to aid on priority analysis

        * processostr : str
            numero processo format xxx.xxx/ano
        * wpage : wPage html 
            webpage scraping class com login e passwd preenchidos
        * download: bool
            default to allways download instead of using files saved on folder  
            Only works for retirada interferencia html

        * returns: instance `Interferencia`

        * exceptions: 
            `DownloadRetiradaInterferenciaFailed`, `CancelaUltimoEstudoFailed`
        """
        estudo = Interferencia(wpage, processostr, dados=SCM_SEARCH.PRIORIDADE, verbose=verbose)
        estudo.processo.salvaDadosBasicosHtml(estudo.processo_path)
        estudo.processo.salvaDadosPoligonalHtml(estudo.processo_path)                    
        # if fase correct MUST have access to retirada de 
        if inFaseRInterferencia(estudo.processo['fase']):
            if not estudo.salvaRetiradaInterferenciaHtml(estudo.processo_path, download):
                raise DownloadRetiradaInterferenciaFailed()
            else:
                # only if retirada interferencia html is saved we can create spreadsheets
                # sometimes we just don't need it   
                try:               
                    if estudo.getTabelaInterferencia(): # sometimes there is no interferences 
                        estudo.getTabelaInterferenciaTodos()
                        estudo.excelInterferencia()
                        estudo.excelInterferenciaAssociados()                
                finally: # if there was an exception cancela ultimo estudo
                    if not estudo.cancelaUltimoEstudo():
                        raise CancelaUltimoEstudoFailed()
        return estudo
    
    def salvaRetiradaInterferenciaHtml(self, html_path, download=True):
        fname = 'sigareas_rinterferencia_'+self.processo.number+'_'+self.processo.year
        if not os.path.exists(os.path.join(html_path, fname)) or download:
            self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1')
            formcontrols = {
                'ctl00$cphConteudo$txtNumProc': self.processo.number,
                'ctl00$cphConteudo$txtAnoProc': self.processo.year,
                'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
            }
            formdata = htmlscrap.formdataPostAspNet(self.wpage.response, formcontrols)
            # must be timout 2 minutes
            self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1',
                    data=formdata, timeout=config['secor_timeout'])
            if not ( self.wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'):
                return False             # Falhou salvar Retirada de Interferencia # provavelmente estudo aberto            
            self.wpage.save(os.path.join(html_path, fname))
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
        formdata = htmlscrap.formdataPostAspNet(self.wpage.response, formcontrols)
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
        formdata = htmlscrap.formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        if self.wpage.response.text.find(r'Estudo excluĂ­do com sucesso.') == -1:
            return False 
        return True

    def getTabelaInterferencia(self):
        interf_html = 'sigareas_rinterferencia_'+self.processo.number+'_'+self.processo.year+'.html'
        interf_html = os.path.join(self.processo_path, interf_html)
        with open(interf_html, "r", encoding="utf-8") as f:
            htmltxt = f.read()
        soup = BeautifulSoup(htmltxt, features="lxml")
        # check connection failure (this table must allways be here)
        if htmltxt.find("ctl00_cphConteudo_gvLowerLeft") == -1:
            raise ConnectionError('Did not connect to sigareas r-interferencia')
        interf_table = soup.find("table", {"id" : "ctl00_cphConteudo_gvLowerRight"})
        if interf_table is None: # possible! no interferencia at all
            return False # nenhuma interferencia SHOW!!
        rows = htmlscrap.tableDataText(interf_table)
        self.tabela_interf = pd.DataFrame(rows[1:], columns=rows[0])
        # instert list of processos associados for each processo interferente
        self.tabela_interf['Dads'] = 0
        self.tabela_interf['Sons'] = 0
        self.tabela_interf['Ativo'] = 'Sim'
        interferentes = [fmtPname(row[1]['Processo'])
                                    for row in self.tabela_interf.iterrows()]
        # Unique Process Only
        interferentes = list(set(interferentes))
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
        # self.processes_interf = dict(zip(list(map(lambda p: p.name, self.processes_interf)),
        #                                 self.processes_interf))
        self.Interferentes = {}
        for name in interferentes:
            processo = Processo.Get(name, self.wpage, SCM_SEARCH.PRIORIDADE, self.verbose)
            self.Interferentes[name] = processo
        # tabela c/ processos associadoas aos processos interferentes
        self.tabela_assoc = pd.DataFrame()
        for row in self.tabela_interf.iterrows():
            # it seams excel writer needs every process name have same length string 000.000/xxxx (12)
            # so reformat process name
            name = fmtPname(row[1]['Processo'])
            processo = self.Interferentes[name]
            self.tabela_interf.loc[row[0], 'Processo'] = name
            self.tabela_interf.loc[row[0], 'Ativo'] = processo['ativo']
            if processo.associados:
                assoc_items = pd.DataFrame({ "Main" : processo.name, "Target" : processo.associados.keys() })
                assoc_items = assoc_items.join(pd.DataFrame(processo.associados.values()))
                assoc_items.drop(columns='obj', inplace=True)
                # not using prioridade of associados
                # assoc_items['Prior'] = processo['prioridadec'] if processo['prioridadec'] else processo['prioridade']
                # number of direct sons/ ancestors
                self.tabela_interf.loc[row[0], 'Sons'] = len(processo['sons'])
                self.tabela_interf.loc[row[0], 'Dads'] = len(processo['parents'])
                self.tabela_assoc = pd.concat([self.tabela_assoc, assoc_items], sort=False, ignore_index=True, axis=0, join='outer')                
        return True

    def getTabelaInterferenciaTodos(self):
        """
          Baixa todas as tabelas de eventos processos interferentes:
            - concatena em tabela Ășnica
            - converte data texto para datetime
            - converte numero evento para np.int
            - cria index ordem eventos para
        """
        if not hasattr(self, 'tabela_interf'):
            if self.getTabelaInterferencia(): # there is no interference !
                return False
        if hasattr(self, 'tabela_interf_eventos'):
            return self.tabela_interf_eventos

        self.tabela_interf_eventos = pd.DataFrame()
        for row in self.tabela_interf.iterrows():
            # cannot remove getEventosSimples and extract everything from dados basicos
            # dados basico scm data nao inclui hora! cant use only scm
            processo_events = getEventosSimples(self.wpage, row[1][1])
            # get columns 'PublicaĂ§ĂŁo D.O.U' & 'ObservaĂ§ĂŁo' from dados basicos
            eventos = self.Interferentes[fmtPname(row[1][1])]['eventos']
            dfbasicos = pd.DataFrame(eventos[1:],
                        columns=eventos[0])
            processo_events['EvSeq'] = len(processo_events)-processo_events.index.values.astype(int) # set correct order of events
            processo_events['Evento'] = processo_events['Evento'].astype(int)
            # put count of associados father and sons
            processo_events['Dads'] = row[1]['Dads']
            processo_events['Sons'] =row[1]['Sons']
            processo_events['Ativo'] = row[1]['Ativo']
            processo_events['Obs'] = dfbasicos['ObservaĂ§ĂŁo']
            processo_events['DOU'] = dfbasicos['PublicaĂ§ĂŁo D.O.U']
            # strdate to datetime comparacao prioridade
            processo_events.Data = processo_events.Data.apply(
                lambda strdate: datetime.strptime(strdate, "%d/%m/%Y %H:%M:%S"))
            # to add an additional row caso a primeira data dos eventos diferente
            # da prioritĂĄria correta
            processo_prioridadec = self.Interferentes[fmtPname(row[1][1])]['prioridadec']
            if processo_events['Data'].values[-1] > np.datetime64(processo_prioridadec):
                #processo_events = processo_events.append(processo_events.tail(1), ignore_index=True) # repeat the last/or first
                processo_events = pd.concat([processo_events, processo_events.tail(1)], ignore_index=True, axis=0, join='outer')
                processo_events.loc[processo_events.index[-1], 'Data'] = np.datetime64(processo_prioridadec)
                processo_events.loc[processo_events.index[-1], 'EvSeq'] = -3 # represents added by here
            # SICOP parte if fisico main available
            # might have more or less lines than SCM eventos
            # use only what we have rest will be empty
            #processo_events['SICOP FISICO PRINCIPAL MOVIMENTACAO']
            # DATA:HORA	SITUAĂĂO	UF	ĂRGĂO	PRIORIDADE	MOVIMENTADO	RECEBIDO	DATA REC.	REC. POR	GUIA
            self.tabela_interf_eventos = pd.concat([self.tabela_interf_eventos, processo_events], axis=0, join='outer')
            #self.tabela_interf_eventos = self.tabela_interf_eventos.append(processo_events)

        self.tabela_interf_eventos.reset_index(inplace=True,drop=True)
        # rearrange collumns in more meaningfully viewing
        columns_order = ['Ativo','Processo', 'Evento', 'EvSeq', 'DescriĂ§ĂŁo', 'Data', 'Dads', 'Sons', 'Obs', 'DOU']
        self.tabela_interf_eventos = self.tabela_interf_eventos[columns_order]
        ### Todos os eventos posteriores a data de prioridade sĂŁo marcados
        # como 0 na coluna Prioridade otherwise 1
        self.tabela_interf_eventos['DataPrior'] = self.processo['prioridadec']
        self.tabela_interf_eventos['EvPrior'] = 0 # 1 prioritario 0 otherwise
        self.tabela_interf_eventos['EvPrior'] = self.tabela_interf_eventos.apply(
            lambda row: 1 if row['Data'] <= self.processo['prioridadec'] else 0, axis=1)
        ### fill-in column with inativam or ativam processo for each event
        ### using excel 'eventos_scm_09102019.xls'
        eventos = pd.read_excel(config['eventos_scm'])
        eventos.drop(columns=['nome'],inplace=True)
        eventos.columns = ['Evento', 'Inativ'] # rename columns
        # join Inativ column -1/1 inativam or ativam processo
        self.tabela_interf_eventos = self.tabela_interf_eventos.join(eventos.set_index('Evento'), on='Evento')
        self.tabela_interf_eventos.Inativ = self.tabela_interf_eventos.Inativ.fillna(0) # not an important event
        # Add a 'Prior' (Prioridade) Collumn At the Beggining
        self.tabela_interf_eventos['Prior'] = 1
        # Prioridade considerando quando houve evento de inativaĂ§ĂŁo
        # se antes do atual nĂŁo Ă© prioritĂĄrio
        for process, events in self.tabela_interf_eventos.groupby('Processo', sort=False):
            # assume prioritĂĄrio ou nĂŁo pela data do primeiro evento
            # ou 0 se nĂŁo se sabe
            prior = 1 if events.iloc[-1]['EvPrior'] > 0 else 0
            alive = np.sum(events.Inativ.values) # alive or dead
            if alive < 0: # DEAD - get by data da Ășltima inativaĂ§ĂŁo
                data_inativ = events.loc[events.Inativ == -1]['Data'].values[0]
                if data_inativ  <= np.datetime64(self.processo['prioridadec']):
                    # morreu antes do atual, nĂŁo Ă© prioritĂĄrio
                    prior = -1
            self.tabela_interf_eventos.loc[
                self.tabela_interf_eventos.Processo == process, 'Prior'] = prior
            #self.tabela_interf_eventos.loc[self.tabela_interf_eventos.Processo == name, 'Prior'] = (
            #1*(events.EvPrior.sum() > 0 and events.Inativ.sum() > -1))
        # re-rearrange columns
        newcolumns = ['Prior'] + self.tabela_interf_eventos.columns[:-1].tolist()
        self.tabela_interf_eventos = self.tabela_interf_eventos[newcolumns]
        # place ObservaĂ§ĂŁo/DOU in the end (last columns)
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
        excelname = ('eventos_prioridade_' + self.processo.number + '_' 
                            + self.processo.year+'.xlsx')
        excelname = os.path.join(self.processo_path, excelname)
        # Get max string size each collum for setting excel width column
        txt_table = interf_eventos.values.astype(str).T
        minsize = np.apply_along_axis(lambda array: np.max([ len(string) for string in array ] ),
                            arr=txt_table, axis=-1) # maximum string size in each column
        headers = np.array([ len(string) for string in interf_eventos.columns ]) # maximum string size each header
        colwidths = np.maximum(minsize, headers) + 5 # 5 characters of space more
        # ObservaĂ§ĂŁo / DOU set size to header size - due a lot of text
        colwidths[-1] = headers[-1] + 10 # ObservaĂ§ĂŁo
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
        #######################################
        # Solution for troublesome
        # format managament on xlsxwriter
        # dict as a storage of excel workbook formats
        fmt_storage = {} # store unique workbook formats
        # alternating colors for background
        color1 = '#78B0DE' # ligh blue from GIMP
        color2 = '#FFFFFF'  # white
        # colors for dim or not fade a process
        fcolor1 = 'black' # alive by events
        fcolor2 = 'red' # fade process
        fmt = {'bg_color': '#FFFFFF', 'font_color': 'black',
               'align' : 'center', 'bold' : False}
        def row_fmt(i, dim, event=False):
            fmt['bg_color'] = (color1 if i%2==0 else color2) # odd or even color change by process
            if dim:
                fmt['font_color'] = 'red'
            else:
                fmt['font_color'] = 'black'
            if event:
                fmt['bold'] = True
            else:
                fmt['bold'] = False
            key = hash(str(fmt))
            excel_fmt = None
            if key in fmt_storage:
                excel_fmt = fmt_storage[key]
            else:
                excel_fmt = workbook.add_format(fmt)
                fmt_storage[key] = excel_fmt
            return excel_fmt
        #######################################
        i=0 # each process row share the same bg color
        for process, events in interf_eventos.groupby('Processo', sort=False):
            # prioritĂĄrio ou nĂŁo pela coluna 'Prior' primeiro value
            prior = events['Prior'].values[0] >= 0 # prioritĂĄrio ou unknown
            dead = events['Ativo'].values[0] == r'NĂŁo'
            dead_nprior = dead and (not prior) # only fade/dim/paint dead and not prior
            for idx, row in events.iterrows(): # processo row by row set format
                #excel row index is not zero based, that's why idx+1 bellow
                if row['Inativ'] > 0 or row['Inativ'] < 0: # revival event / die event
                    # make text bold
                    worksheet.set_row(idx+1, None, row_fmt(i, dead_nprior, True))
                else: # 0
                    worksheet.set_row(idx+1, None, row_fmt(i, dead_nprior, False))
            i += 1
        # Set column width
        for i in range(len(colwidths)):
            # set_column(first_col, last_col, width, cell_format, options)
            worksheet.set_column(i, i, colwidths[i])
        # Close the Pandas Excel writer and output the Excel file.
        writer.close()
        self.excelInterferenciaAssociados()

    def excelInterferenciaAssociados(self):
        """Processos interferentes com processos associados"""
        if not hasattr(self, 'tabela_assoc'):
            return
        excelname = ('eventos_prioridade_assoc_' + self.processo.number + '_'
                          + self.processo.year+'.xlsx')
        excelname = os.path.join(self.processo_path, excelname)
        self.tabela_assoc.to_excel(excelname, index=False)


# something else not sure will be usefull someday
# def salvaEstudoOpcaoDeAreaHtml(self, html_path):
#     self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=8')
#     formcontrols = {
#         'ctl00$cphConteudo$txtNumProc': self.processo.number,
#         'ctl00$cphConteudo$txtAnoProc': self.processo.year,
#         'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
#     }
#     formdata = formdataPostAspNet(self.wpage.response, formcontrols)
#     # must be timout 50
#     self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=8',
#             data=formdata, timeout=__secor_timeout)
#     if not ( self.wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=8'):
#         #print("Falhou salvar Retirada de Interferencia",  file=sys.stderr)
#         # provavelmente estudo aberto
#         return False
#     #wpage.response.url # response url deve ser 'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'
#     fname = 'sigareas_opcao_'+self.processo.number+'_'+self.processo.year
#     self.wpage.save(os.path.join(html_path, fname))
#     return True