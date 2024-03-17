from .. import estudos
from .. import scm
from ..config import config
from .config import ESTUDO_TYPE
from ..util import processPath
from ..sei import Sei, Processo

import tqdm
import traceback
import sys 


def EstudoBatchRun(wpage, processos, estudo=ESTUDO_TYPE.INTERFERENCIA, verbose=False, overwrite=False, **kwargs):
    """          
    ESTUDO_TYPE.INTERFERENCIA
    ESTUDO_TYPE.OPCAO : needs SEI `user` and `passwd` as **kwargs
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
        except scm.ErrorProcessSCM as e:
            print(f"Process {processo} Exception: {traceback.format_exc()}", file=sys.stderr)   
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