import sys, copy, pathlib  
import datetime, os 
import traceback
from concurrent import futures
import enum
import time
import tqdm
from threading import RLock
from functools import wraps
from typing import Literal

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

from .pud import pud 

from .parsing import (
    parseDadosBasicos,
    parseDadosPoligonal,
    scm_data_tags,
    parseNUP,    
    getMissingTagsBasicos
)

from .sqlalchemy import Processodb, object_session

default_run_state = lambda: copy.deepcopy({ 'run' : 
    { 'basic': False, 'associados': False, 'ancestry': False, 'polygon': False } })
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


def updatedb(method: callable) -> callable: 
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

def readdb(method: callable) -> callable:
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

def threadsafe(function: callable) -> callable:   
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
    """
    Class representing a mining process (Processo).

    This class handles the retrieval, parsing, and storage of data related to a mining process SCM website.
    The data is stored in a SQLite database using the SQLAlchemy ORM.

    Attributes:
        name (str): The formatted name of the mining process.
        number (int): The process number.
        year (int): The year of the process.
        _isdisp (bool): Indicates if the process is related to availability (starts with 3xx.xxx/xxx).
        _wpage (wPageNtlm): An instance of the wPageNtlm class for web scraping.
        db (Processodb): The SQLAlchemy object representing the database row for this process.
        lock (RLock): A reentrant lock for thread-safe access to the object.

    Note:
        The `dados` attribute, which contains the process data, is stored as a single JSON column in the SQLite database.
        To retrieve the data, use `self.dados` (a deep copy is returned to avoid reference changes).
        To update the data, first modify the dictionary obtained from `self.dados`, then call `self.update(modified_dict)`.
        This will update the entire `dados` column in the database with the modified dictionary.
        
    Update Effect:
        Based on this if the process is downloaded again only the fields that changed from the dictionary will be updated.
    """       
    def __init__(self, processostr : str, wpagentlm : wPageNtlm = None, 
            processodb : Processodb = None, manager = None, 
            verbose : bool = False ):
        super().__init__()                     
        self.pud = pud(processostr)
        self.name = self.pud.str # will/MUST never change
        self._manager = manager
        with manager.session() as session:                        
            if processodb is None:
                self.db = Processodb(self.name)
                self.db.dados.update(default_run_state())
            else:
                self.db = processodb     
            session.add(self.db)   
            session.commit()                
        self.number, self.year = self.pud.numberyear        
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

    def __getitem__(self, key):        
        return self.dados[key]

    @property
    @readdb    
    def basic_html(self):
        return self.db.basic_html

    @property
    @readdb
    def polygon_html(self):
        return self.db.polygon_html    
    
    @threadsafe
    @updatedb
    def _set_html(self, page: Literal['basic', 'polygon'], value):        
        "html page setter"
        if page == 'basic':
            self.db.basic_html = value
        elif page == 'polygon':
            self.db.polygon_html = value        

    @readdb
    def _get_html(self, page: Literal['basic', 'polygon']):
        "html page getter"
        if page == 'basic':
            return self.db.basic_html
        elif page == 'polygon':
            return self.db.polygon_html
    
    @property
    @readdb
    def modified(self):
        return self.db.modified

    @property
    @readdb
    def dados(self):
        return copy.deepcopy(self.db.dados) # avoid reference change tracking    
    
    @threadsafe
    @updatedb
    def update(self, _dict):
        """        
        Read with self.dados first then update the dict,
        and then call this to update the database.
        Note:
        There's only ONE column DADOS (JSON) on the DB.
        No matter if you modify only one key the ENTIRE dictionary 
        will ALWAYS be updated on the database.
        """
        self.db.dados.update(_dict)

    @readdb
    def __repr__(self):
        return self.db.__repr__()
   
    def runTask(self, task=SCM_SEARCH.BASICOS, wpage=None):
        """Run task from enum SCM_SEARCH desired data."""
        run = self['run']
        if self._wpage is None: # to support being called without wp set 
            self._wpage = wpage
        if task in SCM_SEARCH: # passed argument to perform a default call without args
            if SCM_SEARCH.BASICOS in task and not run['basic']:
                self._dadosScmGet('basic')
            if SCM_SEARCH.POLIGONAL in task and not run['polygon']:
                self._dadosScmGet('polygon')
            if SCM_SEARCH.ASSOCIADOS in task and not run['associados']:
                self._expandAssociados()
            if SCM_SEARCH.PRIORIDADE in task and not run['ancestry']:
                self._ancestry()

    @threadsafe
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

        if not self['run']['basic']:
            self._dadosScmGet('basic')

        if self._verbose:
            print("expandAssociados - getting associados: ", self.name,
            ' - ass_ignore: ', ass_ignore, file=sys.stderr)

        if self['run']['associados']: 
            return self['associados']

        dados = self.dados        
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
                        if type(e) is requests.BasicosErrorSCM:
                            # MUST delete process if did not get scm page
                            # since basic data wont be on it, will break ancestry search etc... 
                            del self._manager[process_name]
                            del dados['associados'][process_name]
                            self.update(dados)
                            print(str(e) + f" Removed from associados. Exception ignored!",
                                file=sys.stderr)
                        else:
                            print(traceback.format_exc(), file=sys.stderr, flush=True)     
                            raise # re-raise                  
        if self._verbose:
            print("expandAssociados - finished associados: ", self.name, file=sys.stderr)
        dados['run']['associados'] = True
        self.update(dados)

    @threadsafe
    def _ancestry(self):
        """
        Build graph of all associados.
        Get root node or older parent.               
        """        
        if not self['run']['basic']:
            self._dadosScmGet('basic')
            
        if self['run']['ancestry']:
            return self['prioridadec']

        if self._verbose:
            print("ancestrySearch - building graph: ", self.name, file=sys.stderr)        
        
        dados = self.dados
        dados['run']['ancestry'] = True        
        dados['prioridadec'] = dados['prioridade']
        self.update(dados)
            
        # if dados['associados']: # not dealing with grupamento many parents yet
        #     try:                
        #         # graph, root = ancestry.createGraphAssociados(self)
        #         #TODO: This is WRONG! root is not the real oldest process is only the graph root
        #         # should use 'parents' and 'sons' instead and `comparePnames`
        #         # self.db.dados['prioridadec'] = self._manager[root]['prioridade']
        #         pass
        #     except RecursionError:
        #         # TODO analyse case of graph with closed loop etc.
        #         pass 
        
    def _pageRequest(self, name : Literal['basic', 'polygon']):
        """python requests page and get response unicode str decoded"""
        if not isinstance(self._wpage, wPageNtlm):
            raise Exception('Invalid `wPage` instance!')
        # str unicode page
        html, url = requests.pageRequest(name, self.name, self._wpage, False)        
        if name == 'basic':
            self._set_html('basic', html) # I don't need images here
        else: # polygon images will be embedded as base64 strings hence perfectly displayable
            self._set_html('polygon', fetchSimpleHTMLStr(url, html=html, 
                session=self._wpage.session, verbose=self._verbose))

    @threadsafe
    def _dadosScmGet(self, 
        page_key : Literal['basic', 'polygon'],
        data_tags : dict = None, 
        redownload : bool = False):
        """
        download or redownload the dados scm basic html or polygon page or
        use the existing one stored at `self._pages` if `redownload` False
        """
        dados = self.dados
        if not dados['run'][page_key]:            
            if redownload or not self._get_html(page_key): # download get with python.requests page html response
                self._pageRequest(page_key)
            if self._get_html(page_key): # if sucessful get html
                if self._verbose:
                    print(f"_dadosScmGet - parsing {page_key} for {self.name}", file=sys.stderr)
                if page_key == 'basic':
                    newdados = parseDadosBasicos(self.basic_html, self.name, self._verbose, data_tags) 
                elif page_key == 'polygon':
                    newdados = parseDadosPoligonal(self.polygon_html, self._verbose)
                dados.update(newdados)           
                dados['run'][page_key] = True
                self.update(dados)  

    @threadsafe
    def _dadosBasicosFillMissing(self):
        """try fill dados faltantes pelo processo associado (pai) 1. UF 2. substancias
            need to be reviewed, wrong assumption about parent process   
        """        
        if not self['run']['associados']:
            self._expandAssociados()
        dados = self.dados
        if dados['associados']:
            miss_data_tags = getMissingTagsBasicos(dados)        
            father = self._manager.GetorCreate(dados['parents'][0], self._wpage, verbose=self._verbose, run=False)
            father._dadosScmGet('basic', data_tags=miss_data_tags)            
            dados.update(father.dados)
            self.update(dados)
            return True
        else:
            return False        
    
    def salvaPageScmHtml(self, html_path, 
        pagename : Literal['basico', 'polygon'] = 'basico', 
        overwrite: bool = False):
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
        if not self._get_html(pagename) or overwrite:
            self._pageRequest(pagename)                     
        # save the already fetched html as single file
        writeHTML(str(path), self._get_html(pagename)  )   


        
            
