from enum import Flag, auto
from .. import estudos
from .. import scm
from ..config import config
from ..util import processPath
from .sei import Sei, Processo

import tqdm
import traceback
import sys 

class ESTUDO_TYPE(Flag):
    INTERFERENCIA = auto()
    OPCAO = auto()

def BatchPreAnalyses(wpage, processos, estudo=ESTUDO_TYPE.INTERFERENCIA, verbose=False, overwrite=False, **kwargs):
    """        
    Batch run pre-analyses (prepare analyses) for *multiple processos* generating their estudos of interferência or opção.
    Create folders, spreadsheets and database entries from web-scrapped data.
    After this the `workapp` system can be used to analyse each processes one by one.  

    * wpage : wPage html
    * processos : list
    * estudo : ESTUDO_TYPE
        ESTUDO_TYPE.INTERFERENCIA
        ESTUDO_TYPE.OPCAO : needs SEI `user` and `passwd` as **kwargs
    * verbose : bool
    * overwrite : bool (default False)
        weather to re-download files and ignore local database entries and files
    """
    
    succeed_NUPs = [] # suceed 
    failed_NUPS = [] # failed
    for processo in tqdm.tqdm(processos):        
        try:            
            if estudo is ESTUDO_TYPE.INTERFERENCIA:
                _ = estudos.Interferencia.make(wpage, processo, verbose=verbose, overwrite=overwrite)   
                proc = _.processo              
            elif estudo is ESTUDO_TYPE.OPCAO:
                proc = scm.ProcessManager.GetorCreate(processo, wpage, task=scm.SCM_SEARCH.BASICOS_POLIGONAL, verbose=verbose)
                with Sei(kwargs['user'], kwargs['passwd'], headless=True) as seid:
                    psei = Processo.fromSei(seid, proc['NUP'])
                    psei.download_latest_documents(10)                
        except Exception as e:              
            print(f"Process {processo} Exception: {traceback.format_exc()}", file=sys.stderr)                       
            failed_NUPS.append((scm.ProcessManager[scm.fmtPname(processo)]['NUP'],''))            
        else:
            succeed_NUPs.append(proc['NUP'])  
    # print all NUPS
    print('SEI NUPs sucess:')
    for nup in succeed_NUPs:
        print(nup)
    print('SEI NUPs failed:')
    for nup in failed_NUPS:
        print(nup)
    return succeed_NUPs, failed_NUPS