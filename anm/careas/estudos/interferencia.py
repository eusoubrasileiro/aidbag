import os
import sys 
import traceback
import pathlib 
import numpy as np
from datetime import datetime
from unidecode import unidecode
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype as is_datetime
from bs4 import BeautifulSoup


from ..config import config
from ..scm import (    
    SCM_SEARCH,
    util,
    pud,
    ProcessManager,
    PoligonalErrorSCM,
    BasicosErrorSCM
)

from ..util import processPath

from ....web import htmlscrap 
from .scraping import (
    fetch_save_Html,
    cancelaUltimo,
    getEventosSimples
)



# fases necessarias e obrigatorias para retirada de interferencia 
interferencia_fases = ['Requerimento de Pesquisa', 'Direito de Requerer a Lavra', 
'Requerimento de Lavra', 'Requerimento de Licenciamento', 'Requerimento de Lavra Garimpeira'] 

 

def inFaseRInterferencia(fase_str):
    for fase in interferencia_fases:
        if fase.find(fase_str.strip()) != -1:
            return True
    return False

def prettyTableStr(table):
    """
    Prettify tabela interferencia to simplify interferencia analisis.
    After the first event rows values get removed.              
    """
    table = table.copy() 
    for name, group in table.groupby(table.Processo):
        # unecessary information - making visual analysis polluted
        table.loc[group.index[1:], 'Ativo'] = '' 
        table.loc[group.index[1:], 'Prior'] = ''  # 1'st will be replaced by a checkbox
        table.loc[group.index[1:], 'Processo'] = ''
        table.loc[group.index[1:], 'Dads'] = ''
        table.loc[group.index[1:], 'Sons'] = ''      
    return table 

def TableStr(table):
    """
    Dataframe columns are converted to text. To save as JSON.
    Nans to ''. Datetime to '%d/%m/%Y %H:%M:%S'    
    """
    table = table.copy() 
    # convert all datetimes to string '%d/%m/%Y %H:%M:%S'
    datetime_columns = table.select_dtypes(include='datetime64').columns.tolist()    
    table[datetime_columns] = table[datetime_columns].map(lambda x: x.strftime("%d/%m/%Y %H:%M:%S"))
    table.fillna('', inplace=True) # fill nan to ''
    table = table.astype(str)    
    return table 


class Interferencia:
    """Estudo de Retirada de Interferência SIGAREAS"""
    def __init__(self, wpage, processostr, verbose=True, getprocesso=True):
        """        
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        processostr : numero processo format xxx.xxx/ano
        """
        self._processo = None 
        self.processo_path = processPath(processostr, create=True)
        self.pud = pud(processostr)
        self.name = self.pud.str
        if getprocesso:
            self._processo = ProcessManager.GetorCreate(self.name, wpage, SCM_SEARCH.ALL, verbose)  
        self.number, self.year = self.pud.numberyear
        self.wpage = wpage
        self.verbose = verbose       
        """tabele de interferencia extraida do sigareas html"""
        self.tabela_interf = None        
        """tabele de inteferencia master criada a partir da acima self.tabela_interf"""
        self.tabela_interf_master = None 
        self.tabela_assoc = None 
        self.cancel_ultimo = False
        interf_html = (config['interferencia']['html_prefix']['this']+'_'+
                       '_'.join([self.number,self.year])+'.html')
        self.sigareas_html = os.path.join(self.processo_path, interf_html)
        self.clayers = []
        
    def getPrioridade(self):
        """get best prioridade data available"""
        dados = ProcessManager[self.name].dados
        return dados['prioridadec'] if 'prioridadec' in dados else dados['prioridade']
    
    @staticmethod
    def make(wpage, processostr, verbose=False, overwrite=False):
        """
        make folders and spreadsheets for specified process
        to aid on priority analysis

        * processostr : str
            numero processo format xxx.xxx/ano
        * wpage : wPage html 
            webpage scraping class com login e passwd preenchidos
        * overwrite: bool
            default to allways use using files saved on folder  
            instead of downloading again

        * returns: instance `Interferencia`

        * exceptions: 
            `DownloadInterferenciaFailed`, `CancelaUltimoEstudoFailed`
        """
        if overwrite and processostr in ProcessManager: # delete from database in case of overwrite            
            del ProcessManager[processostr]
        estudo = Interferencia(wpage, processostr, verbose=verbose)
        estudo._processo.salvaPageScmHtml(estudo.processo_path, 'basic', overwrite)
        estudo._processo.salvaPageScmHtml(estudo.processo_path, 'polygon', overwrite)                    
        estudo.fetchnsaveHTML(overwrite)
        estudo.getcLayers()
        # only if retirada interferencia html is saved we can create spreadsheets        
        if estudo.createTable(): # sometimes there is no interferences 
            estudo.createTableMaster()                                
            estudo.to_excel() # keeping for debugging                  
        estudo.to_database() # save to database marking no table
        # if there was an exception cancela ultimo estudo
        if not estudo.cancel_ultimo:
            estudo.cancelLast()                
        return estudo
    
    def cancelLast(self):
        """
        Cancela ultimo estudo em aberto. ('opção', 'interferencia' etc..)
        """
        return cancelaUltimo(self.wpage, self.number, self.year)        

    def createTable(self):
        """Parse the .html previous downloaded containing interferentes data. 
        
        Create `self.tabela_interf` and `self.tabela_assoc`.

        Raises:
            ConnectionError: 'Did not fetch the table'

        Returns:
            bool: True if there are interferentes
        """        

        with open(self.sigareas_html, "r", encoding="utf-8") as f:
            htmltxt = f.read()
        soup = BeautifulSoup(htmltxt, features="lxml")
        interf_table = soup.find("table", {"id" : "ctl00_cphConteudo_gvLowerRight"})
        if interf_table is None: # possible! no interferencia at all
            ## empty data frame, not yet possible 
            # self.tabela_interf = pd.DataFrame(columns=['Incluir', 'Processo', 'Evento', 'Descrição', 'Data'])
            return False # nenhuma interferencia SHOW!!
        rows = htmlscrap.tableDataText(interf_table)
        self.tabela_interf = pd.DataFrame(rows[1:], columns=rows[0])
        # columns to fill in 
        self.tabela_interf['Dads'] = 0
        self.tabela_interf['Sons'] = 0
        self.tabela_interf['Ativo'] = True
        self.tabela_interf.loc[:,'Processo'] = self.tabela_interf.Processo.apply(lambda x: pud(x).std)
        # tabela c/ processos associadoas aos processos interferentes
        self.tabela_assoc = pd.DataFrame()
        for name in list(set(self.tabela_interf.Processo)): # Unique Process Only
            if self.verbose:
                print(f"createTable: fetching data for associado {name} ", file=sys.stderr)   
            try:                              
                ProcessManager.GetorCreate(name, 
                                self.wpage, SCM_SEARCH.ALL, self.verbose) # needs polygon, associados = ALL
                pdados = ProcessManager[name].dados
            except PoligonalErrorSCM: # might not have poligonal due some other reason
                continue
            except Exception as e:
                raise Exception(f"{traceback.format_exc()}\n\nInterferencia.createTable error at {name}: {e}")
            indexes = (self.tabela_interf.Processo == name)
            self.tabela_interf.loc[indexes, 'Ativo'] = True if 'S' in pdados['ativo'] else False # Sim/Nao to True/False
            if pdados['associados']['dict']:
                self.tabela_interf.loc[indexes, 'Sons'] = len(pdados['sons'])
                self.tabela_interf.loc[indexes, 'Dads'] = len(pdados['parents'])
                assoc_items = pd.DataFrame({ "Main" : name, "Target" : pdados['associados']['dict'].keys() })
                assoc_items = assoc_items.join(pd.DataFrame(pdados['associados']['dict'].values()))                
                # not using prioridade of associados
                # assoc_items['Prior'] = self.getPrioridade()
                # number of direct sons/ ancestors
                self.tabela_assoc = pd.concat([self.tabela_assoc, assoc_items], sort=False, ignore_index=True, axis=0, join='outer')                
        return True



    def createTableMaster(self):
        """
        Create `tabela_interf_eventos` from `self.tabela_interf` previouly parsed,        
        Uses 'tabela de eventos' of processes 'interferentes'. 
        
        return False if no 'interferencia'          
        """
        if self.tabela_interf is None:            
            return False

        self.tabela_interf_master = pd.DataFrame()
        for _,row in self.tabela_interf.iterrows(): # for each possible prioritário
            # table from eventos simples is more complete ['Processo', 'Evento', 'Descrição', 'Data']
            # and also contains Data with time precison we will use it 
            events = getEventosSimples(self.wpage, row['Processo']) 
            # strdate to datetime use bellow for comparison
            events['Data'] = events.Data.apply(
                lambda strdate: datetime.strptime(strdate, "%d/%m/%Y %H:%M:%S"))     
            # we will add ['Observação','Publicação D.O.U'] from SCM Basicos    
            pdados = ProcessManager[row['Processo']].dados
            eventos_scm = pdados['eventos']
            eventos_scm = pd.DataFrame(eventos_scm[1:], columns=eventos_scm[0])
            events['Obs'] = eventos_scm['Observação']
            events['DOU'] = eventos_scm['Publicação D.O.U']
            # index number for each event
            events['EvSeq'] = len(events)-events.index.values.astype(int) # set correct order of events
            # cast to int Event number will be used to join eventos que inativam bellow
            events['Evento'] = events['Evento'].astype(int)
            # put count of associados father and sons
            events['Dads'] = row['Dads']
            events['Sons'] = row['Sons']
            events['Ativo'] = row['Ativo']
            events['Processo'] = events.Processo.apply(lambda x: pud(x).std) # standard names
            ##### Add an additional event row if necessary: #######
            # caso a primeira data dos eventos diferente da prioritária correta
            prioridade = pdados['prioridadec'] if 'prioridadec' in pdados else pdados['prioridade']             
            if events['Data'].values[-1] > np.datetime64(prioridade):                
                events = pd.concat([events, events.tail(1)], ignore_index=True, axis=0, join='outer')
                events.loc[events.index[-1], 'Data'] = np.datetime64(prioridade)
                events.loc[events.index[-1], 'EvSeq'] = -3 # represents added by here            
            # check if it's possível opção pending
            events['Popc'] = False
            if(events['Ativo'].any() and # ativo
                'polygon' in pdados and
                len(pdados['polygon']) > 1 and   # mais de 1 área
                'requerimento' in pdados['fase'].lower() and # fase de requerimento                
                events['Descrição'].apply(lambda ev: 'EXIGÊNCIA' in ev).any()):  # exigência
                events['Popc'] = True # Possível opção pendente - mark todas as rows de eventos

            # TODO SICOP: parte if fisico main available might have more or less lines than SCM eventos
            # use only what we have rest will be empty
            # events['SICOP FISICO PRINCIPAL MOVIMENTACAO']
            # DATA:HORA	SITUAÇÃO	UF	ÓRGÃO	PRIORIDADE	MOVIMENTADO	RECEBIDO	DATA REC.	REC. POR	GUIA

            ##### Append the group of rows of events for this process
            self.tabela_interf_master = pd.concat([self.tabela_interf_master, events], axis=0, join='outer')

        self.tabela_interf_master.reset_index(inplace=True,drop=True)
        # rearrange collumns in more meaningfully viewing
        columns_order = ['Ativo','Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 
        'Obs', 'DOU', 'Dads', 'Sons', 'Popc']
        self.tabela_interf_master = self.tabela_interf_master[columns_order]
        ### Cria coluna 'EvPrior'
        # onde eventos anteriores a data de prioridade são marcados 1 or 0 otherwise
        self.tabela_interf_master['EvPrior'] = 0 # 1 prioritario 0 otherwise        
        data_prioridade = self.getPrioridade()           
        # Verifica se a data de evento é anterior a data de prioridade
        # exceção: licenciamento tem prioridade retroagida pela licença
        # emitida pela prefeitura em até 90 dias       
        for _,row in self.tabela_interf_master.iterrows():
            EventData = row['Data']
            if ('licen' in ProcessManager[row['Processo']]['tipo'].lower() 
                and (row['EvSeq'] == -3 or row['EvSeq'] == 1) ): # only on 1st event
                EventData = np.datetime64(EventData) - np.timedelta64(90,'D')
            if EventData < data_prioridade:
                self.tabela_interf_master.loc[row.name,'EvPrior'] = 1
        ### Join-in column with inativam or ativam processo for each event excel 'eventos_scm_XXXXXXX.xls'
        eventos_xls = pd.read_excel(config['eventos_scm'], dtype={'Evento' : int, 'Inativ' : int})
        eventos_xls.drop(columns=['nome'],inplace=True)        
        # join Inativ column -1/1 inativam or ativam processo
        self.tabela_interf_master = self.tabela_interf_master.join(eventos_xls.set_index('Evento'), on='Evento')
        self.tabela_interf_master.Inativ = self.tabela_interf_master.Inativ.fillna(0) # not an important event
        #### Add a 'Prior' (Prioridade) Collumn At the Beggining
        self.tabela_interf_master['Prior'] = 1
        # Prioridade considerando quando houve evento de inativação se antes do atual não é prioritário
        for process, events in self.tabela_interf_master.groupby('Processo', sort=False):
            # (1) prioritário (-1) não prioritário (0) não se sabe
            # assume prioritário (1) ou não pela data do primeiro evento         
            prioritario = 1 if events.iloc[-1]['EvPrior'] > 0 else 0
            alive = np.sum(events.Inativ.values) # alive or dead
            if alive < 0: # DEAD - get by data da última inativação
                data_inativ = events.loc[events.Inativ == -1]['Data'].values[0]
                if data_inativ  <= np.datetime64(data_prioridade):
                    # morreu antes do atual, não é prioritário
                    prioritario = -1
            self.tabela_interf_master.loc[
                self.tabela_interf_master.Processo == process, 'Prior'] = prioritario

        # re-rearrange columns
        cols_order = ['Prior', 'Ativo', 'Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 
        'EvPrior', 'Inativ', 'Obs', 'DOU', 'Dads', 'Sons', 'Popc']
        self.tabela_interf_master = self.tabela_interf_master[cols_order] 

        return True    


    def getcLayers(self):
        """from page get checked layers (camadas) by checkboxes"""  
        with open(self.sigareas_html) as f:
            soup = BeautifulSoup(f, features="html.parser")              
        trs = soup.select("div[id*='tvn'] tr") 
        trs = list(filter(lambda x: True if x.select("input[checked]") else False, trs))
        trs = [ unidecode(list(tr.children)[7].text.strip()) for tr in trs ]        
        self.clayers = trs


    def to_database(self):
        """
        update database with ['estudo']['table'] 
        keep important old information (like 'done', 'pdf' etc.)
        if 'estudo' already on dados
        """
        dados = ProcessManager[self.name].dados        
        if 'estudo' in dados: # keep some old information
            estudo = dados['estudo']                        
            estudo.update({'clayers' : self.clayers}) 
        else:
            estudo = { 'done' : False, 'clayers' : self.clayers, 'type' : 'interferencia'}             
        estudo['time'] = datetime.now() # update time
        if self.tabela_interf_master is not None:            
            table = self.tabela_interf_master.copy()
            table = TableStr(table)      
            estudo['table'] = table.to_dict()                            
        ProcessManager[self.name].update({'estudo' : estudo})
  

    def to_excel(self):
        """pretty print to excel file tabela interferencia master"""
        if self.tabela_interf_master is None:
            return False
        table = self.tabela_interf_master.copy()

        excelfile = os.path.join(self.processo_path, config['interferencia']['file_prefix'] + '_' +
                '_'.join([self.number,self.year])+'.xlsx')        
        # Get max string size each collum for setting excel width column
        txt_table = table.values.astype(str).T
        minsize = np.apply_along_axis(lambda array: np.max([ len(string) for string in array ] ),
                            arr=txt_table, axis=-1) # maximum string size in each column
        headers = np.array([ len(string) for string in table.columns ]) # maximum string size each header
        colwidths = np.maximum(minsize, headers) + 5 # 5 characters of space more
        # Observação / DOU set size to header size - due a lot of text
        colwidths[-5] = headers[-5] + 10 # Observação
        colwidths[-6] = headers[-6] + 10 # DOU
        # number of rows
        nrows = len(table)
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(excelfile, engine='xlsxwriter')
        # Convert the dataframe to an XlsxWriter Excel object.
        table.to_excel(writer, sheet_name='Sheet1', index=False)
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
        for process, events in table.groupby('Processo', sort=False):
            # prioritário ou não pela coluna 'Prior' primeiro value
            prior = float(events['Prior'].values[0]) >= 0 # prioritário ou unknown
            dead = events['Ativo'].values[0]
            dead_nprior = dead and (not prior) # only fade/dim/paint dead and not prior
            for idx, row in events.iterrows(): # processo row by row set format
                #excel row index is not zero based, that's why idx+1 bellow
                if float(row['Inativ']) > 0 or float(row['Inativ']) < 0: # revival event / die event
                    # make text bold
                    worksheet.set_row(idx+1, None, row_fmt(i, dead_nprior, True))
                else: # 0
                    worksheet.set_row(idx+1, None, row_fmt(i, dead_nprior, False))
            i += 1
        # Set column width
        for i in range(len(colwidths)):
            # set_column(first_col, last_col, width, cell_format, options)
            worksheet.set_column(i, i, colwidths[i])                            
        # processos associados
        if self.tabela_assoc.size > 0:
            self.tabela_assoc.to_excel(writer, sheet_name='Sheet2', index=False)        
        # close the pandas excel writer and output the Excel file.
        writer.close()
      
          
    @staticmethod
    def from_html(wpage, dir='.', overwrite=False):
        name = pud.getAll(pathlib.Path(dir).absolute().stem)[0]
        if overwrite and processostr in ProcessManager: # delete from database in case of overwrite            
            del ProcessManager[processostr]
            estudo = Interferencia(wpage, name, verbose=False, getprocesso=True)        
        else:
            processo = ProcessManager[name]
            estudo = Interferencia(wpage, name, verbose=False, getprocesso=False)   
            estudo._processo = processo    
        estudo._processo.salvaPageScmHtml(estudo.processo_path, 'basic', overwrite)
        estudo._processo.salvaPageScmHtml(estudo.processo_path, 'polygon', overwrite)                    
        estudo.fetchnsaveHTML(overwrite)
        # only if retirada interferencia html is saved we can create spreadsheets        
        if estudo.createTable(): # sometimes there is no interferences 
            estudo.createTableMaster()                                
            estudo.to_excel() # keeping for debugging                  
        estudo.to_database() # save to database marking no table
        return estudo   


    @staticmethod
    def from_excel(dir='.'):            
        name = pud.getAll(pathlib.Path(dir).absolute().stem)[0]
        processo = ProcessManager[name]
        estudo = Interferencia(None, processo.name, verbose=False, getprocesso=False)     
        estudo._processo = processo         
        file_path = list(pathlib.Path(dir).glob(config['interferencia']['file_prefix']+'*.xlsx'))
        if not file_path: 
            raise RuntimeError("Legacy Excel prioridade not found, something like eventos_prioridade_*.xlsx")
        estudo.tabela_interf_master = pd.read_excel(file_path[0])          
        return estudo        
    
    def fetchnsaveHTML(self, overwrite=False):
        """fetch and save html interferencia raises DownloadInterferenciaFailed on fail"""
        html_file = (config['interferencia']['html_prefix']['this']+'_'+
            '_'.join([self.number, self.year]))  
        html_file = pathlib.Path(self.processo_path) / html_file        
        if not overwrite and html_file.with_suffix('.html').exists():
            self.cancel_ultimo = True # did not download - did not need to cancel
            return        
        fetch_save_Html(self.wpage, self.number, self.year, html_file.absolute())
        self.cancel_ultimo = cancelaUltimo(self.wpage, self.number, self.year) # clean up for next usage
      
            

# something else not sure will be usefull someday
# def salvaEstudoOpcaoDeAreaHtml(self, html_path):
#     self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=8')
#     formcontrols = {
#         'ctl00$cphConteudo$txtNumProc': self.number,
#         'ctl00$cphConteudo$txtAnoProc': self.year,
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
#     fname = 'sigareas_opcao_'+self.number+'_'+self.year
#     self.wpage.save(os.path.join(html_path, fname))
#     return True