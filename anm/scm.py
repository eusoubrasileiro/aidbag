import sys
from bs4 import BeautifulSoup

sys.path.append("..") # Adds higher directory to python modules path.
from web import htmlscrap as hscrap
from datetime import datetime
import re

from threading import Thread, Lock

mutex = Lock()

# "scm consulta dados (post) nao aceita formato diferente de 'xxx.xxx/xxxx'"
regxdp = re.compile("\d+")
def fmtPname(pross_str):
    """format process name to xxx.xxx/yyyy
    - input process might be also like this 2735/1935
    prepend zeros in this case to form 002.735/1935"""
    pross_str = ''.join(re.findall(regxdp, pross_str))
    ncharsmissing = 10-len(pross_str)
    pross_str = '0'*ncharsmissing+pross_str # prepend with zeros
    return pross_str[:3]+'.'+pross_str[3:6]+r'/'+pross_str[6:]

def numberyearPname(pross_str):
    "return process (number, year)"
    pross_str = fmtPname(pross_str) # to make sure
    pross_str = ''.join(re.findall(regxdp, pross_str))
    return pross_str[:6], pross_str[6:]

class Processo:
    # static field
    scm_data_tags = { # "data name" ; soup.find fields( "tag", "attributes")
        'prioridade'            : ['span',  { 'id' : "ctl00_conteudo_lblDataPrioridade"} ], # pode estar errada
        'area'                  : ['span',  { 'id' : 'ctl00_conteudo_lblArea'} ],
        'UF'                    : ['span',  { 'id' : 'ctl00_conteudo_lblUF'} ],
        'data_protocolo'        : ['span',  { 'id' : 'ctl00_conteudo_lblDataProtocolo'} ], # pode estar vazia
        'associados'            : ['table', { 'id' : 'ctl00_conteudo_gridProcessosAssociados'} ],
        'substancias'           : ['table', { 'id' : 'ctl00_conteudo_gridSubstancias'} ],
        'eventos'               : ['table', { 'id' : 'ctl00_conteudo_gridEventos'} ],
        'municipios'            : ['table', { 'id' : 'ctl00_conteudo_gridMunicipios'} ],
        'ativo'                 : ['span',  { 'id' : 'ctl00_conteudo_lblAtivo'} ]
    }
    def __new__(cls, processostr, wpage, dadosbasicos=True, fathernsons=True, ancestry=True, verbose=True):
        processostr = fmtPname(processostr)
        if processostr in ProcessStorage:
            if verbose:
                with mutex:
                    print("Processo __new___ getting from storage ", processostr, file=sys.stderr)
            processo = ProcessStorage[processostr]
            if dadosbasicos and not processo.dadosbasicos_run:
                processo.dadosBasicosGet()
            if fathernsons and not processo.fathernsons_run:
                processo.fathernSons()
            if ancestry and not processo.ancestry_run:
                processo.ancestrySearch()
            return processo
        else:
             # No instance existed, so create new object
            self = super().__new__(cls)  # Calls parent __new__ to make empty object
            self.processostr = processostr
            self.processo_number, self.processo_year = numberyearPname(processostr)
            self.wpage = wpage
            self.verbose = verbose
            # control to avoid running again
            self.ancestry_run = False
            self.dadosbasicos_run = False
            self.fathernsons_run = False
            if verbose:
                with mutex:
                    print("Processo __new___ placing on storage ", processostr, file=sys.stderr)
            ProcessStorage[self.processostr] = self   # store this new guy
            if dadosbasicos:
                self.dadosBasicosGet()
            if fathernsons:
                self.fathernSons()
            if ancestry:
                self.ancestrySearch()
            return self
    #def __init__(self, processostr, wpage, scmdata=True, upsearch=True, verbose=True):

    @classmethod # not same as @staticmethod (has a self)
    def fromNumberYear(self, processo_number, processo_year, wpage):
        processostr = processo_number + r'/' + processo_year
        return self(processostr, wpage)

    @staticmethod
    def specifyData(data=['prioridade', 'UF']):
        """return scm_data_tags from specified data labels"""
        return dict(zip(data, [ Processo.scm_data_tags[key] for key in data ]))

    def dadosBasicosRetrieve(self):
        """   Get & Post na página dados do Processo do Cadastro  Mineiro (SCM)
        """
        if hasattr(self, 'scm_dadosbasicosmain_response'): # already downloaded
            self.wpage.response = self.scm_dadosbasicosmain_response
            return True
        self.wpage.get('https://sistemas.dnpm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx')
        formcontrols = {
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
            'ctl00$conteudo$txtNumeroProcesso': self.processostr,
            'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
            '__VIEWSTATEENCRYPTED': ''}
        formdata = hscrap.formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('https://sistemas.dnpm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx',
                      data=formdata)
        # check for failure if cannot find Campo Ativo
        if self.wpage.response.text.find('ctl00_conteudo_lblAtivo') == -1:
            return False
        # may give False
        self.scm_dadosbasicosmain_response = self.wpage.response
        return True

    def dadosPoligonalRetrieve(self):
        formcontrols = {
            'ctl00$conteudo$btnPoligonal': 'Poligonal',
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
        formdata = hscrap.formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('https://sistemas.dnpm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx',
                      data=formdata)
        return self.wpage


    def fathernSons(self, ass_ignore=''):
        """
        * ass_ignore - to ignore in associados list (remove)

        'associados' must be in self.dados dict to build anscestors and sons
        - build self.anscestors lists ( father only)
        - build direct sons (self.dsons) list
        """
        if not (("associados" in self.dados)):  # key must exist
            raise Exception("key <associados> must exist on self.dados")
       # process 'processos associados' to get father, grandfather etc.
        self.anscestors = []
        self.dsons = []
        self.assprocesses = {}
        self.associados = False
        self.fathernsons_run = True
        if (not (self.dados['associados'][0][0] == 'Nenhum processo associado.')):
            self.associados = True
            # 'processo original' vs 'processo'  (many many times) wrong
            # sons / father association are many times wrong
            # father as son and vice-versa
            # get all processes listed on processos associados
            # dados['associados'][0][:] header line
            # dados['associados'][1][5] # coluna 5 'processo original'
            # dados['associados'][1][0] # coluna 0 'processo'
            nrows = len(self.dados['associados'])
            assprocesses_str = ([self.dados['associados'][i][0] for i in range(1, nrows) ] +
                             [ self.dados['associados'][i][5] for i in range(1, nrows) ])
            assprocesses_str = list(set(assprocesses_str)) # Unique Process Only
            assprocesses_str = list(map(fmtPname, assprocesses_str)) # formatted process names
            assprocesses_str.remove(self.processostr)# remove SELF from list
            ass_ignore = fmtPname(ass_ignore)
            if ass_ignore in assprocesses_str:  # ignore this process (son)
                assprocesses_str.remove(ass_ignore) # removing circular reference
            # get 'data_protocolo' of every_body
            for aprocess in assprocesses_str:
                processo = Processo(aprocess, self.wpage,  True, False, False,
                                        verbose=self.verbose)
                self.assprocesses[aprocess] = processo
            # from here we get dsons
            for kname, vprocess in self.assprocesses.items():
                if vprocess.data_protocolo >= self.prioridade:
                    self.dsons.append(kname)
                else: # and anscestors if any
                    self.anscestors.append(kname)
            # go up on ascestors until no other parent
            if len(self.anscestors) > 1:
                raise Exception("fathernSons - failed More than one parent: ", self.processostr)
        # nenhum associado
        return self.associados

    def ancestrySearch(self):
        """
        upsearch for ancestry of this process
        - create the 'correct' prioridade (self.prioridadec)
        - complete the self.anscestors lists ( ..., grandfather, great-grandfather etc.) from
        closer to farther
        """
        self.ancestry_run = True
        self.prioridadec = self.prioridade
        if self.associados and len(self.anscestors) > 0:
            # first father already has an process class object (get it)
            self.anscestorsprocesses = [] # storing the ancestors processes objects
            parent = self.assprocesses[self.anscestors[0]] # first father
            son_name = self.processostr # self is the son
            if self.verbose:
                with mutex:
                    print("ancestrySearch - going up: ", parent.processostr, file=sys.stderr)
            # find corrected data prioridade by ancestry
            while True: # how long will this take?
                parent.fathernSons(ass_ignore=son_name)
                # remove circular reference to son
                self.anscestorsprocesses.append(parent)
                if len(parent.anscestors) > 1:
                    raise Exception("ancestrySearch - failed More than one parent: ", parent.processostr)
                if len(parent.anscestors) == 0:
                    break
                self.anscestors.append(parent.anscestors[0])
                son_name = parent.processostr
                parent = Processo(parent.anscestors[0], self.wpage,
                        True, False, False, self.verbose)
                self.prioridadec = parent.prioridade

    def toDates(self):
        """prioridade pode estar errada, por exemplo, quando uma cessão gera processos 300
        a prioridade desses 300 acaba errada ao esquecer do avô"""
        self.prioridade = datetime.strptime(self.dados['prioridade'], "%d/%m/%Y %H:%M:%S")
        self.data_protocolo = datetime.strptime(self.dados['data_protocolo'], "%d/%m/%Y %H:%M:%S")
        return self.prioridade

    def dadosBasicosGet(self, data_tags=None, redo=False):
        """check your nltm authenticated session
        if getting empty dict dados"""
        self.dadosbasicos_run = True
        if data_tags is None: # data tags to fill in 'dados' with
            data_tags = self.scm_data_tags
        if not hasattr(self, 'dados') or redo == True:
            self.dadosBasicosRetrieve()
            self.dados = {}
        else:
            return len(self.dados) == len(data_tags)
        soup = BeautifulSoup(self.wpage.response.text, features="lxml")
        if self.verbose:
            with mutex:
                print("dadosBasicosGet - parsing: ", self.processostr, file=sys.stderr)
        for data in data_tags:
            result = soup.find(data_tags[data][0],
                                    data_tags[data][1])
            if not (result is None):
                if data_tags[data][0] == 'table': # parse table if table
                    result = hscrap.tableDataText(result)
                else:
                    result = result.text
                self.dados.update({data : result})
        if self.dados['data_protocolo'] == '': # might happen
            self.dados['data_protocolo'] = self.dados['prioridade']
            if self.verbose:
                print('dadosBasicosGet - missing <data_protocolo>: ', self.processostr, file=sys.stderr)
        self.toDates()
        return len(self.dados) == len(data_tags) # return if got w. asked for

    def dadosBasicosGetMissing(self):
        """obtém dados faltantes (se houver) pelo processo associado (pai):
           - UF
           - substancias
        """
        if not hasattr(self, 'dados'):
            self.dadosBasicosGet()
        # cant get missing without parent
        if self.dados['processos_associados'][0][0] == "Nenhum processo associado.":
            return False
        missing = []
        if self.dados['UF'] == "":
            missing.append('UF')
        if self.dados['substancias'][0][0] == 'Nenhuma substância.':
            missing.append('substancias')
        if self.dados['municipios'][0][0] == 'Nenhum município.':
            missing.append('municipios')
        miss_data_tags = Processo.specifyData(missing)
        # processo father
        fathername = self.dados['processos_associados'][1][5]
        if fmtPname(fathername) == fmtPname(self.processostr): # doesn't have father
            return False
        father = Processo(fathername, self.wpage)
        father.dadosBasicosGet(miss_data_tags)
        self.dados.update(father.dados)
        del father
        return self.dados


############################################################
# Container of processes to avoid :
# 1. conneting/open page of scm again
# 2. parsing all information again
# If it was already parsed save it in here
ProcessStorage = {}
# key - fmtPname pross_str - value Processo object
