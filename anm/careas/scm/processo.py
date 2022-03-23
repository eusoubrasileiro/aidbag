import sys, os, copy
import glob, json

from . import ancestry
from ....web.htmlscrap import wPageNtlm
import concurrent.futures
import threading
from threading import Lock

from .requests import (
    dadosBasicosPageRetrieve,
    dadosPoligonalPageRetrieve
)

from .util import (
    fmtPname,
    numberyearPname
)

from .parsing import (
    parseDadosPoligonal,
    scm_data_tags,
    parseNUP,
    parseDadosBasicos,
    getMissingTagsBasicos
)

mutex = Lock()
"""`threading.Lock` exists due 'associados' search with multiple threads"""


"""
Use `Processo.Get` to avoid creating duplicate Processo's
"""
class Processo:    
    def __init__(self, processostr, wpagentlm, verbose=True):
        """
        Hint: Use `Processo.Get` to avoid creating duplicate Processo's

        dados :
        1. scm dados basicos parse   
        2. 1 + expand associados   
        3. 2 + correção prioridade (ancestors list)   
        """        
        self.name = fmtPname(processostr) # `fmtPname` unique string process number/year
        self.number, self.year = numberyearPname(self.name)
        self.isdisp = True if str(self.number)[0] == 3 else False # if starts 3xx.xxx/xxx disponibilidade        
        self.wpage = wPageNtlm(wpagentlm.user, wpagentlm.passwd)
        self.verbose = verbose
        # control to avoid running again
        self.ancestry_run = False
        self.dadosbasicos_run = False
        self.associados_run = False
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
        # anscestors assessment: parents and sons  
        # process 'processos associados' to get father, grandfather etc.
        self.Associados = {}  
        """key : value - processo name : {attributes}
        attributes {} keys 'tipo','data' de associação, 'obj' scm.processo.Processo etc..."""        
        self.anscestorsprocesses = []

   
    def __getitem__(self, key):
        """get an property from the dados dictionary after `dadosbasicos_run` is True"""
        if self.dadosbasicos_run:
            return self.dados[key]
        return None 

    def runtask(self, task=None, cdados=0):
        """
        codedados :
        1. scm dados basicos parse   
        2. 1 + expand associados   
        3. 2 + correção prioridade (ancestors list)   
        """
        # check if some taks is running
        # only ONE can have this process at time
        if not self.isfree.wait(60.*2):
            raise Exception("runtask - wait time-out for process: ", self.name)
        self.isfree.clear() # make it busy
        if cdados: # passed argument to perform a default call without args
            if (cdados == 1) and not self.dadosbasicos_run:
                task = (self.dadosBasicosGet, {})
            elif (cdados == 2) and not self.associados_run:
                task = (self.expandAssociados, {})
            elif (cdados == 3) and not self.ancestry_run:
                task = (self.ancestry, {})
        if task:
            task, params = task
            if self.verbose:
                with mutex:
                    print('task to run: ', task.__name__, ' params: ', params,
                    ' - process: ', self.name, file=sys.stderr)
            task(**params)
        self.isfree.set() # make it free

    #@classmethod # not same as @staticmethod (has a self)
    #can be created on other file where the class is no present by reference it 
    def fromNumberYear(self, processo_number, processo_year, wpage):
        processostr = processo_number + r'/' + processo_year
        return self(processostr, wpage)

    @staticmethod
    def getNUP(processostr, wpagentlm):
        response = dadosBasicosPageRetrieve(processostr, wpagentlm)
        return parseNUP(response.content)

    def dadosBasicosPageRetrieve(self):
        if not self.html_dbasicospage:             
            self.response_dbasicospage = dadosBasicosPageRetrieve(self.name, self.wpage, False)
            self.html_dbasicospage = self.response_dbasicospage.content
        return self.response_dbasicospage

    def salvaDadosBasicosHtml(self, html_path):
        self.wpage.response = self.dadosBasicosPageRetrieve() # re-use request.response
        dadosbasicosfname = 'scm_basicos_'+self.number+'_'+self.year
        # re-use request.response overwrite html saved
        self.wpage.save(os.path.join(html_path, dadosbasicosfname))

    def dadosPoligonalPageRetrieve(self):
        if not self.html_poligonpage: 
            self.response_poligonpage = dadosPoligonalPageRetrieve(self.name, self.wpage, False)
            self.html_poligonpage = self.response_poligonpage.content
        return self.response_poligonpage

    def salvaDadosPoligonalHtml(self, html_path):
        self.wpage.response = self.dadosPoligonalPageRetrieve() # re-use request.response
        # sobrescreve
        dadospolyfname = 'scm_poligonal_'+self.number+'_'+self.year
        self.wpage.save(os.path.join(html_path, dadospolyfname))

    def expandAssociados(self, ass_ignore=''):
        """
        Search and Load on `ProcessStorage` all processes associated with this. 

        * ass_ignore - to ignore in associados list (remove)

        'associados' must be in self.dados dict to build anscestors and sons

        The search is done using a ThreadPool for all 'associados'.
        That cascades searches for each 'associado' also using a ThreadPool. 
        To make it outward only (avoiding circular reference) 
        the source of the search is always passed to be ignored on the next search.

        """
        if not self.dadosbasicos_run:
            self.dadosBasicosGet()

        if self.associados_run: 
            return self.Associados       

        if self.Associados:
            # local copy for object search -> removing circular reference
            associados = copy.deepcopy(self.Associados)      
            if ass_ignore: # equivalent to ass_ignore != ''
                # if its going to be ignored it's because it already exists                   
                self.Associados[ass_ignore].update({'obj' : ProcessStorage[ass_ignore]})  
                # for outward search ignore this process
                del associados[ass_ignore] # removing circular reference                
            if self.verbose:
                with mutex:
                    print("expandAssociados - getting associados: ", self.name,
                    ' - ass_ignore: ', ass_ignore, file=sys.stderr)
            # helper function to search outward only
            def _expandAssociados(name, wp, ignore, verbosity):
                """ *ass_ignore : must be set to avoid being waiting for parent-source 
                    Also make the search spread outward only"""
                proc = Processo.Get(name, wp, 0, verbosity, False)
                proc.dadosBasicosGet()
                proc.expandAssociados(ass_ignore=ignore)
                return proc
            # ignoring empty lists 
            if associados:
                with concurrent.futures.ThreadPoolExecutor() as executor: # thread number optimal       
                    # use a dict to map { process name : future_wrapped_Processo }             
                    # due possibility of exception on Thread and to know which process was responsible for that
                    #future_processes = {process_name : executor.submit(Processo.Get, process_name, self.wpage, 1, self.verbose) 
                    #    for process_name in assprocesses_name}
                    future_processes = {process_name : executor.submit(_expandAssociados, 
                        process_name, self.wpage, self.name, self.verbose) 
                        for process_name in associados}
                    concurrent.futures.wait(future_processes.values())
                    #for future in concurrent.futures.as_completed(future_processes):         
                    for process_name, future_process in future_processes.items():               
                        try:
                            # add to process name, property 'obj' process objects
                            self.Associados[process_name].update({'obj': future_process.result()})
                        except Exception as exc:
                            print("Exception raised while running expandAssociados thread for process {:0}".format(
                                process_name), file=sys.stderr)
                            raise(exc)
            if self.verbose:
                with mutex:
                    print("expandAssociados - finished associados: ", self.name, file=sys.stderr)
        self.associados_run = True
        return self.Associados

    def ancestry(self):
        """
        Build graph of all associados.
        Get root node or older parent.               
        """
        if self.ancestry_run:
            return self['prioridadec']

        if not self.associados_run:
            self.expandAssociados()

        if self.verbose:
            with mutex:
                print("ancestrySearch - building graph: ", self.name, file=sys.stderr)
        
        self.dados['prioridadec'] = self['prioridade']
        if self.Associados:
            graph, root = ancestry.createGraphAssociados(self)
            self.dados['prioridadec'] = ProcessStorage[root]['prioridade']

        self.ancestry_run = True
        return self['prioridadec']

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
        if self.verbose:
            with mutex:
                print("dadosBasicosGet - parsing: ", self.name, file=sys.stderr)        
        # using class field directly       
        new_dados = parseDadosBasicos(self.html_dbasicospage, self.name, self.verbose, mutex, data_tags)
        self.dados.update(new_dados)
        self.Associados = self.dados['associados']
        return len(self.dados) == len(data_tags) # return if got w. asked for

    def dadosPoligonalGet(self, download=True):
        """dowload the dados scm poligonal html page or 
        use the existing one stored at `self.html_poligonpage` 
        than parse all data_tags passed storing the resulting in `self.polydata`
        return True           
          * note: not used by self.run!
        """
        if download: # download get with python.requests page html response  
            self.dadosPoligonalPageRetrieve()
        # dont need to retrieve anything
        if self.verbose:
            with mutex:
                print("dadosPoligonalGet - parsing: ", self.name, file=sys.stderr)   
        self.polydata = parseDadosPoligonal(self.html_poligonpage)
        return self.polydata

    def dadosBasicosFillMissing(self):
        """try fill dados faltantes pelo processo associado (pai) 1. UF 2. substancias
            need to be reviewed, wrong assumption about parent process   
        """
        if not self.associados_run:
            self.expandAssociados()
        if self.Associados:
            miss_data_tags = getMissingTagsBasicos(self.dados)        
            father = Processo.Get(self.dados['parents'][0], self.wpage, verbose=self.verbose, run=False)
            father.dadosBasicosGet(miss_data_tags)
            self.dados.update(father.dados)
            return True
        else:
            return False

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
        processo = Processo.Get(processostr, wPageNtlm('', ''), verbose=verbose, run=False)
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




