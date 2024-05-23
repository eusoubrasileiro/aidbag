import sys 
import datetime
import threading
from functools import wraps
from threading import local
from contextlib import contextmanager
from sqlalchemy import (
    create_engine,
    text,
    func
    )
from sqlalchemy.orm import (
    Session,
    scoped_session,    
    sessionmaker,
    object_session
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
        super().__init__()      
        self._engine = create_engine(f"sqlite:///{config['scm']['process_storage_file']+'.db'}")                    
        self.__session = scoped_session(sessionmaker(bind=self._engine))
        self.debug = debug           
        self.lock = threading.RLock()
    
    @property
    def session(self):
        """
        Thread-unique session from scoped_session . 
        `scoped_session` returns the same session for the same thread and 
        closes it in case the thread ends somehow. 
        Usage:
        with ProcessManager.session() as session:
            session.refresh(processo.db)
            # do something ...
            session.commit() # or not depending on what you do
        That automatically closes the session making objects not bound to a 
        session. But `updatedb` reataches the object to a 
        session no matter what happened before
        """        
        return self.__session

    def __delitem__(self, key : str):    
        """
        this is called when del ProcessManager[key] 
        be careful with this 
        """
        if self[key]:                
            p = self[key]                                    
            super().__delitem__(key)
            p.delete()
    
    def __getitem__(self, key : str) -> Processo:
        """
        Get process from local dictionary first or Database second. 
        """
        with self.lock:
            key = fmtPname(key)    
            if key in self:
                processo = super().__getitem__(key)   
                return processo
            else:
                with self.session() as session:
                    processodb = session.query(Processodb).filter_by(name=key).first()                                        
                if processodb is not None:
                    processo = Processo(key, processodb=processodb, manager=self)                           
                    self.update({key : processo})
                    return processo    
                return None

    def _getwithFilter(self, filter_condition):
        """
        Get `.all()` processos querying with sqlalchemy filter 
        example:
        getting processes with 'clayers' key in 'dados->iestudo'
        ProcessManager.getwithFilter( text("dados->'estudo ? 'clayers'"))
        """
        with self.lock:             
            with self.session() as session:
                processes = self.session.query(Processodb).filter(filter_condition).all()   
            list_processes = []
            for process in processes:
                processo = Processo(process.name, processodb=process, manager=self) # replace with a newer guy  
                list_processes.append(processo)
            return list_processes    

    # def _getAll(self):
    #     """
    #     Get all processes from Database no dictionary interaction - 
    #       for database interactions direct from python no SQL needed
    #     """
    #     with self.lock:
    #         with self.session() as session:
    #             processes = session.query(Processodb).all()
    #         list_processes = []
    #         for process in processes:
    #             processo = Processo(process.name, processodb=process, manager=self) 
    #             list_processes.append(processo)
    #         return list_processes 
   
    def runTask(self, wp, *args, **kwargs):
        """run `runTask` on every process on database    

        * wp : wPageNtlm
            must be provided   

        Any aditional args or keywork args for `runTask` can be passed. 
        Like dados=Processo.SCM_SEARCH.BASICOS or any tuple (function, args) pair
        """    
        for processodb in progressbar(session.query(Processodb).all()):
            processo = Processo(processodb.name, processodb=processodb, 
                wpagentlm=wPageNtlm(wp.user, wp.passwd, ssl=True))
            #must be one independent requests.Session for each process otherwise mess                        
            processo.runTask(*args, **kwargs)            

    def GetorCreate(self, processostr, wpagentlm, task=SCM_SEARCH.ALL, verbose=False, run=True):
        """
        Create a new or get a Processo if it has not expired. 
        (config['scm']['process_expire'])

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
        processo.db.polygon_html = html_poligonal
        processo._dadosScmGet('basic', download=False) 
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
        path_polygon_html = list(path.glob('*poligonal*.html')) # html file on folder
        if not path_main_html:
            raise FileNotFoundError(".fromHtml main scm html file not found!")
        if not processostr: # get process str name by file name
            processostr= fmtPname(str(path_main_html[0]))
        polygon_html = None
        main_html = try_read_html(path_main_html[0])
        if path_polygon_html: # if present
            path_polygon_html = try_read_html(path_polygon_html[0])
        elif verbose:            
            print('Didnt find a poligonal page html saved', file=sys.stderr)                
        return Processo.fromStrHtml(processostr, main_html, polygon_html, verbose=verbose)


ProcessManager = ProcessManagerClass()   
"""Container and Factory of Processos's 
Stores web-scrapped and parsed data on local dictionary and Database
* key : unique `fmtPname` process string
* value : `scm.Processo` object
Not using any other layer of cache making sqlite3 queries everytime.
Everytime means: each object property access/modification is a new query by SQL Alchemy ORM standard. 
"""




# More About the Request Context - Flask's Request Context
# 

# In Flask, the request context is a critical concept that allows you to access
# various objects that are related to the current request, such as the request
# and response objects, the current application, and more. Flask uses a context
# stack to manage these objects in a way that is safe for concurrent requests.
#
# When a request is received by the Flask application, Flask pushes a new
# context onto the context stack. This context is associated with the current
# request and contains all the information and objects needed to handle that
# specific request. Once the request is processed, the context is popped from
# the stack, and any resources associated with that context are cleaned up.
#
# The request context is managed using Python's thread-local storage, which
# ensures that each thread (request) has its own isolated context.

# Threading and the Request Context:
# In a typical WSGI server setup, such as with Flask, each incoming request is
# handled by a separate thread. This is a common practice to achieve concurrency
# and responsiveness in web applications. However, this threading model can
# sometimes lead to unexpected behavior when it comes to managing sessions,
# especially when you're manually managing sessions.
#
# For example, consider a scenario where you manually create a session at the
# beginning of a request and then try to use that session later in the request.
# If the request context is closed and reopened (which can happen due to the way
# threads are managed), the session you created initially might no longer be
# valid, leading to issues.

# Managing Your Own Sessions:
# When you're manually managing sessions in Flask, you need to be aware of the
# request context and threading behavior. Here are some guidelines:

# Create Sessions per Request: Create a new session at the beginning of each
# request, and ensure that you're using the same session throughout that
# request. This helps ensure that the session is properly scoped to the current
# request context.

# Explicitly Close Sessions: Explicitly close the session at the end of the
# request. This helps release resources associated with the session and ensures
# that you're not holding onto resources longer than necessary.

# Avoid Sharing Sessions: Do not share sessions between different requests or
# threads. Each request should have its own isolated session to avoid conflicts
# and unexpected behavior.

# Thread-Local Storage: Be aware that the request context and session management
# use thread-local storage. If you're manually managing sessions, you need to be
# mindful of how sessions are accessed and closed within the current thread's
# context.

# Exception Handling: Handle exceptions properly to ensure that sessions are
# closed even in cases of errors.
