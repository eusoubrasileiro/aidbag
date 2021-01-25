import sys, os
import glob
from bs4 import BeautifulSoup

sys.path.append("..") # Adds higher directory to python modules path.
from web import htmlscrap
from datetime import datetime
import re

from multiprocessing.dummy import Pool as ThreadPool
import itertools
import threading
from threading import Thread, Lock

mutex = Lock()

scm_timeout=(2*60)

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

# static field
scm_data_tags = { # "data name" ; soup.find fields( "tag", "attributes")
    'prioridade'            : ['span',  { 'id' : "ctl00_conteudo_lblDataPrioridade"} ], # pode estar errada
    'area'                  : ['span',  { 'id' : 'ctl00_conteudo_lblArea'} ],
    'UF'                    : ['span',  { 'id' : 'ctl00_conteudo_lblUF'} ],
    'NUP'                   : ['span',  { 'id' : 'ctl00_conteudo_lblNup'} ],
    'tipo'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoRequerimento'} ],
    'fase'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoFase'} ],
    'data_protocolo'        : ['span',  { 'id' : 'ctl00_conteudo_lblDataProtocolo'} ], # pode estar vazia
    'associados'            : ['table', { 'id' : 'ctl00_conteudo_gridProcessosAssociados'} ],
    'substancias'           : ['table', { 'id' : 'ctl00_conteudo_gridSubstancias'} ],
    'eventos'               : ['table', { 'id' : 'ctl00_conteudo_gridEventos'} ],
    'municipios'            : ['table', { 'id' : 'ctl00_conteudo_gridMunicipios'} ],
    'ativo'                 : ['span',  { 'id' : 'ctl00_conteudo_lblAtivo'} ]
}

"""
Use `Processo.Get` to avoid creating duplicate Processo's
"""
class Processo:
    def __init__(self, processostr, wpagentlm, verbose=True):
        """
        Hint: Use `Processo.Get` to avoid creating duplicate Processo's

        dados :
                1 - scm dados basicos page
                2 - anterior + processos associados (father and direct sons)
                3 - anterior + correção prioridade ancestor list
        """
        processostr = fmtPname(processostr)
        self.processostr = processostr
        self.number, self.year = numberyearPname(processostr)
        self.wpage = htmlscrap.wPageNtlm(wpagentlm.user, wpagentlm.passwd)
        self.verbose = verbose
        # control to avoid running again
        self.ancestry_run = False
        self.dadosbasicos_run = False
        self.fathernsons_run = False
        self.isfree = threading.Event()
        self.isfree.set() # make it free right now so it can execute

    def runtask(self, task=None, cdados=0):
        """
        codedados :
                1 - scm dados basicos page
                2 - anterior + processos associados (father and direct sons)
                3 - anterior + correção prioridade (ancestors list)
        """
        # check if some taks is running
        # only ONE can have this process at time
        if not self.isfree.wait(60.*2):
            raise Exception("runtask - wait time-out for process: ", self.processostr)
        self.isfree.clear() # make it busy
        if cdados: # passed argument to perform a default calls without args
            if (cdados == 1) and not self.dadosbasicos_run:
                task = (self.dadosBasicosGet, {})
            elif (cdados == 2) and not self.fathernsons_run:
                task = (self.fathernSons, {})
            elif (cdados == 3) and not self.ancestry_run:
                task = (self.ancestrySearch, {})
        if task:
            task, params = task
            if self.verbose:
                with mutex:
                    print('task to run: ', task.__name__, ' params: ', params,
                    ' - process: ', self.processostr, file=sys.stderr)
            task(**params)
        self.isfree.set() # make it free

    @classmethod # not same as @staticmethod (has a self)
    def fromNumberYear(self, processo_number, processo_year, wpage):
        processostr = processo_number + r'/' + processo_year
        return self(processostr, wpage)

    @staticmethod
    def specifyData(data=['prioridade', 'UF']):
        """return scm_data_tags from specified data labels"""
        return dict(zip(data, [ scm_data_tags[key] for key in data ]))

    def _dadosBasicosRetrieve(self):
        """   Get & Post na página dados do Processo do Cadastro  Mineiro (SCM)
        """
        if hasattr(self, 'scm_dadosbasicosmain_response'): # already downloaded
            self.wpage.response = self.scm_dadosbasicosmain_response
            return True
        self.wpage.get('https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx')
        formcontrols = {
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
            'ctl00$conteudo$txtNumeroProcesso': self.processostr,
            'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
            '__VIEWSTATEENCRYPTED': ''}
        formdata = htmlscrap.formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx',
                      data=formdata, timeout=scm_timeout)
        # check for failure if cannot find Campo Ativo
        if self.wpage.response.text.find('ctl00_conteudo_lblAtivo') == -1:
            raise Exception("Processo._dadosBasicosRetrieve - did not receive page")
        # may give False
        self.scm_dadosbasicosmain_response = self.wpage.response
        self.scm_dadosbasicosmain_html = self.wpage.response.text
        return True

    def salvaDadosBasicosHtml(self, html_path):
        self._dadosBasicosRetrieve() # self.wpage.response will be filled
        dadosbasicosfname = 'scm_basicos_'+self.number+self.year
        # sobrescreve
        self.wpage.save(os.path.join(html_path, dadosbasicosfname))

    def _dadosPoligonalRetrieve(self):
        if hasattr(self, 'scm_dadosbasicospoli_response'): # already downloaded
            self.wpage.response = self.scm_dadosbasicospoli_response
            return True
        formcontrols = {
            'ctl00$conteudo$btnPoligonal': 'Poligonal',
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
        formdata = htmlscrap.formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx',
                      data=formdata)
        self.scm_dadosbasicospoli_response = self.wpage.response
        self.scm_dadosbasicospoli_html = self.wpage.response.text
        return True

    def salvaDadosPoligonalHtml(self, html_path):
        self._dadosPoligonalRetrieve() # self.wpage.response will be filled
        # sobrescreve
        dadospolyfname = 'scm_poligonal_'+self.number+self.year
        self.wpage.save(os.path.join(html_path, dadospolyfname))

    def fathernSons(self, ass_ignore=''):
        """
        * ass_ignore - to ignore in associados list (remove)

        'associados' must be in self.dados dict to build anscestors and sons
        - build self.anscestors lists ( father only)
        - build direct sons (self.dsons) list
        """
        if not self.dadosbasicos_run:
            self.dadosBasicosGet()

       # process 'processos associados' to get father, grandfather etc.
        self.anscestors = []
        self.dsons = []
        self.assprocesses = {}
        self.associados = False

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
            self.assprocesses_str = ([self.dados['associados'][i][0] for i in range(1, nrows) ] +
                             [ self.dados['associados'][i][5] for i in range(1, nrows) ])
            self.assprocesses_str = list(set(self.assprocesses_str)) # Unique Process Only
            self.assprocesses_str = list(map(fmtPname, self.assprocesses_str)) # formatted process names
            self.assprocesses_str.remove(self.processostr)# remove SELF from list
            ass_ignore = fmtPname(ass_ignore)
            if ass_ignore in self.assprocesses_str:  # ignore this process (son)
                self.assprocesses_str.remove(ass_ignore) # removing circular reference
            if self.verbose:
                with mutex:
                    print("fathernSons - getting associados: ", self.processostr,
                    ' - ass_ignore: ', ass_ignore, file=sys.stderr)
            # for aprocess in self.assprocesses_str:
            #     processo = Processo(aprocess, self.wpage,  1, self.verbose)
            #     self.assprocesses[aprocess] = processo
            #create multiple python requests sessions
            # get 'data_protocolo' of every_body
            self.assprocesses = None
            # ignoring empty lists
            # only one son or father that is ignored
            if self.assprocesses_str:
                with ThreadPool(len(self.assprocesses_str)) as pool:
                    # Open the URLs in their own threads and return the results
                    # processo = Processo(aprocess, self.wpage, True, False, False, verbose=self.verbose)
                    self.assprocesses = pool.starmap(Processo.Get, zip(self.assprocesses_str,
                                                    itertools.repeat(self.wpage),
                                                    itertools.repeat(1),
                                                    itertools.repeat(self.verbose)))
                # create dict of key process name , value process objects
                self.assprocesses = dict(zip(list(map(lambda p: p.processostr, self.assprocesses)),
                                                self.assprocesses))
                if self.verbose:
                    with mutex:
                        print("fathernSons - finished associados: ", self.processostr, file=sys.stderr)
                #from here we get dsons
                for kname, vprocess in self.assprocesses.items():
                    if vprocess.data_protocolo >= self.prioridade:
                        self.dsons.append(kname)
                    else: # and anscestors if any
                        self.anscestors.append(kname)
                # go up on ascestors until no other parent
                if len(self.anscestors) > 1:
                    raise Exception("fathernSons - failed more than one parent: ", self.processostr)
        # nenhum associado
        self.fathernsons_run = True
        return self.associados

    def ancestrySearch(self):
        """
        upsearch for ancestry of this process
        - create the 'correct' prioridade (self.prioridadec)
        - complete the self.anscestors lists ( ..., grandfather, great-grandfather etc.) from
        closer to farther
        """
        if not self.fathernsons_run:
            self.fathernSons()

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
                # must run on same thread to block the sequence
                # of instructions just after this
                parent.runtask((parent.fathernSons,{'ass_ignore':son_name}))
                # remove circular reference to son
                self.anscestorsprocesses.append(parent)
                if len(parent.anscestors) > 1:
                    raise Exception("ancestrySearch - failed More than one parent: ", parent.processostr)
                if len(parent.anscestors) == 0:
                    break
                self.anscestors.append(parent.anscestors[0])
                son_name = parent.processostr
                parent = Processo.Get(parent.anscestors[0], self.wpage, 1, self.verbose)
                self.prioridadec = parent.prioridade
        self.ancestry_run = True

    def _toDates(self):
        """prioridade pode estar errada, por exemplo, quando uma cessão gera processos 300
        a prioridade desses 300 acaba errada ao esquecer do avô"""
        self.prioridade = datetime.strptime(self.dados['prioridade'], "%d/%m/%Y %H:%M:%S")
        self.data_protocolo = datetime.strptime(self.dados['data_protocolo'], "%d/%m/%Y %H:%M:%S")
        return self.prioridade

    def dadosBasicosGet(self, data_tags=None, redo=False, parse_only=False):
        """check your nltm authenticated session
        if getting empty dict dados"""
        if data_tags is None: # data tags to fill in 'dados' with
            data_tags = scm_data_tags.copy()
        if not parse_only:
            if not hasattr(self, 'dados') or redo == True:
                self._dadosBasicosRetrieve()
                self.dados = {}
            else:
                return len(self.dados) == len(data_tags)
        else: # dont need to retrieve anything
            self.dados = {}
        soup = BeautifulSoup(self.scm_dadosbasicosmain_html, features="lxml")
        if self.verbose:
            with mutex:
                print("dadosBasicosGet - parsing: ", self.processostr, file=sys.stderr)

        new_dados = htmlscrap.dictDataText(soup, data_tags)
        self.dados.update(new_dados)

        if self.dados['data_protocolo'] == '': # might happen
            self.dados['data_protocolo'] = self.dados['prioridade']
            if self.verbose:
                with mutex:
                    print('dadosBasicosGet - missing <data_protocolo>: ', self.processostr, file=sys.stderr)
        self._toDates()
        self.NUP = self.dados['NUP'] # numero unico processo SEI
        self.dadosbasicos_run = True
        return len(self.dados) == len(data_tags) # return if got w. asked for

    def _dadosBasicosGetMissing(self):
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
        father = Processo.Get(fathername, self.wpage)
        father.dadosBasicosGet(miss_data_tags)
        self.dados.update(father.dados)
        del father
        return self.dados

    def save(self):
        pass

    @staticmethod
    def fromHtml(path='.', processostr=None, verbose=True):
        curdir = os.getcwd()
        os.chdir(path)
        path_main_html = glob.glob('*basicos*.html')[0] # html file on folder
        if not processostr: # get process str name by file name
            processostr= fmtPname(glob.glob('*basicos*.html')[0])
        processo = Processo.Get(processostr, htmlscrap.wPageNtlm('', ''), None, verbose, run=False)
        main_html = None
        with open(path_main_html, 'r') as f: # read html scm
            main_html = f.read()
        processo.scm_dadosbasicosmain_html = main_html
        processo.dadosBasicosGet(parse_only=True)
        os.chdir(curdir) # go back
        return processo

    @staticmethod
    def Get(processostr, wpagentlm, dados=3, verbose=True, run=True):
        """
        Create a new or get a Processo from ProcessStorage

        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos

        dados :
                        1 - scm dados basicos page
                        2 - anterior + processos associados (father and direct sons)
                        3 - anterior + correção prioridade ancestor list
        """
        processo = None
        processostr = fmtPname(processostr)
        if processostr in ProcessStorage:
            if verbose: # only for pretty orinting
                with mutex:
                    print("Processo __new___ getting from storage ", processostr, file=sys.stderr)
            processo = ProcessStorage[processostr]
        else:
            if verbose: # only for pretty orinting
                with mutex:
                    print("Processo __new___ placing on storage ", processostr, file=sys.stderr)
        processo = Processo(processostr, wpagentlm,  verbose)
        ProcessStorage[processostr] = processo   # store this new guy
        if run: # wether run the task, sometimes loading from file no run
            processo.runtask(cdados=dados)
        return processo

############################################################
# Container of processes to avoid :
# 1. connecting/open page of SCM again
# 2. parsing all information again
# If it was already parsed save it in here
ProcessStorage = {}
# key - fmtPname pross_str - value Processo object
