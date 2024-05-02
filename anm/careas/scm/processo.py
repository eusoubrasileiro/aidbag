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
    writeHTML,
    saveSimpleHTML,
    try_read_html,
    fetchSimpleHTMLStr
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

from .sqlalchemy import Processodb, object_session

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


def updatedb(method):
    """
    Decorator that refreshes the object at the beginning of the wrapped method and
    updates the database after the wrapped method is executed.
    `refresh` re-add it to the session if it is not already attached to the session.
    Session is opened and closed at the end of method call.
    Used for methods that update the database.
    """    
    @wraps(method) # preserves method name, docstring, etc
    def wrapper(self, *args, **kwargs):
        with self._manager.session() as session:
            if object_session(self.db) is None:
                session.add(self.db)
            session.refresh(self.db)
            result = method(self, *args, **kwargs)
            session.commit()            
        return result
    return wrapper

def readdb(method):
    """
    Decorator that refreshes-updates the sqlalchemy object at the begging.
    `refresh` re-add it to the session if it is not already attached to the session.
    Session is opened and closed at the end of method call.
    Used for methods that only read the database.
    """    
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._manager.session() as session:
            if object_session(self.db) is None:
                session.add(self.db)
            session.refresh(self.db)
            result = method(self, *args, **kwargs)       
        return result 
    return wrapper

def threadsafe(function):   
    """Decorator for methods of `Processo` needing thread safe execution.
    The same 'Processo' may exist on different threads but method execution 
    must be controled by `threading.RLock` so that only one thread can write on 
    the object (database-object) at a time.         
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
        name = fmtPname(processostr)
        self._manager = manager
        with manager.session() as session:                        
            if processodb is None:
                self.db = Processodb(fmtPname(processostr))
                self.db.dados.update(default_run_state())
            else:
                self.db = processodb     
            session.add(self.db)   
            session.commit()
        # `fmtPname` unique string process number/year
        self.number, self.year = numberyearPname(name)
        self._isdisp = True if str(self.number)[0] == 3 else False # if starts 3xx.xxx/xxx disponibilidade  
        if wpagentlm: 
            self._wpage = wPageNtlm(wpagentlm.user, wpagentlm.passwd)
        # might be None in case loading from JSON, html etc...        
        self._verbose = verbose                             
        self.lock = RLock()
    
    def delete(self):
        """
        Use this to delete the object from the database.
        Then you can del the object.
        """
        with self._manager.session() as session:
            session.delete(self.db)
            session.commit()

    # properties to be used by other classes/functions not self

    @property
    @readdb    
    def basic_html(self):
        return self.db.basic_html
    
    @property
    @readdb
    def polygon_html(self):
        return self.db.polygon_html
    
    @property
    @readdb
    def name(self):
        return self.db.name
    
    @property
    @readdb
    def modified(self):
        return self.db.modified

    @property
    @readdb
    def dados(self):
        return copy.deepcopy(self.db.dados) # avoid reference change tracking

    @threadsafe # avoid multiple threads writing at the same time
    @updatedb    
    def update(self, key, value):        
        self.db.dados[key] = value

    @readdb
    def __repr__(self):
        return self.db.__repr__()

    @readdb
    def __getitem__(self, key):
        """get a copy of property from the data dictionary if exists"""        
        return copy.deepcopy(self.db.dados[key])

    @readdb
    def __contains__(self, key):
        """check if property exist on self.dados"""
        return key in self.db.dados

    @threadsafe
    @readdb
    def runTask(self, task=SCM_SEARCH.BASICOS, wpage=None):
        """Run task from enum SCM_SEARCH desired data."""
        if self._wpage is None: # to support being called without wp set 
            self._wpage = wpage
        if task in SCM_SEARCH: # passed argument to perform a default call without args
            if SCM_SEARCH.BASICOS in task and not self.db.dados['run']['basicos']:
                self._dadosBasicosGetIf()
            if SCM_SEARCH.POLIGONAL in task and not self.db.dados['run']['polygonal']:
                self._dadosPoligonalGetIf()
            if SCM_SEARCH.ASSOCIADOS in task and not self.db.dados['run']['associados']:
                self._expandAssociados()
            if SCM_SEARCH.PRIORIDADE in task and not self.db.dados['run']['ancestry']:
                self._ancestry()

    @threadsafe
    @updatedb
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
        dados = self.db.dados
        if not dados['run']['basicos']:
            self._dadosBasicosGetIf()

        if self._verbose:
            print("expandAssociados - getting associados: ", self.db.name,
            ' - ass_ignore: ', ass_ignore, file=sys.stderr)

        if dados['run']['associados']: 
            return dados['associados']

        if not dados['associados']:
            dados['run']['associados'] = True
            return
        
        # local copy for object search -> removing circular reference
        associados = dados['associados']      
        if ass_ignore: # equivalent to ass_ignore != ''
            # if its going to be ignored it's because it already exists 
            # being associated with someone 
            # !inconsistency! bug situations identified where A -> B but B !-> A on 
            # each of A and B SCM page -> SO check if ass_ignore exists on self.associados
            if ass_ignore in dados['associados']:
                # for outward search ignore this process
                del associados[ass_ignore] # removing circular reference    
            else: # !inconsistency! bug situation identified where A -> B but B !-> A 
                # encontrada em grupamento mineiro 
                # processo em mais de um grupamento mineiro
                # sendo que um dos grupamentos havia sido cancelado mas a associação não removida                    
                inconsistency = ["Process {0} associado to this process but this is NOT associado to {0} on SCM".format(
                    ass_ignore)]
                dados['inconsistencies'] += inconsistency 
                if self._verbose:
                    print("expandAssociados - inconsistency: ", self.db.name,
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
                    process_name, self._wpage, self.db.name, self._verbose) 
                    for process_name in associados}
                futures.wait(future_processes.values()) 
                #for future in concurrent.futures.as_completed(future_processes):         
                for process_name, future_process in future_processes.items():               
                    try:                        
                        future_process.result()
                    except Exception as e:                            
                        print(f"Exception raised while running expandAssociados thread for process {process_name}",
                            file=sys.stderr)     
                        if type(e) is requests.BasicosErrorSCM:
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
            print("expandAssociados - finished associados: ", self.db.name, file=sys.stderr)
        self.db.dados['run']['associados'] = True   

    @threadsafe
    @updatedb
    def _ancestry(self):
        """
        Build graph of all associados.
        Get root node or older parent.               
        """
        dados = self.db.dados
        if not dados['run']['basicos']:
            self._dadosBasicosGetIf()

        if self._verbose:
            print("ancestrySearch - building graph: ", self.db.name, file=sys.stderr)    
            
        if dados['run']['ancestry']:
            return dados['prioridadec']

        self.db.dados['prioridadec'] = dados['prioridade']
        if not dados['run']['associados'] and not dados['associados']:             
            self.db.dados['run']['ancestry'] = True            
            return dados['prioridadec']
        else:
            self._expandAssociados()            
            
        if dados['associados']: # not dealing with grupamento many parents yet
            try:                
                # graph, root = ancestry.createGraphAssociados(self)
                #TODO: This is WRONG! root is not the real oldest process is only the graph root
                # should use 'parents' and 'sons' instead and `comparePnames`
                # self.db.dados['prioridadec'] = self._manager[root]['prioridade']
                pass
            except RecursionError:
                # TODO analyse case of graph with closed loop etc.
                pass 

        self.db.dados['run']['ancestry'] = True
        return dados['prioridadec']

    @readdb
    def _dadosBasicosGetIf(self, **kwargs):
        """wrap around `_dadosBasicosGet`to download only if page html
        was not downloaded yet"""
        if not self.db.basic_html:
            self._dadosBasicosGet(**kwargs)
        else: 
            self._dadosBasicosGet(download=False, **kwargs)    

    @threadsafe
    @updatedb
    def _pageRequest(self, name):
        """python requests page and get response unicode str decoded"""
        if not isinstance(self._wpage, wPageNtlm):
            raise Exception('Invalid `wPage` instance!')
        # str unicode page
        html, url = requests.pageRequest(name, self.db.name, self._wpage, False)        
        if name == 'basic':
            self.db.basic_html = html # I don't need images here
        else: # polygon images will be embedded as base64 strings hence perfectly displayable
            self.db.polygon_html = fetchSimpleHTMLStr(url, html=html, 
                session=self._wpage.session, verbose=self._verbose)

    @threadsafe
    @updatedb
    def _dadosBasicosGet(self, data_tags=None, download=True):
        """dowload the dados basicos scm main html page or 
        use the existing one stored at `self._pages` 
        than parse all data_tags passed storing the resulting in `self.db.dados`
        return True if succeed on parsing every tag False ortherwise
        """        
        if not self.db.dados['run']['basicos']: # if not done yet
            if data_tags is None: # data tags to fill in 'dados' with
                data_tags = scm_data_tags.copy()
            if download: # download get with python.requests page html response            
                self._pageRequest('basic')        
            if self.db.basic_html:
                if self._verbose:
                    print("dadosBasicosGet - parsing: ", self.db.name, file=sys.stderr)        
                # using class field directly       
                dados = parseDadosBasicos(self.db.basic_html, 
                    self.db.name, self._verbose, data_tags)            
                self.db.dados.update(dados)
                self.db.dados['run']['basicos'] = True 
                
    @readdb
    def _dadosPoligonalGetIf(self, **kwargs):
        """wrap around `_dadosPoligonalGet`to download only if page html
        was not downloaded yet"""
        if not self.db.polygon_html:
            self._dadosPoligonalGet(**kwargs)
        else: 
            self._dadosPoligonalGet(download=False, **kwargs)         

    @threadsafe
    @updatedb
    def _dadosPoligonalGet(self, download=True):
        """dowload the dados scm poligonal html page or 
        use the existing one stored at `self._pages` 
        than parse all data_tags passed storing the resulting in `self.db.dados['poligonal']`
        return True           
          * note: not used by self.run!
        """
        if not self['run']['polygonal']: 
            if download: # download get with python.requests page html response  
                self._pageRequest('polygon')
            if self.db.polygon_html:
                if self._verbose:
                    print("dadosPoligonalGet - parsing: ", self.name, file=sys.stderr)   
                dados = parseDadosPoligonal(self.db.polygon_html, self._verbose)
                self.db.dados.update({'polygon' : dados })                       
                self.db.dados['run']['polygonal'] = True                     

    @threadsafe
    @updatedb
    def _dadosBasicosFillMissing(self):
        """try fill dados faltantes pelo processo associado (pai) 1. UF 2. substancias
            need to be reviewed, wrong assumption about parent process   
        """
        if not self.db.dados['run']['associados']:
            self._expandAssociados()
        if self.db.dados['associados']:
            miss_data_tags = getMissingTagsBasicos(self.db.dados)        
            father = self._manager.GetorCreate(self.db.dados['parents'][0], self._wpage, verbose=self._verbose, run=False)
            father._dadosBasicosGetIf(data_tags=miss_data_tags)
            self.db.dados.update(father._dados)
            return True
        else:
            return False
        
    @threadsafe
    @updatedb
    def salvaPageScmHtml(self, html_path, pagename='basic', overwrite=False):
        """Save SCM Html page 'Basicos' or 'Poligonal' tab.

        Args:
            html_path (str): pathlib.Path where to save
            pagename (str): 'basic' or 'polygon'
            overwrite (bool): wether to overwrite already saved html
        """                
        path = pathlib.Path(html_path).joinpath(config['scm']['html_prefix'][pagename]+
                                                self.number+'_'+self.year)
        if not overwrite and path.with_suffix('.html').exists():
            return 
        if( (pagename == 'basic'and not self.db.basic_html) or
            (pagename == 'polygon'and not self.db.polygon_html) ):
            self._pageRequest(pagename) 
        html = self.db.basic_html if(pagename == 'basic') else self.db.polygon_html        
        # save the already fetched html as single file
        writeHTML(str(path), html)   


        
            
