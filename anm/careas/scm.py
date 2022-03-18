import sys, os
import glob, json
from bs4 import BeautifulSoup
from datetime import datetime
import concurrent.futures
import threading
from threading import Lock

from numpy import true_divide
from ...web import htmlscrap

from .scm_requests import (
    dadosBasicosPageRetrieve,
    dadosPoligonalPageRetrieve
)

from .scm_util import (
    fmtPname,
    numberyearPname,
    findfmtPnames,
    findPnames
)

from .constants import (
    scm_data_tags
)


mutex = Lock()
"""`threading.Lock` exists due ancestry search with multiple threads"""

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
        self.processostr = fmtPname(processostr) # `fmtPname` unique string process number/year
        self.name = self.processostr
        self.number, self.year = numberyearPname(self.processostr)
        self.wpage = htmlscrap.wPageNtlm(wpagentlm.user, wpagentlm.passwd)
        self.verbose = verbose
        # control to avoid running again
        self.ancestry_run = False
        self.dadosbasicos_run = False
        self.fathernsons_run = False
        self.isfree = threading.Event()
        self.isfree.set() # make it free right now so it can execute
        self.dados = {} 
        """dados to be parsed uses `htmlscrap.dictDataText` """
        self.polydata = {}
        """dados da poligonal to be parsed"""
        # and python.requests responses to be-reused and to save page content
        self.response_dbasicospage = None  
        """python.requests response for dbasicos page to be-reused and to save page content"""
        self.response_poligonpage = None  
        """python.requests responses for poligonal page to be-reused and to save page content"""
        self.html_dbasicospage = None     
        """html source of all data (aba dados basicos) to be parsed"""
        self.html_poligonpage = None         
        """html source of all data (aba poligonal) to be parsed"""
        # anscestors control  
        # process 'processos associados' to get father, grandfather etc.
        self.associados = False 
        """aba dados basicos tabela associados presente ou não """
        self.assprocesses = {}
        """aba dados basicos tabela associados processos dict {'processostr' : scm.Processo}
        dict of key process name : value process objects"""
        self.anscestorsprocesses = []
        self.anscestors = []
        self.dsons = [] # direct sons
        # prioridade
        self.prioridade = None
        self.prioridadec = None 
        """prioridade corrigida by ancestors"""    
        self.data_protocolo = None
        """data de protocolo"""
        self.NUP = ''
        """numero unico processo SEI"""
   

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
        if cdados: # passed argument to perform a default call without args
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

    #@classmethod # not same as @staticmethod (has a self)
    #can be created on other file where the class is no present by reference it 
    def fromNumberYear(self, processo_number, processo_year, wpage):
        processostr = processo_number + r'/' + processo_year
        return self(processostr, wpage)

    def isOlder(self, other):
        """simple check wether
        self 02/2005 is older than 03/2005"""
        if self.year < other.year:
            return True 
        if self.year > other.year:
            return False 
        # same year now 
        if self.number < other.number:
            return True 
        if self.number > other.number:
            return False 
        raise Exception("Error `IsOlder` process are equal")

    @staticmethod
    def specifyDataToParse(data=['prioridade', 'UF']):
        """return scm_data_tags from specified data labels"""
        return dict(zip(data, [ scm_data_tags[key] for key in data ]))    

    @staticmethod
    def getNUP(processostr, wpagentlm):
        response = dadosBasicosPageRetrieve(processostr, wpagentlm)
        soup = BeautifulSoup(response.text, features="lxml")
        return soup.select_one('[id=ctl00_conteudo_lblNup]').text

    def dadosBasicosPageRetrieve(self):
        if not self.html_dbasicospage:             
            self.response_dbasicospage = dadosBasicosPageRetrieve(self.processostr, self.wpage, False)
            self.html_dbasicospage = self.response_dbasicospage.content
        return self.response_dbasicospage

    def salvaDadosBasicosHtml(self, html_path):
        self.wpage.response = self.dadosBasicosPageRetrieve() # re-use request.response
        dadosbasicosfname = 'scm_basicos_'+self.number+'_'+self.year
        # re-use request.response overwrite html saved
        self.wpage.save(os.path.join(html_path, dadosbasicosfname))

    def dadosPoligonalPageRetrieve(self):
        if not self.html_poligonpage: 
            self.response_poligonpage = dadosPoligonalPageRetrieve(self.processostr, self.wpage, False)
            self.html_poligonpage = self.response_poligonpage.content
        return self.response_poligonpage

    def salvaDadosPoligonalHtml(self, html_path):
        self.wpage.response = self.dadosPoligonalPageRetrieve() # re-use request.response
        # sobrescreve
        dadospolyfname = 'scm_poligonal_'+self.number+'_'+self.year
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

        if self.fathernsons_run: # might need to run more than once?
            return self.associados

       
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
            assprocesses_name = ([self.dados['associados'][i][0] for i in range(1, nrows) ] +
                             [ self.dados['associados'][i][5] for i in range(1, nrows) ])
            assprocesses_name = list(set(assprocesses_name)) # Unique Process Only
            assprocesses_name = list(map(fmtPname, assprocesses_name)) # formatted process names
            assprocesses_name.remove(self.processostr)# remove SELF from list
            ass_ignore = fmtPname(ass_ignore) if ass_ignore != '' else ''

            if ass_ignore in assprocesses_name:  # ignore this process
                assprocesses_name.remove(ass_ignore) # removing circular reference
            if self.verbose:
                with mutex:
                    print("fathernSons - getting associados: ", self.processostr,
                    ' - ass_ignore: ', ass_ignore, file=sys.stderr)   
                    print("fathernSons - getting associados: ", self.processostr,
                    ' assprocesses_name: ', assprocesses_name, file=sys.stderr)            

            # helper function to search outword only
            def exploreAssociados(name, wp, ignore, verbosity):
                """ *ass_ignore : must be set to avoid being waiting for parent-source searcher
                    the search will spread outward only"""
                proc = Processo.Get(name, wp, 0, verbosity, False)
                proc.dadosBasicosGet()
                proc.fathernSons(ass_ignore=ignore)
                return proc

            # ignoring empty lists only one son or father that is ignored
            if assprocesses_name:
                with concurrent.futures.ThreadPoolExecutor() as executor: # thread number optimal       
                    # use a dict to map { process name : future_wrapped_Processo }             
                    # due possibility of exception on Thread and to know which process was responsible for that
                    #future_processes = {process_name : executor.submit(Processo.Get, process_name, self.wpage, 1, self.verbose) 
                    #    for process_name in assprocesses_name}
                    future_processes = {process_name : executor.submit(exploreAssociados, 
                        process_name, self.wpage, self.processostr, self.verbose) 
                        for process_name in assprocesses_name}
                    concurrent.futures.wait(future_processes.values())
                    #for future in concurrent.futures.as_completed(future_processes):         
                    for process_name, future_process in future_processes.items():               
                        try:
                            # create dict of key process name, value process objects
                            self.assprocesses.update({process_name : future_process.result()})
                        except Exception as exc:
                            print("Exception raised while running fathernSons thread for process {:0}".format(
                                process_name), file=sys.stderr)
                            raise(exc)
            # put back the 'ass_ignore', so the comparison bellow works
            if ass_ignore != '':
                self.assprocesses.update({ ass_ignore : ProcessStorage[ass_ignore]})  
            if self.verbose:
                with mutex:
                    print("fathernSons - self.assprocesses: ", self.assprocesses, file=sys.stderr)
            # from here we get dsons, first run 
            # TODO: run again once prioridade is fixed
            for name, process in self.assprocesses.items():
                if process.isOlder(self):
                    self.anscestors.append(name)                        
                else: # yonger
                    self.dsons.append(name)
            # go up on ascestors until no other parent?
            if len(self.anscestors) > 1:
                raise Exception("fathernSons - failed more than one parent: ", self.processostr)
            if self.verbose:
                with mutex:
                    print("fathernSons - finished associados: ", self.processostr, file=sys.stderr)
        # nenhum associado
        self.fathernsons_run = True
        return self.associados

    def ancestrySearch(self, ass_ignore=''):
        """
        upsearch for ancestry of this process
        - create the 'correct' prioridade (self.prioridadec)
        - complete the self.anscestors lists ( ..., grandfather, great-grandfather etc.) from
        closer to farther
        """
        if self.ancestry_run:
            return

        if self.verbose:
            with mutex:
                print("ancestrySearch - starting: ", self.processostr, file=sys.stderr)

        if not self.fathernsons_run:
            self.fathernSons(ass_ignore)

        self.prioridadec = self.prioridade
        if self.associados and len(self.anscestors) > 0:
            # first father already has an process class object (get it)
            self.anscestorsprocesses = [] # storing the ancestors processes objects
            parent = self.assprocesses[self.anscestors[0]] #first father get by process name string
            son_name = self.processostr # self is the son
            if self.verbose:
                with mutex:
                    print("ancestrySearch - going up: ", parent.processostr, file=sys.stderr)
            # find corrected data prioridade by ancestry
            while True: # how long will this take?
                # must run on same thread to block the sequence
                # of instructions just after this
                parent.runtask((parent.ancestrySearch,{'ass_ignore':son_name}))
                # remove circular reference to son
                self.anscestorsprocesses.append(parent)
                if len(parent.anscestors) > 1:
                    raise Exception("ancestrySearch - failed More than one parent: ", parent.processostr)
                else:
                    if len(parent.anscestors) == 0: # case only 1 parent, FINISHED
                        if parent.prioridadec < self.prioridadec:
                            self.prioridadec = parent.prioridadec
                        if self.verbose:
                            with mutex:
                                print("ancestrySearch - finished: ", self.processostr, file=sys.stderr)
                        break
                    else: # 1 anscestors, LOOP again
                        self.anscestors.append(parent.anscestors[0]) # store its name string
                        son_name = parent.processostr
                        parent = Processo.Get(parent.anscestors[0], self.wpage, 1, self.verbose)
                        # its '1' above because the loop will ask for 3 `ancestrySearch`
                        # do not correct prioridadec until end is reached
        self.ancestry_run = True

    def _toDates(self):
        """prioridade pode estar errada, por exemplo, quando uma cessão gera processos 300
        a prioridade desses 300 acaba errada ao esquecer do avô"""
        self.prioridade = datetime.strptime(self.dados['prioridade'], "%d/%m/%Y %H:%M:%S")
        self.data_protocolo = datetime.strptime(self.dados['data_protocolo'], "%d/%m/%Y %H:%M:%S")
        return self.prioridade

    def dadosBasicosGet(self, data_tags=None, download=True):
        """dowload the dados basicos scm main html page or 
        use the existing one stored at `self.html_dbasicospage` 
        than parse all data_tags passed storing the resulting in `self.dados`
        return True if succeed on parsing every tag False ortherwise
        """
        if data_tags is None: # data tags to fill in 'dados' with
            data_tags = scm_data_tags.copy()
        if download: # download get with python.requests page html response            
            self.dadosBasicosPageRetrieve()
        # using class field directly       
        soup = BeautifulSoup(self.html_dbasicospage, features="lxml")
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

    def dadosPoligonalGet(self, redo=False, download=True):
        """dowload the dados scm poligonal html page or 
        use the existing one stored at `self.html_poligonpage` 
        than parse all data_tags passed storing the resulting in `self.polydata`
        return True           
          * note: not used by self.run!
        """
        if download: # download get with python.requests page html response  
            self.dadosPoligonalPageRetrieve()
        # dont need to retrieve anything
        soup = BeautifulSoup(self.html_poligonpage, features="lxml")
        if self.verbose:
            with mutex:
                print("dadosPoligonalGet - parsing: ", self.processostr, file=sys.stderr)
        
        htmltables = soup.findAll('table', { 'class' : 'BordaTabela' }) #table[class="BordaTabela"]
        if htmltables: 
            memorial = htmlscrap.tableDataText(htmltables[-1])
            data = htmlscrap.tableDataText(htmltables[1])
            data = data[0:5] # informações memo descritivo
            self.polydata = {'area'     : float(data[0][1].replace(',', '.')), 
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
            return True
        else: # might not have poligonal data, some error
            return False        

    def dadosBasicosFillMissing(self):
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
        miss_data_tags = Processo.specifyDataToParse(missing)
        # processo father
        fathername = self.dados['processos_associados'][1][5]
        if fmtPname(fathername) == fmtPname(self.processostr): # doesn't have father
            return False
        father = Processo.Get(fathername, self.wpage)
        father.dadosBasicosGet(miss_data_tags)
        self.dados.update(father.dados)
        del father
        return self.dados


    def to_json(self):
        """json serialize this process 
            - not fully tested
            - no thread support yet"""
        proc = {}

        # create a dict of the object and then to json 
        return json.dumps()


    @staticmethod
    def fromStrHtml(processostr, html_basicos, html_poligonal=None, verbose=True):
        """Create a `Processo` from a html str of basicos and poligonal (if available)
            - main_html : str (optional)
                directly from a request.response.content string previouly saved  
                `processostr` must be set
        """
        processo = Processo.Get(processostr, htmlscrap.wPageNtlm('', ''), verbose=verbose, run=False)
        processo.html_dbasicospage = html_basicos
        processo.dadosBasicosGet(download=False) 
        if html_poligonal:
            processo.html_poligonpage = html_poligonal
            if not processo.dadosPoligonalGet(download=False):
                if verbose:
                    print('Some error on poligonal page cant read poligonal table', file=sys.stderr)
        return processo


    @staticmethod
    def fromHtml(path='.', processostr=None, verbose=True):
        """Try create a `Processo` from a html's of basicos and poligonal (optional)       
        """
        curdir = os.getcwd()
        os.chdir(path)
        path_main_html = glob.glob('*basicos*.html')[0] # html file on folder
        path_poligon_html = glob.glob('*poligonal*.html') # html file on folder
        main_html = None        
        poligon_html = None
        if not processostr: # get process str name by file name
            processostr= fmtPname(glob.glob('*basicos*.html')[0])

        with open(path_main_html, 'r') as f: # read html scm
            main_html = f.read()

        if path_poligon_html: # if present
            path_poligon_html = path_poligon_html[0]
            with open(path_poligon_html, 'r') as f: # read html scm
                poligon_html = f.read()
        else:
            print('Didnt find a poligonal page html saved', file=sys.stderr)
        os.chdir(curdir) # go back
        
        return Processo.fromStrHtml(processostr, main_html, poligon_html, verbose=verbose)

    @staticmethod
    def Get(processostr, wpagentlm, dados=3, verbose=True, run=True):
        """
        Create a new or get a Processo from ProcessStorage

        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos

        Dados:
        1. scm dados basicos page  
        2. anterior + processos associados (father and direct sons)  
        3. anterior + correção prioridade ancestor list  
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
        if run: # wether run the task, dont run when loading from file/str
            processo.runtask(cdados=dados)
        return processo


# Inherits from dict since it is:
# 1. the recommended global approach 
# 2. thread safe for 'simple set/get'
class ProcessStorageClass(dict):
    """Container of processes to avoid 
    1. connecting/open page of SCM again
    2. parsing all information again    
    * If it was already parsed save it in here { key : value }
    * key : unique `fmtPname` process string
    * value : `scm.Processo` object
    """
    @staticmethod
    def saveStorageJson(self):
        pass

    @staticmethod
    def loadStorageJson(self):
        pass

ProcessStorage = ProcessStorageClass()
"""Container of processes to avoid 
1. connecting/open page of SCM again
2. parsing all information again    
* If it was already parsed save it in here { key : value }
* key : unique `fmtPname` process string
* value : `scm.Processo` object
"""




