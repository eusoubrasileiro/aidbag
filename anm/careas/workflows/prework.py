import tqdm

from ....web.htmlscrap import wPageNtlm
from .. import estudos
from .. import scm
from ..scm.requests import RequestsSCMException
from ..estudos.scraping import DownloadInterferenciaFailed
from .sei import Sei, Processo
from .enums import ESTUDO_TYPE

# with sei.Sei(anm_user, anm_passwd, True) as seid:     
#     for name in progressbar(wf.currentProcessGet()):           
#         p = scm.ProcessManager[name]
#         if 'licen' in p['tipo'].lower(): # todos tipo licenciamento - ou que 
#             psei = sei.Processo.fromSei(seid, p['NUP'])                   
#             psei.downloadDocumentosFiltered(lambda x: True if 'municip' in x['title'].lower() else False)


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
    
    with Sei(wpage.user, wpage.passwd) as seid: # used bellow if needed (open only once)
        for processo in tqdm.tqdm(processos):        
            processo = processo.str        
            try:            
                if estudo is ESTUDO_TYPE.INTERFERENCIA:
                    _ = estudos.Interferencia.make(wpage, processo, verbose=verbose, overwrite=overwrite)                   
                if estudo is ESTUDO_TYPE.OPCAO:            
                    _ = scm.ProcessManager.GetorCreate(processo, wpage, task=scm.SCM_SEARCH.BASICOS_POLIGONAL, verbose=verbose)                            
                proc = scm.ProcessManager[processo]    
                # TODO: make this cleaner or generic other type of estudos 
                if estudo is ESTUDO_TYPE.OPCAO:
                    psei = Processo.fromSei(seid, proc['NUP'])
                    psei.downloadDocumentos(10) # autocreate processfolder      
                # todos licenciamento, mudança regime p/ etc.
                if 'licen' in proc['tipo'].lower(): 
                    psei = Processo.fromSei(seid, proc['NUP'])
                    # download licença municipal if any
                    psei.downloadDocumentosFiltered(lambda x: True if 'municip' in x['title'].lower() else False)
            except RequestsSCMException as e:
                pobj = scm.ProcessManager[processo] 
                dados = pobj.dados
                dados['prework'] = {'status' : dados['status'] }  # save for use on workapp
                pobj.update(dados)                
            except DownloadInterferenciaFailed as e:                
                pobj = scm.ProcessManager[processo] 
                dados = pobj.dados
                dados['prework'] = {'status' : {'error' : str(e)} } # save for use on workapp
                pobj.update(dados)
                nupstr = dados['NUP'] if 'NUP' in dados else processo # NotFoundError don't even fetch it                   
                failed_NUPS.append((nupstr, str(e)))             
            else:
                pobj = scm.ProcessManager[processo] 
                dados = pobj.dados
                dados['prework'] = { 'status' : 'ok' } # save for use on workapp
                pobj.update(dados)
                succeed_NUPs.append(pobj['NUP']) 
        # print all NUPS
    print('SEI NUPs sucess:')
    for nup in succeed_NUPs:
        print(nup)
    print('SEI NUPs failed:')
    for nup in failed_NUPS:
        print(nup)
    return succeed_NUPs, failed_NUPS