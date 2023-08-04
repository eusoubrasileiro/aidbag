import sys, copy, pathlib  
import datetime, os 
import traceback
from concurrent import futures
import enum
import time
import tqdm
from threading import RLock
from functools import wraps

from ....general import progressbar 
from ....web.htmlscrap import wPageNtlm
from ....web.io import (
    saveHtmlPage,
    saveFullHtmlPage, 
    try_read_html
    )

from . import requests 
from . import ancestry
from ..config import config

from .util import (
    fmtPname,
    numberyearPname,
    processUniqueNumber
)

from .parsing import (
    parseDadosPoligonal,
    scm_data_tags,
    parseNUP,
    parseDadosBasicos,
    getMissingTagsBasicos
)

from .requests import urls as requests_urls
from .sqlalchemy import Processodb

default_run_state = lambda: copy.deepcopy({ 'run' : 
    { 'basicos': False, 'associados': False, 'ancestry': False, 'polygonal': False } })
""" start state of running parsing processes of process - without deepcopy all mess expected"""

class SCM_SEARCH(enum.Flag):
    """what to search to fill in a `Processo` class"""
    NONE = enum.auto()
    BASICOS = enum.auto()
    ASSOCIADOS = enum.auto()
    PRIORIDADE = enum.auto()
    POLIGONAL = enum.auto()    
    BASICOS_POLIGONAL = BASICOS | POLIGONAL
    ALL = BASICOS | ASSOCIADOS | PRIORIDADE | POLIGONAL


def update_database_on_finish(method):
    """Decorator that updates the database after the wrapped method is executed."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        self._manager.session.commit()
        return result
    return wrapper

def thread_safe(function):
    """Decorator for methods of `Processo` needing thread safe execution.
    The same 'Processo' may exist on different threads but method execution 
    must be controled by `threading.RLock` so that only one thread can write on 
    the database-object at a time.         
    Uses self.lock field"""
    @wraps(function)
    def wrapper(self, *args, **kwargs):            
        if not self.lock.acquire(timeout=60.*2):
            raise TimeoutError(f"Wait time-out in function {function.__name__} for process { self.name }")
        result = function(self, *args, **kwargs)            
        self.lock.release() # make it free
        return result 
    return wrapper

class Processo():    
    def __init__(self, processostr : str, wpagentlm : wPageNtlm = None, 
            processodb : Processodb = None, manager = None, 
            verbose : bool = False ):
        super().__init__()        
        if processodb is None:
            self.db = Processodb(fmtPname(processostr))
            self.db.dados.update(default_run_state())
        else:
            self.db = processodb
        self._manager = manager
        # `fmtPname` unique string process number/year
        self.number, self.year = numberyearPname(self.db.name)
        self._isdisp = True if str(self.number)[0] == 3 else False # if starts 3xx.xxx/xxx disponibilidade  
        if wpagentlm: 
            self._wpage = wPageNtlm(wpagentlm.user, wpagentlm.passwd)
        # might be None in case loading from JSON, html etc...        
        self._verbose = verbose                            
        self._requests_session = None   
        self.lock = RLock()

    @property
    def basic_html(self):
        return self.db.basic_html

    @property
    def polygon_html(self):
        return self.db.polygon_html

    @property
    def name(self):
        return self.db.name

    @property
    def modified(self):
        return self.db.modified

    @property
    def dados(self):
         return copy.deepcopy(self.db.dados)

    def __getitem__(self, key):
        """get a copy of property from the data dictionary if exists"""        
        return copy.deepcopy(self.db.dados[key])

    def __contains__(self, key):
        """check if property exist on self.dados"""
        return key in self.db.dados

    def runTask(self, task=SCM_SEARCH.BASICOS, wpage=None):
        """Run task from enum SCM_SEARCH desired data."""
        if self._wpage is None: # to support being called without wp set 
            self._wpage = wpage
        if task in SCM_SEARCH: # passed argument to perform a default call without args
            if SCM_SEARCH.BASICOS in task and not self['run']['basicos']:
                self._dadosBasicosGetIf()
            if SCM_SEARCH.POLIGONAL in task and not self['run']['polygonal']:
                self._dadosPoligonalGetIf()
            if SCM_SEARCH.ASSOCIADOS in task and not self['run']['associados']:
                self._expandAssociados()
            if SCM_SEARCH.PRIORIDADE in task and not self['run']['ancestry']:
                self._ancestry()

    @thread_safe
    @update_database_on_finish
    def _expandAssociados(self, ass_ignore=''):
        """
        Search and Load on `ProcessManager` all processes associated with this. 

        * ass_ignore - to ignore in associados list (remove)

        'associados' must be in self.db.dados dict to build anscestors and sons

        The search is done using a ThreadPool for all 'associados'.
        That cascades searches for each 'associado' also using a ThreadPool. 
        To make it outward only (avoiding circular reference) 
        the source of the search is always passed to be ignored on the next search.

        """
        if not self['run']['basicos']:
            self._dadosBasicosGetIf()

        if self._verbose:
            print("expandAssociados - getting associados: ", self.name,
            ' - ass_ignore: ', ass_ignore, file=sys.stderr)

        if self['run']['associados']: 
            return self['associados']

        if not self['associados']:
            self.db.dados['run']['associados'] = True
            return
        
        # local copy for object search -> removing circular reference
        associados = self['associados']      
        if ass_ignore: # equivalent to ass_ignore != ''
            # if its going to be ignored it's because it already exists 
            # being associated with someone 
            # !inconsistency! bug situations identified where A -> B but B !-> A on 
            # each of A and B SCM page -> SO check if ass_ignore exists on self.associados
            if ass_ignore in self['associados']:
                # for outward search ignore this process
                del associados[ass_ignore] # removing circular reference    
            else: # !inconsistency! bug situation identified where A -> B but B !-> A 
                # encontrada em grupamento mineiro 
                # processo em mais de um grupamento mineiro
                # sendo que um dos grupamentos havia sido cancelado mas a associação não removida                    
                inconsistency = ["Process {0} associado to this process but this is NOT associado to {0} on SCM".format(
                    ass_ignore)]
                self.db.dados['inconsistencies'] += inconsistency 
                if self._verbose:
                    print("expandAssociados - inconsistency: ", self.name,
                    ' : ', inconsistency, file=sys.stderr)
        # helper function to search outward only
        def _expandassociados(name, wp, ignore, verbosity):
            """ *ass_ignore : must be set to avoid being waiting for parent-source 
                Also make the search spread outward only"""
            proc = self._manager.GetorCreate(name, wp, SCM_SEARCH.BASICOS, verbosity)                
            proc._expandAssociados(ignore)
            return proc
        # ignoring empty lists 
        if associados:
            with futures.ThreadPoolExecutor() as executor: # thread number optimal       
                # use a dict to map { process name : future_wrapped_Processo }             
                # due possibility of exception on Thread and to know which process was responsible for that
                future_processes = {process_name : executor.submit(_expandassociados, 
                    process_name, self._wpage, self.name, self._verbose) 
                    for process_name in associados}
                futures.wait(future_processes.values()) 
                #for future in concurrent.futures.as_completed(future_processes):         
                for process_name, future_process in future_processes.items():               
                    try:                        
                        future_process.result()
                    except Exception as e:                            
                        print(f"Exception raised while running expandAssociados thread for process {process_name}",
                            file=sys.stderr)     
                        if type(e) is requests.ErrorProcessSCM:
                            # MUST delete process if did not get scm page
                            # since basic data wont be on it, will break ancestry search etc... 
                            del self._manager[process_name]
                            del self.db.dados['associados'][process_name]
                            print(str(e) + f" Removed from associados. Exception ignored!",
                                file=sys.stderr)
                        else:
                            print(traceback.format_exc(), file=sys.stderr, flush=True)     
                            raise # re-raise                  
        if self._verbose:
            print("expandAssociados - finished associados: ", self.name, file=sys.stderr)
        self.db.dados['run']['associados'] = True   

    @thread_safe
    @update_database_on_finish
    def _ancestry(self):
        """
        Build graph of all associados.
        Get root node or older parent.               
        """
        if not self['run']['basicos']:
            self._dadosBasicosGetIf()

        if self._verbose:
            print("ancestrySearch - building graph: ", self.name, file=sys.stderr)    
            
        if self['run']['ancestry']:
            return self['prioridadec']

        self.db.dados['prioridadec'] = self['prioridade']
        if not self['run']['associados'] and not self['associados']:             
            self.db.dados['run']['ancestry'] = True            
            return self['prioridadec']
        else:
            self._expandAssociados()            
            
        if self['associados']: # not dealing with grupamento many parents yet
            try:
                graph, root = ancestry.createGraphAssociados(self)
                #TODO: This is WRONG! root is not the real oldest process is only the graph root
                # should use 'parents' and 'sons' instead and `comparePnames`
                self.db.dados['prioridadec'] = self._manager[root]['prioridade']
            except RecursionError:
                # TODO analyse case of graph with closed loop etc.
                pass 

        self.db.dados['run']['ancestry'] = True
        return self['prioridadec']

            
    def _dadosBasicosGetIf(self, **kwargs):
        """wrap around `_dadosBasicosGet`to download only if page html
        was not downloaded yet"""
        if not self.db.basic_html:
            self._dadosBasicosGet(**kwargs)
        else: 
            self._dadosBasicosGet(download=False, **kwargs)    

    @thread_safe
    @update_database_on_finish
    def _pageRequest(self, name):
        """python requests page and get response unicode str decoded"""
        if not isinstance(self._wpage, wPageNtlm):
            raise Exception('Invalid `wPage` instance!')
        # str unicode page
        html, _, session = requests.pageRequest(name, self.name, self._wpage, False)
        self._requests_session = session
        if name == 'basic':
            self.db.basic_html = html
        else:
            self.db.polygon_html = html

    @thread_safe
    @update_database_on_finish
    def _dadosBasicosGet(self, data_tags=None, download=True):
        """dowload the dados basicos scm main html page or 
        use the existing one stored at `self._pages` 
        than parse all data_tags passed storing the resulting in `self.db.dados`
        return True if succeed on parsing every tag False ortherwise
        """
        if not self['run']['basicos']: # if not done yet
            if data_tags is None: # data tags to fill in 'dados' with
                data_tags = scm_data_tags.copy()
            if download: # download get with python.requests page html response            
                self._pageRequest('basic')        
            if self.db.basic_html:
                if self._verbose:
                    print("dadosBasicosGet - parsing: ", self.name, file=sys.stderr)        
                # using class field directly       
                dados = parseDadosBasicos(self.db.basic_html, 
                    self.name, self._verbose, data_tags)            
                self.db.dados.update(dados)
                self.db.dados['run']['basicos'] = True 
                

    def _dadosPoligonalGetIf(self, **kwargs):
        """wrap around `_dadosPoligonalGet`to download only if page html
        was not downloaded yet"""
        if not self.db.polygon_html:
            self._dadosPoligonalGet(**kwargs)
        else: 
            self._dadosPoligonalGet(download=False, **kwargs)         

    @thread_safe
    @update_database_on_finish
    def _dadosPoligonalGet(self, download=True):
        """dowload the dados scm poligonal html page or 
        use the existing one stored at `self._pages` 
        than parse all data_tags passed storing the resulting in `self.db.dados['poligonal']`
        return True           
          * note: not used by self.run!
        """
        if not self['run']['polygonal']: 
            if download: # download get with python.requests page html response  
                self._pageRequest('poligon')
            if self.db.polygon_html:
                if self._verbose:
                    print("dadosPoligonalGet - parsing: ", self.name, file=sys.stderr)   
                dados = parseDadosPoligonal(self.db.polygon_html, self._verbose)
                self.db.dados.update({'poligon' : dados })                       
                self.db.dados['run']['polygonal'] = True                     

    @thread_safe
    @update_database_on_finish
    def _dadosBasicosFillMissing(self):
        """try fill dados faltantes pelo processo associado (pai) 1. UF 2. substancias
            need to be reviewed, wrong assumption about parent process   
        """
        if not self['run']['associados']:
            self._expandAssociados()
        if self['associados']:
            miss_data_tags = getMissingTagsBasicos(self.db.dados)        
            father = self._manager.GetorCreate(self['parents'][0], self._wpage, verbose=self._verbose, run=False)
            father._dadosBasicosGetIf(data_tags=miss_data_tags)
            self.db.dados.update(father._dados)
            return True
        else:
            return False
        

    def salvaPageScmHtml(self, html_path, pagename='basic', overwrite=False):
        """Save SCM Html page 'Basicos' or 'Poligonal' tab.

        Args:
            html_path (str): pathlib.Path where to save
            pagename (str): 'basic' or 'poligon'
            overwrite (bool): weather to overwrite already saved html
        """                
        path = pathlib.Path(html_path).joinpath(config['scm']['html_prefix'][pagename]+
                                                self.number+'_'+self.year)
        if not overwrite and path.with_suffix('.html').exists():
            return 
        if( (pagename == 'basic'and not self.db.basic_html) or
            (pagename == 'poligon'and not self.db.polygon_html) ):
                self._pageRequest(pagename) # get/fill-in self._requests_session          
        html = self.db.basic_html if(pagename == 'basic') else self.db.polygon_html
        if self._requests_session: # save html and page contents - full page  
            # MUST re-use session due ASP.NET authentication etc.           
            saveFullHtmlPage(requests_urls[pagename], str(path), self._requests_session, html)          
        else: # save simple plain html text page
            saveHtmlPage(str(path), html)   


        
            
