import sys 
import datetime
from threading import local
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    scoped_session,
    sessionmaker
    )

from ..config import config
from .processo import (
    Processo, 
    Processodb,
    SCM_SEARCH
    )
from .util import (
    fmtPname
    )
from ....web.htmlscrap import wPageNtlm
from ....web.io import try_read_html


class ProcessManagerClass(dict):
    """Container and Factory of Processo objects 
    uses SQLAlchemy sqlite3 for storage 
    Avoids:
        1. connecting/open page of SCM again
        2. parsing all information again    
    * If it was already parsed save in the sqlite3 database
    * key : unique `fmtPname` process string
    * value : `scm.Processo` object
    """    
    def __init__(self, debug=False): 
        """
        * save_on_set: save on database on set 
        """        
        super().__init__()      
        self._engine = create_engine(f"sqlite:///{config['scm']['process_storage_file']+'.db'}")                    
        self.__session = scoped_session(sessionmaker(bind=self._engine))
        self.debug = debug   
  
    @property
    def _session(self):
        """thread-unique session due use of scoped_session"""
        return self.__session()
        
    def __delitem__(self, key : str):        
        self._session.delete(self[key].db)
        self._session.commit()
        super().__delitem__(key)
    
    def __getitem__(self, key : str) -> Processo:
        key = fmtPname(key)    
        if key in self:
            return super().__getitem__(key)   
        else:
            processodb = self._session.query(Processodb).filter_by(name=key).first()
            if processodb is not None:
                processo = Processo(processodb.name, processodb=processodb, manager=self)   
                self.update({processo.name : processo})
                return processo    
            return None

    def __setitem__(self, key, process : Processo):                           
        self._session.add(process.db)            
        self._session.commit()
        super().__setitem__(key, process)

    
    def runTask(self, wp, *args, **kwargs):
        """run `runTask` on every process on database    

        * wp : wPageNtlm
            must be provided   

        Any aditional args or keywork args for `runTask` can be passed. 
        Like dados=Processo.SCM_SEARCH.BASICOS or any tuple (function, args) pair
        """
        for processodb in progressbar(self._session.query(Processodb).all()):
            processo = Processo(processodb.name, processodb=processodb, 
                wpagentlm=wPageNtlm(wp.user, wp.passwd, ssl=True))
            #must be one independent requests.Session for each process otherwise mess                        
            processo.runTask(*args, **kwargs)
        self._session.commit()
   
    def GetorCreate(self, processostr, wpagentlm, task=SCM_SEARCH.ALL, verbose=False, run=True):
        """
        Create a new or get a Processo if it has not expired. (config['scm']['process_expire'])

        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        processostr = fmtPname(processostr)        
        # try from database or self
        processo = self[processostr]                        
        if processo is not None:
            processo._verbose = verbose
            processo._wpage = wPageNtlm(wpagentlm.user, wpagentlm.passwd)
            if processo.modified + config['scm']['process_expire'] < datetime.datetime.now():         
                if verbose:       
                    print("Processo placing on storage ", processostr, file=sys.stderr)
                del self[processostr] # delete here and on database before adding a new one               
                processo = Processo(processostr, wpagentlm, manager=self, verbose=verbose) # replace with a newer guy  
                self[processostr] = processo
            else:
                if verbose: 
                    print("Processo getting from storage ", processostr, file=sys.stderr)            
        else:
            if verbose: 
                print("Processo placing on storage ", processostr, file=sys.stderr)
            processo = Processo(processostr, wpagentlm, manager=self, verbose=verbose)  # store new guy
            self[processostr] = processo            
        if run: # wether run the task, dont run when loading from file/str
            processo.runTask(task)
        return processo

    # def fromHtmls(self, paths, verbose=False):        
    #     for process_path in tqdm.tqdm(paths):
    #         try:   
    #             processo = Processo.fromHtml(process_path, verbose=False)
    #             processo.onchange = ProcessManager.__process_changed
    #             self.update({processo.name : processo})
    #         except FileNotFoundError:
    #             if verbose:
    #                 print(f"Did not find process html at {process_path}", file=sys.stderr)           
    
    def fromStrHtml(processostr, html_basicos, html_poligonal=None, verbose=True):
        """Create a `Processo` from a html str of basicos and poligonal (if available)
            - main_html : str (optional)
                directly from a request.response.content string previouly saved  
                `processostr` must be set
        """
        processo = Processo(processostr, None, manager=self, verbose=verbose)
        processo.db.basic_html = html_basicos
        processo.db.poligon_html = html_poligonal
        processo._dadosBasicosGet(download=False) 
        if html_poligonal:            
            if not processo._dadosPoligonalGet(download=False) and verbose:
                print('Some error on poligonal page cant read poligonal table', file=sys.stderr)            
        self[processo.name] = processo # saves it in here
        return processo

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


ProcessManager = ProcessManagerClass()   
"""Container and Factory of processes to avoid 
1. connecting/open page of SCM again
2. parsing all information again    
* If it was already parsed save it in here { key : value }
* key : unique `fmtPname` process string
* value : `scm.Processo` object
Not using any other layer of cache making sqlite3 queries everytime 
"""