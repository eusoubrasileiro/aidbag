import sys, copy, pathlib  
import datetime, zlib, os 
import json, traceback
from concurrent import futures
import threading
import enum
import functools
import time
import tqdm

from ....general import progressbar 
from ....web.htmlscrap import wPageNtlm
from ....web.io import (
    saveHtmlPage, 
    try_read_html
    )
from ....web.json import (
    datetime_to_json,
    json_to_datetime
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

class SCM_SEARCH(enum.Flag):
    """what to search to fill in a `Processo` class"""
    NONE = enum.auto()
    BASICOS = enum.auto()
    ASSOCIADOS = enum.auto()
    PRIORIDADE = enum.auto()
    POLIGONAL = enum.auto()    
    BASICOS_POLIGONAL = BASICOS | POLIGONAL
    ALL = BASICOS | ASSOCIADOS | PRIORIDADE | POLIGONAL
    

def thread_safe(function):
    """Decorator for methods of `Processo` or `ProcessStorage` needing thread safe execution using self->threading.RLock
    Only one Thread can execute that method at time.
    Classes must have self.lock field"""
    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):            
        if not self.lock.acquire(timeout=60.*2):
            raise TimeoutError(f"Wait time-out in function {function.__name__} for process { self.name }")
        result = function(self, *args, **kwargs)            
        self.lock.release() # make it free
        return result 
    return wrapper


process_expire = config['scm']['process_expire']  
"""how long to keep a process on ProcessStorage"""
default_run_state = lambda: copy.deepcopy({ 'run' : 
    { 'basicos': False, 'associados': False, 'ancestry': False, 'polygonal': False } })
""" start state of running parsing processes of process - without deepcopy all mess expected"""

"""
Use `Processo.Get` to avoid creating duplicate Processo's
"""
class Processo:    
    def __init__(self, processostr, wpagentlm, verbose=True):
        """
        Hint: Use `Processo.Get` to avoid creating duplicate Processo's
        """        
        self.name = fmtPname(processostr) # `fmtPname` unique string process number/year
        self.number, self.year = numberyearPname(self.name)
        self.isdisp = True if str(self.number)[0] == 3 else False # if starts 3xx.xxx/xxx disponibilidade  
        if wpagentlm: 
            self._wpage = wPageNtlm(wpagentlm.user, wpagentlm.passwd)
        else: # might be None in case loading from JSON, html etc...
            self._wpage = None 
        self._verbose = verbose
        self.lock = threading.RLock() # re-entrant can be acquired by same thread multiple times
        """`threading.RLock` exists due 'associados' search with multiple threads"""
        self._dados = {} 
        # control to avoid from running again        
        self._dados.update(default_run_state())                           
        """dados parsed and processed """
        # web pages are 'dadosbasicos' and 'poligonal'
        self._pages = { 'basic'   : {'html' : '' },
                        'poligon' : {'html' : '' } 
                      } # 'html' is the request.response.text property : bytes unicode decoded or infered      
        self.birth = datetime.datetime.now() 
        """when this process was requested for the first time"""
        self.onchange = None
        """pointer to function - called when process changes either _pages or _dados
           receives one argument the calling process (self)
        """

    def __getitem__(self, key):
        """get an property from the dados dictionary if exists"""        
        return self._dados[key]           
    
    def __contains__(self, key):
        """check if property exist on self._dados"""
        return key in self._dados
         
    @property
    def associados(self):
        """key : value - processo name : {attributes}
        attributes {} keys 'tipo', 'data' de associação, 'obj' scm.processo.Processo etc..."""        
        return  self._dados['associados']   

    @property
    def pages(self):
        return self._pages

    @thread_safe
    def runTask(self, task=SCM_SEARCH.BASICOS, wpage=None):
        """
        Run task from enum SCM_SEARCH desired data.
        
        * task : enum
            SCM_SEARCH
        """
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

    def _pageRequest(self, name):
        """python requests page and get response unicode str decoded"""
        if not isinstance(self._wpage, wPageNtlm):
            raise Exception('Invalid `wPage` instance!')
        response = requests.pageRequest(name, self.name, self._wpage, False)
        self._pages[name]['html'] = response.text # str unicode page       
        self.__changed()
        return self._pages[name]['html']

    @thread_safe
    def _expandAssociados(self, ass_ignore=''):
        """
        Search and Load on `ProcessStorage` all processes associated with this. 

        * ass_ignore - to ignore in associados list (remove)

        'associados' must be in self.dados dict to build anscestors and sons

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
            return self.associados       

        if not self.associados:
            self['run']['associados'] = True
            return
        
        # local copy for object search -> removing circular reference
        associados = copy.copy(self.associados)      
        if ass_ignore: # equivalent to ass_ignore != ''
            # if its going to be ignored it's because it already exists 
            # being associated with someone 
            # !inconsistency! bug situations identified where A -> B but B !-> A on 
            # each of A and B SCM page -> SO check if ass_ignore exists on self.associados
            if ass_ignore in self.associados:                                
                self.associados[ass_ignore].update({'obj' : ProcessStorage[ass_ignore]})  
                # for outward search ignore this process
                del associados[ass_ignore] # removing circular reference    
            else: # !inconsistency! bug situation identified where A -> B but B !-> A 
                # encontrada em grupamento mineiro 
                # processo em mais de um grupamento mineiro
                # sendo que um dos grupamentos havia sido cancelado mas a associação não removida                    
                inconsistency = ["Process {0} associado to this process but this is NOT associado to {0} on SCM".format(
                    ass_ignore)]
                self._dados['inconsistencies'] = self._dados['inconsistencies'] + inconsistency 
                if self._verbose:
                    print("expandAssociados - inconsistency: ", self.name,
                    ' : ', inconsistency, file=sys.stderr)
        # helper function to search outward only
        def _expandassociados(name, wp, ignore, verbosity):
            """ *ass_ignore : must be set to avoid being waiting for parent-source 
                Also make the search spread outward only"""
            proc = Processo.Get(name, wp, SCM_SEARCH.BASICOS, verbosity)                
            proc._expandAssociados(ignore)
            return proc
        # ignoring empty lists 
        if associados:
            with futures.ThreadPoolExecutor() as executor: # thread number optimal       
                # use a dict to map { process name : future_wrapped_Processo }             
                # due possibility of exception on Thread and to know which process was responsible for that
                #future_processes = {process_name : executor.submit(Processo.Get, process_name, self.wpage, 1, self.verbose) 
                #    for process_name in assprocesses_name}
                future_processes = {process_name : executor.submit(_expandassociados, 
                    process_name, self._wpage, self.name, self._verbose) 
                    for process_name in associados}
                futures.wait(future_processes.values())
                #for future in concurrent.futures.as_completed(future_processes):         
                for process_name, future_process in future_processes.items():               
                    try:
                        # add to process name, property 'obj' process objects                            
                        self.associados[process_name].update({'obj': future_process.result()})
                    except Exception as e:                            
                        print(f"Exception raised while running expandAssociados thread for process {process_name}",
                            file=sys.stderr)     
                        if type(e) is requests.ErrorProcessSCM:
                            # MUST delete process if did not get scm page
                            # since basic data wont be on it, will break ancestry search etc... 
                            del ProcessStorage[process_name]
                            del self.associados[process_name]
                            print(str(e) + f" Removed from associados. Exception ignored!",
                                file=sys.stderr)
                        else:
                            print(traceback.format_exc(), file=sys.stderr, flush=True)     
                            raise # re-raise                  
        if self._verbose:
            print("expandAssociados - finished associados: ", self.name, file=sys.stderr)
            
        self._dados['run']['associados'] = True
        self.__changed()        

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

        self._dados['prioridadec'] = self['prioridade']
        if not self['run']['associados'] and not self.associados:             
            self._dados['run']['ancestry'] = True            
            return self['prioridadec']
        else:
            self._expandAssociados()            
            
        if self.associados: # not dealing with grupamento many parents yet
            graph, root = ancestry.createGraphAssociados(self)
            self._dados['prioridadec'] = ProcessStorage[root]['prioridade']

        self._dados['run']['ancestry'] = True
        return self['prioridadec']
    
    def _dadosBasicosGetIf(self, **kwargs):
        """wrap around `_dadosBasicosGet`to download only if page html
        was not downloaded yet"""
        if not self._pages['basic']['html']:
            self._dadosBasicosGet(**kwargs)
        else: 
            self._dadosBasicosGet(download=False, **kwargs)    

    def _dadosBasicosGet(self, data_tags=None, download=True):
        """dowload the dados basicos scm main html page or 
        use the existing one stored at `self._pages` 
        than parse all data_tags passed storing the resulting in `self.dados`
        return True if succeed on parsing every tag False ortherwise
        """
        if not self['run']['basicos']: # if not done yet
            if data_tags is None: # data tags to fill in 'dados' with
                data_tags = scm_data_tags.copy()
            if download: # download get with python.requests page html response            
                self._pageRequest('basic')        
            if self._pages['basic']['html']:
                if self._verbose:
                    print("dadosBasicosGet - parsing: ", self.name, file=sys.stderr)        
                # using class field directly       
                dados = parseDadosBasicos(self._pages['basic']['html'], 
                    self.name, self._verbose, data_tags)            
                self._dados.update(dados)
                self._dados['run']['basicos'] = True 
                self.__changed()   
                
    def _dadosPoligonalGetIf(self, **kwargs):
        """wrap around `_dadosPoligonalGet`to download only if page html
        was not downloaded yet"""
        if not self._pages['poligon']['html']:
            self._dadosPoligonalGet(**kwargs)
        else: 
            self._dadosPoligonalGet(download=False, **kwargs)         

    def _dadosPoligonalGet(self, download=True):
        """dowload the dados scm poligonal html page or 
        use the existing one stored at `self._pages` 
        than parse all data_tags passed storing the resulting in `self.dados['poligonal']`
        return True           
          * note: not used by self.run!
        """
        if not self['run']['polygonal']: 
            if download: # download get with python.requests page html response  
                self._pageRequest('poligon')
            if self._pages['poligon']['html']:
                if self._verbose:
                    print("dadosPoligonalGet - parsing: ", self.name, file=sys.stderr)   
                dados = parseDadosPoligonal(self._pages['poligon']['html'], self._verbose)
                self._dados.update({'poligon' : dados })                       
                self._dados['run']['polygonal'] = True
                self.__changed()        

    def _dadosBasicosFillMissing(self):
        """try fill dados faltantes pelo processo associado (pai) 1. UF 2. substancias
            need to be reviewed, wrong assumption about parent process   
        """
        if not self['run']['associados']:
            self._expandAssociados()
        if self.associados:
            miss_data_tags = getMissingTagsBasicos(self._dados)        
            father = Processo.Get(self._dados['parents'][0], self._wpage, verbose=self._verbose, run=False)
            father._dadosBasicosGetIf(data_tags=miss_data_tags)
            self._dados.update(father._dados)
            self.__changed()        
            return True
        else:
            return False

    def salvaDadosBasicosHtml(self, html_path, overwrite=False):
        """not thread safe"""
        path = pathlib.Path(html_path).joinpath('scm_basicos_'+self.number+'_'+self.year)
        if not overwrite and path.with_suffix('.html').exists():
            return 
        if not self._pages['basic']['html']:
            self._pageRequest('basic') # get/fill-in self.wpage.response            
        if not hasattr(self._wpage, 'response'):
            saveHtmlPage(str(path), self._pages['basic']['html'])
        else: # save html and page contents - full page
            self._wpage.save(str(path), self._pages['basic']['html']) 

    def salvaDadosPoligonalHtml(self, html_path, overwrite=False):
        """not thread safe"""
        path = pathlib.Path(html_path).joinpath('scm_poligonal_'+self.number+'_'+self.year)
        if not overwrite and path.with_suffix('.html').exists():
            return 
        if not self._pages['poligon']['html']:
            self._pageRequest('poligon') # get/fill-in self.wpage.reponse
        if not hasattr(self._wpage, 'response'): # save only the html
            saveHtmlPage(str(path), self._pages['poligon']['html'])
        else: # save html and page contents - full page
            self._wpage.save(str(path), self._pages['poligon']['html']) 
            
    def toSqliteTuple(self):
        """Create a tuple of this process with complexes fields as json strings
        to save on sqlite database"""
        basicos = self._pages['basic']['html'] 
        basicos = basicos if basicos is not None else ''        
        poligon = self._pages['poligon']['html']
        poligon = poligon if poligon is not None else ''        
        return (  self.name,                                     
                  self.birth.isoformat(),
                  # datetime convertion default function to JSON string                  
                  json.dumps(self._dados, default=datetime_to_json),
                  zlib.compress(basicos.encode('utf-8')),
                  zlib.compress(poligon.encode('utf-8'))
                )    
    
    @staticmethod
    def fromSqliteTuple(tuplesqlite, reparse=False, verbose=False):
        name, birth, _dados, page_basicos, page_poligon = tuplesqlite
        process = Processo(name, None, False)
        process.birth = datetime.datetime.fromisoformat(birth)      
        process._dados = json.loads(_dados, object_hook=json_to_datetime)        
        process._pages['basic']['html'] = zlib.decompress(page_basicos).decode('utf-8')
        process._pages['poligon']['html'] = zlib.decompress(page_poligon).decode('utf-8')
        if 'run' not in process: # backward compatibility
            process._dados.update(default_run_state())   
        if reparse:
            process._dadosBasicosGet(download=False)
            if process._pages['poligon']['html']:            
                if not process._dadosPoligonalGet(download=False) and verbose:
                    print('Some error on poligonal page cant read poligonal table', file=sys.stderr)           
                else:
                    process._dados['run']['polygonal'] = True                  
        return process            
            
    def toJSON(self):
        """
        JSON serialize this process
        mainly saves self.pages['html'] unicoded decoded string 

        Note that everything to be parsed is there. It's safer than 
        saving the parsed, processed data that might change in the future.
        """
        # create a dict of the object and then to json 
        pdict = { 'name'   : self.name,                                     
                  'birth' : self.birth,
                  '_pages' : self._pages,
                  '_dados' : self._dados
                }
        return json.dumps(pdict, default=datetime_to_json)

    def toJSONfile(self, fname=None):
        """
        JSON serialize this process and saves to a file 
        name given by `yearNumber`
        """
        if not fname:
            fname = processUniqueNumber(self.name)+'.JSON'
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(self.toJSON())
        return fname
    
    def __changed(self):
        """something changed so birth datetime changes"""
        self.birth = datetime.datetime.now() 
        if self.onchange is not None:
            self.onchange(self)

    @staticmethod
    def fromJSON(strJSON, verbose=False, reparse=False):
        """Create a `Processo` from a JSON str create with `toJSON` method.
           only 'dados basicos' are parsed associados, ancestry need to be run
           
           * reparse : to parse data from html overwritting existing `._dados`
        """
        jsondict = json.loads(strJSON, object_hook=json_to_datetime)            
        process = Processo(jsondict['name'], None, False)
        process.birth = jsondict['birth']        
        process._dados = jsondict['_dados']        
        process._pages = jsondict['_pages']                        
        if 'run' not in process: # backward compatibility
            process._dados.update(default_run_state())  
        if reparse:
            process._dadosBasicosGet(download=False)
            process._dados['run']['basicos'] = True                  
            if process._pages['poligon']['html']:            
                if not process._dadosPoligonalGet(download=False) and verbose:
                    print('Some error on poligonal page cant read poligonal table', file=sys.stderr)           
                process._dados['run']['polygonal'] = True        
        return process

    @staticmethod
    def fromJSONfile(fname, verbose=False):
        """Create a `Processo` from a JSON str create with `toJSON` method saved on file fname.
        """
        pJSON = ''
        with open(fname, 'r', encoding='utf-8') as f:
            pJSON = f.read()
        return Processo.fromJSON(pJSON, verbose)

    @staticmethod
    def getNUP(processostr, wpagentlm):
        response = requests.pageRequest('basic', processostr, wpagentlm, True)
        return parseNUP(response.content)

    @staticmethod
    def fromStrHtml(processostr, html_basicos, html_poligonal=None, verbose=True):
        """Create a `Processo` from a html str of basicos and poligonal (if available)
            - main_html : str (optional)
                directly from a request.response.content string previouly saved  
                `processostr` must be set
        """
        processo = Processo(processostr, None, verbose=verbose)
        processo._pages['basic']['html'] = html_basicos
        processo._pages['poligon']['html'] = html_poligonal
        processo._dadosBasicosGet(download=False) 
        if html_poligonal:            
            if not processo._dadosPoligonalGet(download=False) and verbose:
                print('Some error on poligonal page cant read poligonal table', file=sys.stderr)
        return processo

    @staticmethod
    def fromHtml(path='.', processostr=None, verbose=True):
        """Try create a `Processo` from a html's of basicos and poligonal (optional)       
        """
        path = pathlib.Path(path)        
        path_main_html = list(path.glob('*basicos*.html')) # html file on folder
        path_poligon_html = list(path.glob('*poligonal*.html')) # html file on folder
        if not path_main_html:
            raise FileNotFoundError(".fromHtml main scm html file not found!")
        if not processostr: # get process str name by file name
            processostr= fmtPname(str(path_main_html[0]))
        poligon_html = None
        main_html = try_read_html(path_main_html[0])
        if path_poligon_html: # if present
            path_poligon_html = try_read_html(path_poligon_html[0])
        elif verbose:            
            print('Didnt find a poligonal page html saved', file=sys.stderr)                
        return Processo.fromStrHtml(processostr, main_html, poligon_html, verbose=verbose)

    @staticmethod
    def Get(processostr, wpagentlm, task=SCM_SEARCH.ALL, verbose=True, run=True):
        """
        Create a new or get a Processo from ProcessStorage if it has not expired. (config['scm']['process_expire'])

        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        processo = None                
        processostr = fmtPname(processostr)        
        if ProcessStorage.get(processostr) is not None:
            processo = ProcessStorage[processostr] #  storage doesn't keep wpage
            processo._wpage = wPageNtlm(wpagentlm.user, wpagentlm.passwd)
            if processo.birth + process_expire < datetime.datetime.now():         
                if verbose:       
                    print("Processo placing on storage ", processostr, file=sys.stderr)
                processo = Processo(processostr, wpagentlm,  verbose)  # store newer guy             
                ProcessStorage[processostr] = processo
            else:
                if verbose: 
                    print("Processo getting from storage ", processostr, file=sys.stderr)            
        else:
            if verbose: 
                print("Processo placing on storage ", processostr, file=sys.stderr)
            processo = Processo(processostr, wpagentlm,  verbose)  # store new guy
            ProcessStorage[processostr] = processo            
        if run: # wether run the task, dont run when loading from file/str
            processo.runTask(task)
        return processo



# create the sqlite database for processes
# with sqlite3.connect('process_storage.db') as conn: # already commits and closes
#    sql = f"""CREATE TABLE STORAGE(
#       NAME CHAR(12) NOT NULL,   
#       BIRTH TIMESTAMP,
#       DADOS TEXT,
#       PAGE_BASIC BLOB, 
#       PAGE_POLIGON BLOB,
#       UNIQUE(NAME) ON CONFLICT REPLACE
#    )"""
#    conn.execute(sql)

import sqlite3
    

# Inherits from dict since it is:
# 1. the recommended global approach 
# 2. thread safe for 'simple set/get'
class ProcessFactoryStorageClass(dict):
    """Container of processes to avoid 
    1. connecting/open page of SCM again
    2. parsing all information again    
    * If it was already parsed save it in here { key : value }
    * key : unique `fmtPname` process string
    * value : `scm.Processo` object
    """    
    def __init__(self, save_on_set=True, debug=False): 
        """
        * save_on_set: save on database on set 
        """        
        super().__init__()      
        self.save_on_set = save_on_set        
        self.debug = debug
        with sqlite3.connect(config['scm']['process_storage_file']+'.db') as conn: # context manager already commits and closes connection
            self.ondb = conn.execute("SELECT name FROM storage").fetchall()             

       
    def __insert_to_sqlite(self, key):
        with sqlite3.connect(config['scm']['process_storage_file']+'.db') as conn: # context manager already commits and closes connection
            cursor = conn.cursor()    
            # cursor.execute("SELECT * FROM storage WHERE name = ?", key)
            # process_row = cursor.fetchone()
            # if process_row:
            cursor.execute("INSERT INTO storage VALUES (?,?,?,?,?)", self[key].toSqliteTuple())   
            if self.debug:
                print(f"Just inserted or modified {conn.total_changes} rows on database", file=sys.stderr)
            
    def __select_from_sqlite(self, key):
        with sqlite3.connect(config['scm']['process_storage_file']+'.db') as conn:
            cursor = conn.cursor()    
            cursor.execute("SELECT * FROM storage WHERE name='{:}'".format(key))
            process_row = cursor.fetchone()
            if process_row:
                return Processo.fromSqliteTuple(process_row)
            return None
                   
    def __setitem__(self, key, value):        
        super().__setitem__(key, value)     
        if not value.onchange: # on change callback of process
            value.onchange = ProcessStorage.__process_changed
        if self.save_on_set:
            threading.Thread(target=self.__insert_to_sqlite, args=(key,)).start()        
    
    def get(self, key):
        try:
            result = self[key]
        except KeyError:
            return None 
        return result    
    
    # def __contains__(self, __o: object) -> bool:
    #     return super().__contains__(__o)         
    
    @staticmethod
    def __process_changed(process):
        """update process on database"""
        ProcessStorage[process.name] = process
        
    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)   
        process = self.__select_from_sqlite(key)        
        if not process:
            raise KeyError()
        self[key] = process # store here for faster access        
        # add event listener when changed will get updated on database 
        process.onchange = ProcessStorage.__process_changed
        return process
        
    def loadAll(self, verbose=False):        
        """Load all processes from sqlite database on self"""
        fname = config['scm']['process_storage_file'] + '.db'          
        if not os.path.exists(fname):
            print(f"Process Storage database file not found {fname}", file=sys.stderr)
            return 
        with sqlite3.connect(config['scm']['process_storage_file']+'.db') as conn:
            start = time.time()
            dbdict = {}
            for row in conn.execute("SELECT * FROM storage").fetchall():
                process = Processo.fromSqliteTuple(row)
                process.onchange = ProcessStorage.__process_changed
                dbdict.update({ row[0] : process })
            self.update(dbdict)            
            if verbose:
                print(f"Loading and creating {len(self)} processes from database took {time.time()-start:.2f} seconds")
        #iterator = processes if not verbose else progressbar(processes, "Loading Processes: ")        
        #self.update({process.name : process for process in map(Processo.fromJSON, iterator)})  
    
    def runTask(self, wp, *args, **kwargs):
        """run `runTask` on every process on storage    

        * wp : wPageNtlm
            must be provided   

        Any aditional args or keywork args for `runTask` can be passed.  

        Like dados=Processo.SCM_SEARCH.BASICOS or any tuple (function, args) pair
        """
        for pname in progressbar(ProcessStorage):
            #must be one independent requests.Session for each process otherwise mess            
            ProcessStorage[pname]._wpage = wPageNtlm(wp.user, wp.passwd, ssl=True)             
            ProcessStorage[pname].runTask(*args, **kwargs)
    
    def fromHtmls(self, paths, verbose=False):        
        for process_path in tqdm.tqdm(paths):
            try:   
                processo = Processo.fromHtml(process_path, verbose=False)
                processo.onchange = ProcessStorage.__process_changed
                self.update({processo.name : processo})
            except FileNotFoundError:
                if verbose:
                    print(f"Did not find process html at {process_path}", file=sys.stderr)   
        
            
ProcessStorage = ProcessFactoryStorageClass()
threading.Thread(target=ProcessStorage.loadAll, args=(True,)).start() # load processes saved on start      
"""Container and Factory of processes to avoid 
1. connecting/open page of SCM again
2. parsing all information again    
* If it was already parsed save it in here { key : value }
* key : unique `fmtPname` process string
* value : `scm.Processo` object
"""