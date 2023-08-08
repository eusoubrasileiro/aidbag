import sys 
import datetime
from functools import wraps
from threading import local
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import object_session
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
        """
        Thread-unique session to use as a context manager using the scoped_session
        Always return the same session for the same thread. 
        with ProcessManager._session() as session:
            # do something ...
        automatically closes the session making objects not bound to a session
        """
        return self.__session
    
    @property
    def session(self):
        """
        Thread-unique session uses scoped_session but don't close it.
        Always return the same session for the same thread. 
        """
        return self._session()

    def __delitem__(self, key : str):        
        self.session.delete(self[key].db)
        self.session.commit()
        super().__delitem__(key)
    
    def __getitem__(self, key : str) -> Processo:
        """
        Get process from local dictionary first or Database second
        In case its session or thread was closed add it to the current new session.
        Delete the previous in case is not closed yet.
        (That's the case for a web application : each request is a new thread)
        """
        key = fmtPname(key)    
        if key in self:
            processo = super().__getitem__(key)   
            # in the case the session or thread that create it was closed add it back to a new session
            # this will cause an exception if the previous session was not closed!
            # Flask request thread (request_context) sometimes is closed and reopened (during the same request)
            # (which can happen due to the way threads are managed), the session you created is lost 
            # so we delete it and add a new one - more bellow about that
            session_db = object_session(processo.db)
            if session_db is not self.session:    
                if session_db is not None: 
                    session_db.close()            
                self.session.add(processo.db)
            return processo
        else:
            processodb = self.session.query(Processodb).filter_by(name=key).first()
            if processodb is not None:
                processo = Processo(processodb.name, processodb=processodb, manager=self)   
                self.update({processo.name : processo})
                return processo    
            return None

    def __setitem__(self, key, process : Processo):                           
        self.session.add(process.db)            
        self.session.commit()
        super().__setitem__(key, process)

    
    def runTask(self, wp, *args, **kwargs):
        """run `runTask` on every process on database    

        * wp : wPageNtlm
            must be provided   

        Any aditional args or keywork args for `runTask` can be passed. 
        Like dados=Processo.SCM_SEARCH.BASICOS or any tuple (function, args) pair
        """
        for processodb in progressbar(self.session.query(Processodb).all()):
            processo = Processo(processodb.name, processodb=processodb, 
                wpagentlm=wPageNtlm(wp.user, wp.passwd, ssl=True))
            #must be one independent requests.Session for each process otherwise mess                        
            processo.runTask(*args, **kwargs)
        self.session.commit()
   
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
"""Container and Factory of Processos's 
Stores web-scrapped and parsed data on local dictionary and Database
* key : unique `fmtPname` process string
* value : `scm.Processo` object
Not using any other layer of cache making sqlite3 queries everytime.
Everytime means: each object property access/modification is a new query by SQL Alchemy ORM standard. 
Default behaviour is the scoped_session is never closed in each-thread until it closes itself. 
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
