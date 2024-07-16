from aidbag.web.json import json_to_path, path_to_json

from ..config import config
from ..util import processPath
from ..scm import (
    pud, 
    NotProcessNumber, 
    ProcessManager
)

import json
import pathlib
import os
import shutil 

# Current Processes being worked on 
ProcessPathStorage = {} 
"""
Stores paths for current process being worked on style { 'xxx.xxx/xxxx' : pathlib.Path() }.  
Uses `config['processos_path']` to search for process work folders.
"""




def currentProcessGet(path=None, sort='name', clear=True):
    """
    Return dict of processes paths currently on work folder.
    Update `ProcessPathStorage` dict with process names and paths.
        
    * sort:
        to sort glob result by 
        'time' modification time recent modifications first
        'name' sort by name 
        
    * return: list [ pathlib.Path's ...]
        current process folders working on from default careas working env.
        
    * clear : default True
        clear `ProcessPathStorage` before updating (ignore json file)
        
    Hint: 
        * use .keys() for list of process
        * use .values() for list of paths `pathlib.Path` object
    """
    global ProcessPathStorage
    if clear: # ignore json file 
        ProcessPathStorage.clear()
    else: # Read paths for current process being worked on from file 
        with open(config['wf_processpath_json'], "r") as f:
            ProcessPathStorage = json.load(f, object_hook=json_to_path)   
        return ProcessPathStorage
    if not path: # default work folder of processes
        path = config['processos_path']        
    path = pathlib.Path(path)    
    paths = path.glob('*') 
    if 'time' in sort:
        paths = sorted(paths, key=os.path.getmtime)[::-1]        
    elif 'name' in sort:
        paths = sorted(paths)   
    for cur_path in paths: # remove what is NOT a process folder
        if not cur_path.is_dir():
            continue
        try:
            pud(str(cur_path))
            ProcessPathStorage.update({ pud(str(cur_path)).str : cur_path.absolute()})      
        except NotProcessNumber:
            continue 
    with open(config['wf_processpath_json'], "w") as f: # Serialize data into file
        json.dump(ProcessPathStorage, f, default=path_to_json)
    return ProcessPathStorage
    
    


### can be used to move process folders to Concluidos
def currentProcessMove(process_str, dest_folder='Concluidos', 
    rootpath=os.path.join(config['secor_path'], "Processos"), delpath=False):
    """
    move process folder path to `dest_folder` (this can create a new folder)
    * process_str : process name to move folder
    * dest_folder : path relative to root_path  default `__secor_path__\Processos`
    also stores the new path on `ProcessPathStorage` 
    * delpath : False (default) 
        delete the path from `ProcessPathStorage` (stop tracking)
    """    
    process_str = pud(process_str).str # just to make sure it is unique
    dest_path =  pathlib.Path(rootpath).joinpath(dest_folder).joinpath(
        processPath(process_str, fullpath=False)).resolve() # resolve, solves "..\" to an absolute path 
    shutil.move(ProcessPathStorage[process_str].absolute(), dest_path)    
    if delpath: 
        del ProcessPathStorage[process_str]
    else:
        ProcessPathStorage[process_str] = dest_path
    with open(config['wf_processpath_json'], "w") as f: # Serialize 
        json.dump(ProcessPathStorage, f, default=path_to_json)


def ProcessManagerFromHtml(path=None):    
    """fill in `ProcessManager` using html from folders of processes"""    
    if not path:
        path = pathlib.Path(config['processos_path']).joinpath("Concluidos")    
    currentProcessGet(path)
    ProcessManager.fromHtmls(ProcessPathStorage.values())        


