import sys, copy
from datetime import datetime
from bs4 import BeautifulSoup
from ....web import htmlscrap
from .util import (
    comparePnames,
    fmtPname
)


# HTML tags for SCM main page
# static field
scm_data_tags = { # "data name" ; soup.find fields( "tag", "attributes")
    'prioridade'            : ['span',  { 'id' : "ctl00_conteudo_lblDataPrioridade"} ], # pode estar errada
    'data_protocolo'        : ['span',  { 'id' : 'ctl00_conteudo_lblDataProtocolo'} ], # pode estar vazia
    'area'                  : ['span',  { 'id' : 'ctl00_conteudo_lblArea'} ],
    'UF'                    : ['span',  { 'id' : 'ctl00_conteudo_lblUF'} ],
    'NUP'                   : ['span',  { 'id' : 'ctl00_conteudo_lblNup'} ],
    'tipo'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoRequerimento'} ],
    'fase'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoFase'} ],    
    'associados'            : ['table', { 'id' : 'ctl00_conteudo_gridProcessosAssociados'} ],
    'substancias'           : ['table', { 'id' : 'ctl00_conteudo_gridSubstancias'} ],
    'eventos'               : ['table', { 'id' : 'ctl00_conteudo_gridEventos'} ],
    'municipios'            : ['table', { 'id' : 'ctl00_conteudo_gridMunicipios'} ],
    'ativo'                 : ['span',  { 'id' : 'ctl00_conteudo_lblAtivo'} ]
}


def parseNUP(dbasicos_page):
    soup = BeautifulSoup(dbasicos_page, features="lxml")
    return soup.select_one('[id=ctl00_conteudo_lblNup]').text   


def parseDadosBasicos(dbasicos_page, name, verbose, mutex, data_tags=scm_data_tags):    
    soup = BeautifulSoup(dbasicos_page, features="lxml")
    dados = htmlscrap.dictDataText(soup, data_tags)
    if dados['data_protocolo'] == '': # might happen
        dados['data_protocolo'] = dados['prioridade']
        if verbose:
            with mutex:
                print('parseDadosBasicos - missing <data_protocolo>: ', file=sys.stderr)
    # prioridade pode estar errada, por exemplo, quando uma cessão gera processos 300
    # a prioridade desses 300 acaba errada ao esquecer do avô
    # protocolo pode estar errado ou ausente também
    dados['prioridade'] = datetime.strptime(dados['prioridade'], "%d/%m/%Y %H:%M:%S")
    dados['prioridadec'] = dados['prioridade'] # just for start
    dados['data_protocolo'] = datetime.strptime(dados['data_protocolo'], "%d/%m/%Y %H:%M:%S")    
    # associados
    if dados['associados'][0][0] == "Nenhum processo associado.":
        dados['associados'] = {} # overwrite by an empty dictionary 
    else:
        table_associados = copy.copy(dados['associados']) # copy because it will be overwritten
        nrows = len(table_associados)   
        # 'processo original' & 'processo'  (many times wrong)
        # get all processes listed on processos associados
        # table_associados[0][:] header line
        # table_associados[1][5] # coluna 5 'processo original'
        # table_associados[1][0] # coluna 0 'processo'            
        associados = ([table_associados[i][0] for i in range(1, nrows) ] +
                            [table_associados[i][5] for i in range(1, nrows) ])            
        associados = list(dict.fromkeys(associados)) # unique process mantaining order py3.7+
        associados = list(map(fmtPname, associados)) # formatted process names
        associados.remove(name) # remove SELF from list
        # create dictionary of associados with empty dict of properties
        # properties will be filled after
        # 'obj' property will be a class instance of scm.processo.Processo
        # dados['associados'] = { name : {} for name in associados } 
        # properties 'tipo' e 'data de associação'
        # ordem é mantida key : process name                  #   
        dados['associados'] = {  # overwrite by a dictionary of associados
                associados[i-1] : # process name is the key 
                    { # properties
                        'tipo'    : table_associados[i][2], 
                        'titular' : table_associados[i][1], 
                        'data'    : datetime.strptime(table_associados[i][3], "%d/%m/%Y"),
                        'obj'     : None,
                    }
                for i in range(1, nrows) 
            }
        # from here we get direct sons and parents/anscestors
        # from process names only
        # 800.xxx/2005 -> 300.yyy/2005
        dados['sons'] = []
        dados['parents'] = []
        for associado in dados['associados']:
            code = comparePnames(associado, name)
            if code == -1: # before
                dados['parents'].append(associado)
            elif code == 1: # after
                dados['sons'].append(associado)        
    return dados 

# fonte de informação da data de origem do processo 
# 1. numero do processo 
# 2. data de associacao 
# data de associacao não existe para self 
# but data protocolo pode ou não existir
# se prioridade existe pode não ser útil para associação
# não há opção tem que ser por nome mesmo

def parseDadosPoligonal(poligonpage):
    polydata = {}
    soup = BeautifulSoup(poligonpage, features="lxml")
    htmltables = soup.findAll('table', { 'class' : 'BordaTabela' }) #table[class="BordaTabela"]
    if htmltables: 
        memorial = htmlscrap.tableDataText(htmltables[-1])
        data = htmlscrap.tableDataText(htmltables[1])
        data = data[0:5] # informações memo descritivo
        polydata = {'area'     : float(data[0][1].replace(',', '.')), 
                    'datum'     : data[0][3],
                    'cmin'      : float(data[1][1]), 
                    'cmax'      : float(data[1][3]),
                    'amarr_lat' : data[2][1],
                    'amarr_lon' : data[2][3],
                    'amarr_cum' : data[3][3],
                    'amarr_ang' : data[4][1],
                    'amarr_rum' : data[4][3],
                    'memo'      : memorial
                    }
    return polydata

def getMissingTagsBasicos(dados):
    missing = []
    if dados['UF'] == "":
        missing.append('UF')
    if dados['substancias'][0][0] == 'Nenhuma substância.':
        missing.append('substancias')
    if dados['municipios'][0][0] == 'Nenhum município.':
        missing.append('municipios')
    miss_data_tags = { key : scm_data_tags[key] for key in missing }        
    return miss_data_tags

    # def isOlderAssociado(self, other):
    #     """simple check for associados 
    #     wether self 02/2005 is older than 03/2005"""
    #     # if starts with 3xx
    #     # if self.disp: # if disponibilidade get data associação mais antiga -> origen
    #     #     datas = [ d['data'] for d in self.AssociadosData.values() ]
    #     #     datas.sort(reverse=False)
    #     #     syear = datas[0].year
    #     # else:
    #     #     syear = self.year 
    #     # if other.disp: # if disponibilidade get data associação mais antiga -> origen
    #     #     datas = [ d['data'] for d in other.AssociadosData.values() ]
    #     #     datas.sort(reverse=False)
    #     #     oyear = datas[0].year 
    #     # else:
    #     #     oyear = other.year 
    #     if self.year < other.year:
    #         return True 
    #     if self.year > other.year:
    #         return False 
    #     # same year now       
    #     if self.number < other.number:
    #         return True 
    #     if self.number > other.number:
    #         return False 
    #     raise Exception("Error `IsOlder` process are equal")