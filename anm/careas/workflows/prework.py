import traceback
import sys 
import tqdm

from ....web.htmlscrap import wPageNtlm
from .. import estudos
from .. import scm
from ..estudos.scraping import DownloadInterferenciaFailed
from ..config import config
from ..util import processPath
from .sei import Sei, Processo
from .enums import ESTUDO_TYPE


def BatchPreAnalyses(wpage : wPageNtlm, processos: list[scm.pud], 
    estudo : ESTUDO_TYPE = ESTUDO_TYPE.INTERFERENCIA, 
    verbose : bool = False, overwrite: bool = False, **kwargs):
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
        processo = processo.str        
        try:            
            if estudo is ESTUDO_TYPE.INTERFERENCIA:
                _ = estudos.Interferencia.make(wpage, processo, verbose=verbose, overwrite=overwrite)   
                proc = scm.ProcessManager[processo]
            elif estudo is ESTUDO_TYPE.OPCAO:
                _ = scm.ProcessManager.GetorCreate(processo, wpage, task=scm.SCM_SEARCH.BASICOS_POLIGONAL, verbose=verbose)
                proc = scm.ProcessManager[processo]     
                with Sei(kwargs['user'], kwargs['passwd'], headless=True) as seid:
                    psei = Processo.fromSei(seid, proc['NUP'])
                    psei.download_latest_documents(10) # autocreate processfolder                                  
        except DownloadInterferenciaFailed as e:
            dados = proc.dados
            dados['prework'] = {'status' : 'error', 'error' : str(e)} # save for use on workapp
            scm.ProcessManager[processo].update(dados)
            failed_NUPS.append((dados['NUP'], str(e))) 
        except Exception as e:
            failed_NUPS.append((proc['NUP'],
                f"Process {processo} Exception: {traceback.format_exc()}"))            
        else:
            dados = proc.dados
            dados['prework'] = { 'status' : 'ok' } # save for use on workapp
            scm.ProcessManager[processo].update(dados)
            succeed_NUPs.append(proc['NUP']) 
    # print all NUPS
    print('SEI NUPs sucess:')
    for nup in succeed_NUPs:
        print(nup)
    print('SEI NUPs failed:')
    for nup in failed_NUPS:
        print(nup)
    return succeed_NUPs, failed_NUPS