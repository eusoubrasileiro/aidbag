from .. import estudos
from .. import scm
from ..config import config
from .config import ESTUDO_TYPE

import tqdm
import traceback
import sys 


def EstudoBatchRun(wpage, processos, estudo=ESTUDO_TYPE.INTERFERENCIA, verbose=False, overwrite=False):
    """      
    TODO?
    - Analise de Formulario 1
    """
    succeed_NUPs = [] # suceed 
    failed_NUPS = [] # failed
    estudo = None
    for processo in tqdm.tqdm(processos):        
        try:            
            if estudo == 'interferencia':
                estudo = estudos.Interferencia.make(wpage, processo, verbose=verbose, overwrite=overwrite)   
                proc = estudo.processo              
            elif estudo == 'opção':
                proc = scm.ProcessManager.GetorCreate(processo, wpage, dados=scm.SCM_SEARCH.BASICOS_POLIGONAL, verbose=verbose)
                proc.salvaPageScmHtml(config['processos_path'], 'basic', overwrite)
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