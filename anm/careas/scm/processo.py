import sys, os, copy
import datetime, zlib
import glob, json, traceback
import concurrent.futures
import threading
import enum
import tempfile
import functools

from ....general import progressbar 
from ....web.htmlscrap import wPageNtlm
from . import requests 
from . import ancestry

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
        # control to prevent from running again
        self._dadosbasicos_run = False
        self._associados_run = False
        self._ancestry_run = False
        self._dadospoly_run = False
        self.lock = threading.RLock() # re-entrant can be acquired by same thread multiple times
        """`threading.RLock` exists due 'associados' search with multiple threads"""
        self._dados = {} 
        """dados parsed and processed """
        # web pages are 'dadosbasicos' and 'poligonal'
        # data_raw must be json serializable
        self._pages = { 'dadosbasicos'   : {'html' : None, 'data_raw' : {} },
                        'poligonal'      : {'html' : None, 'data_raw' : {} } 
                      } # 'html' is the request.response.text property : bytes unicode decoded or infered       

    def __getitem__(self, key):
        """get an property from the dados dictionary `dadosbasicos_run` must have run"""        
        return self._dados[key]        

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
            if SCM_SEARCH.BASICOS in task and not self._dadosbasicos_run:
                self._dadosBasicosGet()
            elif SCM_SEARCH.ASSOCIADOS in task and not self._associados_run:
                self._expandAssociados()
            elif SCM_SEARCH.PRIORIDADE in task and not self._ancestry_run:
                self._ancestry()
            elif SCM_SEARCH.POLIGONAL in task and not self._dadospoly_run:
                self._dadosPoligonalGet()

    def _pageRequest(self, name):
        """python requests page and get response unicode str decoded"""
        if not isinstance(self._wpage, wPageNtlm):
            raise Exception('Invalid `wPage` instance!')
        if not self._pages[name]['html']:
            response = requests.pageRequest(name, self.name, self._wpage, False)
            self._pages[name]['html'] = response.text # str unicode page             
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
        if not self._dadosbasicos_run:
            self._dadosBasicosGet()

        if self._associados_run: 
            return self.associados       

        if not self.associados:
            self._associados_run = True
            return
        
        if self._verbose:
            print("expandAssociados - getting associados: ", self.name,
            ' - ass_ignore: ', ass_ignore, file=sys.stderr)
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
            with concurrent.futures.ThreadPoolExecutor() as executor: # thread number optimal       
                # use a dict to map { process name : future_wrapped_Processo }             
                # due possibility of exception on Thread and to know which process was responsible for that
                #future_processes = {process_name : executor.submit(Processo.Get, process_name, self.wpage, 1, self.verbose) 
                #    for process_name in assprocesses_name}
                future_processes = {process_name : executor.submit(_expandassociados, 
                    process_name, self._wpage, self.name, self._verbose) 
                    for process_name in associados}
                concurrent.futures.wait(future_processes.values())
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
            
        self._associados_run = True        

    def _ancestry(self):
        """
        Build graph of all associados.
        Get root node or older parent.               
        """
        if self._ancestry_run:
            return self['prioridadec']

        if not self._dadosbasicos_run:
            self._dadosBasicosGet()

        if self._associados_run: 
            return self.associados       
        
        if not self._associados_run and self.associados:
            self._expandAssociados()

        if self._verbose:
            print("ancestrySearch - building graph: ", self.name, file=sys.stderr)
        
        self._dados['prioridadec'] = self['prioridade']
        if self.associados: # not dealing with grupamento many parents yet
            graph, root = ancestry.createGraphAssociados(self)
            self._dados['prioridadec'] = ProcessStorage[root]['prioridade']

        self._ancestry_run = True
        return self['prioridadec']

    def _dadosBasicosGet(self, data_tags=None, download=True):
        """dowload the dados basicos scm main html page or 
        use the existing one stored at `self.html_dbasicospage` 
        than parse all data_tags passed storing the resulting in `self.dados`
        return True if succeed on parsing every tag False ortherwise
        """
        if not self._dadosbasicos_run: # if not done yet
            if data_tags is None: # data tags to fill in 'dados' with
                data_tags = scm_data_tags.copy()
            if download: # download get with python.requests page html response            
                self._pageRequest('dadosbasicos')        
            if self._verbose:
                print("dadosBasicosGet - parsing: ", self.name, file=sys.stderr)        
            # using class field directly       
            dados, dados_raw = parseDadosBasicos(self._pages['dadosbasicos']['html'], 
                self.name, self._verbose, data_tags)
            self._pages['dadosbasicos']['data_raw'] = dados_raw
            self._dados.update(dados)
            self._dadosbasicos_run = True 

    def _dadosPoligonalGet(self, download=True):
        """dowload the dados scm poligonal html page or 
        use the existing one stored at `self.html_poligonpage` 
        than parse all data_tags passed storing the resulting in `self.polydata`
        return True           
          * note: not used by self.run!
        """
        if not self._dadospoly_run: 
            if download: # download get with python.requests page html response  
                self._pageRequest('poligonal')
            # dont need to retrieve anything
            if self._verbose:
                print("dadosPoligonalGet - parsing: ", self.name, file=sys.stderr)   
            dados = parseDadosPoligonal(self._pages['poligonal']['html'])
            self._dados.update({'poligonal' : dados })
            self._pages['poligonal']['data_raw'] = dados             
            self._dadospoly_run = True

    def _dadosBasicosFillMissing(self):
        """try fill dados faltantes pelo processo associado (pai) 1. UF 2. substancias
            need to be reviewed, wrong assumption about parent process   
        """
        if not self._associados_run:
            self._expandAssociados()
        if self.associados:
            miss_data_tags = getMissingTagsBasicos(self._dados)        
            father = Processo.Get(self._dados['parents'][0], self._wpage, verbose=self._verbose, run=False)
            father._dadosBasicosGet(miss_data_tags)
            self._dados.update(father._dados)
            return True
        else:
            return False

    def salvaDadosBasicosHtml(self, html_path):
        """not thread safe"""
        if not self._pages['dadosbasicos']['html']:
            self._pageRequest('dadosbasicos') # get/fill-in self.wpage.reponse
        self._wpage.save(os.path.join(html_path, 'scm_basicos_'+self.number+'_'+self.year),
                        self._pages['dadosbasicos']['html']) 

    def salvaDadosPoligonalHtml(self, html_path):
        """not thread safe"""
        if not self._pages['poligonal']['html']:
            self._pageRequest('poligonal') # get/fill-in self.wpage.reponse
        self._wpage.save(os.path.join(html_path, 'scm_poligonal_'+self.number+'_'+self.year),
                        self._pages['poligonal']['html']) 

    def toJSON(self):
        """
        JSON serialize this process
        mainly saves self.pages['html'] unicoded decoded string 

        Note that everything to be parsed is there. It's safer than 
        saving the parsed, processed data that might change in the future.
        """
        # create a dict of the object and then to json 
        # 'data_raw' must be json serializable 
        pdict = { 'name'   : self.name,                  
                  '_pages' : self._pages }
        return json.dumps(pdict)

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

    @staticmethod
    def fromJSON(strJSON, verbose=True):
        """Create a `Processo` from a JSON str create with `toJSON` method.
           only 'dados basicos' are parsed associados, ancestry need to be run
        """
        jsondict = json.loads(strJSON)
        process = Processo.Get(jsondict['name'], None, SCM_SEARCH.NONE, False, False)
        for k in jsondict['_pages']:
            process._pages.update({k : jsondict['_pages'][k]})        
        process._dadosBasicosGet(download=False)
        if process._pages['poligonal']['html']:
             if not process._dadosPoligonalGet(download=False):
                if verbose:
                    print('Some error on poligonal page cant read poligonal table', file=sys.stderr)           
        return process

    @staticmethod
    def fromJSONfile(fname, verbose=False):
        """Create a `Processo` from a JSON str create with `toJSON` method saved on file fname.
        """
        pJSON = ''
        with open(fname, 'r', encoding='utf-8') as f:
            pJSON = f.read()
        Processo.fromJSON(pJSON, verbose)

    @staticmethod
    def getNUP(processostr, wpagentlm):
        response = requests.pageRequest('dadosbasicos', processostr, wpagentlm, True)
        return parseNUP(response.content)

    @staticmethod
    def fromStrHtml(processostr, html_basicos, html_poligonal=None, verbose=True):
        """Create a `Processo` from a html str of basicos and poligonal (if available)
            - main_html : str (optional)
                directly from a request.response.content string previouly saved  
                `processostr` must be set
        """
        processo = Processo.Get(processostr, None, verbose=verbose, task=SCM_SEARCH.NONE, run=False)
        processo._pages['dadosbasicos']['html'] = html_basicos
        processo._dadosBasicosGet(download=False) 
        if html_poligonal:
            processo._pages['poligonal']['html'] = html_poligonal
            if not processo._dadosPoligonalGet(download=False):
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

        with open(path_main_html, 'r', encoding='utf-8') as f: # read html scm
            main_html = f.read()

        if path_poligon_html: # if present
            path_poligon_html = path_poligon_html[0]
            with open(path_poligon_html, 'r', encoding='utf-8') as f: # read html scm
                poligon_html = f.read()
        elif verbose:            
            print('Didnt find a poligonal page html saved', file=sys.stderr)
        os.chdir(curdir) # go back
        
        return Processo.fromStrHtml(processostr, main_html, poligon_html, verbose=verbose)

    @staticmethod
    def Get(processostr, wpagentlm, task=SCM_SEARCH.ALL, verbose=True, run=True):
        """
        Create a new or get a Processo from ProcessStorage

        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        processo = None
        processostr = fmtPname(processostr)
        if processostr in ProcessStorage:
            if verbose: # only for pretty printing
                print("Processo __new___ getting from storage ", processostr, file=sys.stderr)
            processo = ProcessStorage[processostr]
        else:
            if verbose: # only for pretty printing
                print("Processo __new___ placing on storage ", processostr, file=sys.stderr)
        processo = Processo(processostr, wpagentlm,  verbose)
        ProcessStorage[processostr] = processo   # store this new guy 
        if run: # wether run the task, dont run when loading from file/str
            processo.runTask(task)
        return processo


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
    def __init__(self, store_at_every=5): 
        """
        * store_at_every: save on disk at every 
        """
        super().__init__()  
        self.store_at_every = store_at_every
        self.tempdir = tempfile.gettempdir()
    
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

    def toJSON(self):
        """Create dict of processes JSON serialized
        after `.toJSON` for each process stored"""
        processes = {}
        for k, v in self.items():
            processes.update({k : v.toJSON()})
        return json.dumps(processes)

    def toJSONfile(self, fname=None, zip=True):
        """Create dict of processes JSON serialized 
        than compress dict with `zlib`        
        """
        JSONstr = self.toJSON().encode('utf-8')
        if not fname:            
            ext = 'JSON.zip' if zip else '.JSON'
            fname =  'ProcessStored'+datetime.datetime.now().strftime('_%Y_%m_%d_h%Hm%M_') + ext
        if zip:
            JSONstr = zlib.compress(JSONstr)            
        with open(fname, 'wb') as f:
            f.write(JSONstr)
        return fname

    @staticmethod
    def fromJSONfile(fname=None, zip=True, verbose=False):
        """Create a `ProcessStorageClass` from a JSON str create with `toJSONfile` method saved on file fname.
        * zip : 
            default assumed to be zipped
        """
        if not fname: # use default storage file first found
            fname = glob.glob('ProcessStored_*_JSON.zip')[0]

        processesJSON = ''
        with open(fname, 'rb') as f:
            processesJSON = f.read()
        if zip:
            processesJSON = zlib.decompress(processesJSON)
        else:
            processesJSON = processesJSON.decode('utf-8')
        processes = json.loads(processesJSON) # recreat dict { process-name : JSON-str } 
        iterator = processes if not verbose else progressbar(processes, "Loading: ")
        for keys in iterator:
            Processo.fromJSON(processes[keys], verbose)

 


# # from many saved JSON processes locally
# import glob 

# for k, v in scm.ProcessStorage.items():
#     v.toJSONfile()
# jsonprocesses = glob.glob("*.JSON")
# for jsonprocess in jsonprocesses:
#     scm.Processo.fromJSONfile(jsonprocess, True)        

# running runTask on all process on storage
# import tqdm 

# for k in scm.ProcessStorage:
#     if scm.ProcessStorage[k].associados:
#         print(scm.ProcessStorage[k].associados)

ProcessStorage = ProcessFactoryStorageClass()
"""Container and Factory of processes to avoid 
1. connecting/open page of SCM again
2. parsing all information again    
* If it was already parsed save it in here { key : value }
* key : unique `fmtPname` process string
* value : `scm.Processo` object
"""