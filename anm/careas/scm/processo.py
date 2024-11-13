import sys, copy, pathlib  
import datetime, os 
import traceback
from concurrent import futures
import enum
import time
import queue
from functools import cmp_to_key
from threading import RLock, Lock
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
from ..config import config
from .pud import pud, cmpPud
from .parsing import (
    parseDadosBasicos,
    parseDadosPoligonal,
    scm_data_tags,
    parseNUP,    
    getMissingTagsBasicos
)

from .ancestry import (
    pGraph,
    toChronology,
    is_tree    
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
            obj_session = object_session(self.db)
            # object might be on another session from another thread
            if obj_session is None or obj_session != session:                
                if obj_session is not None: # uggly but simpler
                    # in the future try something simpler like one single session?
                    # since two or more thread session cannot the same object
                    obj_session.expunge(self.db)
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
    
    def __getitem__(self, key):        
        return self.dados[key]

    def __contains__(self, item):
        return item in self.dados  # Check if item is in content

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

        G = pGraph()
        if self._verbose:
            self.graph = G # for debugging 
        visited = set() 
        # outward expand the graph using a queue instead of threads
        # MUCH simpler and safer to control what's happening and avoid deadlocks
        # slower but async is the next step
        # doesn't assume the graph is a tree or whatever else
        process_queue = queue.Queue()
        process_queue.put(self.name)
        while not process_queue.empty():
            process_name = process_queue.get()
            if process_name in visited:
                continue
            visited.add(process_name)                   
            # this here can be made async from gemini answer
            # turn from G = pGraph() .. a function
            # TODO:  Run synchronous web scraping in a thread
            # await asyncio.to_thread(self._manager.GetorCreate, process_name, ...)  #
            process =  self._manager.GetorCreate(process_name, 
                self._wpage, SCM_SEARCH.BASICOS, self._verbose) 
            associados = process['associados']['dict']
            for associado, edge_data in associados.items(): 
                if associado not in visited:
                    process_queue.put(associado)
                    # add node source -> target and  edge (arrow ->) attributes dict
                    G.add_edge(process_name, associado, **edge_data)               
                    if self._verbose:
                        print(f"Adding edge {process_name}->{associado} "
                              f"at graph at {process_name} for debugging", file=sys.stderr)
                        
        # Run the asynchronous graph construction
        # asyncio.run(build_graph_async(initial_process_name))

        if G.nodes():
            if is_tree(G): # a tree graph expected well behaved
                # graph due (cessões parciais, disponibilidade ... )
                G = toChronology(G) # oriented by chronology is save                   
                # sort everything only by name for now... todo in future check also 
                # data_assoc if an exception of comparision happens
                nodes = sorted(list(G.nodes), key=cmp_to_key(cmpPud))
                if nodes:
                    oldest = nodes[0]  
                    dados = self.dados
                    dados['prioridadec'] = self._manager[oldest]['prioridade']        
            else: # this likely a crazy, cyclic graph or worse
                # processos associados a multiplos agrupamentos que deveriam ter sido desconectados
                print("Acyclic or complex graph can't infer prioridade from oldest", file=sys.stderr)
                # you can plot and interactivly visualize it on Gephi (use Yifan Hu layout)
                # for that you need to export like bellow to .gexf format
                # Convert datetime attributes to strings
                # for u, v, attrs in p.graph.edges(data=True):
                #     for key, value in attrs.items():
                #         if isinstance(value, datetime.datetime):
                #             attrs[key] = value.isoformat()  # Convert to ISO 8601 format
                # nx.write_gexf(p.graph, 'cyclic_graph.gexf') 
        
            # graph is ready need to DB-save-it on ALL processes on its nodes
            for name in G.nodes:
                proc = self._manager[name]
                proc_dados = proc.dados
                proc_dados['associados']['graph'] = G.toList()
                proc.update(proc_dados)

        dados = self.dados
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
        
    def _pageRequest(self, name : Literal['basic', 'polygon']):
        """python requests page and get response unicode str decoded"""
        if not isinstance(self._wpage, wPageNtlm):
            raise Exception('Invalid `wPage` instance!')
        # str unicode page
        try:
            html, url = requests.pageRequest(name, self.name, self._wpage, False)        
        except requests.RequestsSCMException as e:            
            dados = self.dados
            dados['status'] = {'error' : str(e)}
            self.update(dados)                        
            raise e 
        else:
            dados = self.dados
            dados['status'] = 'ok'
            self.update(dados)                        
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
        if not dados['run'][page_key] or redownload:            
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
        if dados['associados']['dict']:
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



        
            
