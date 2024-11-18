import sys 
import traceback
import os
import re 
import tqdm 

from .. import scm     
from ..config import config
from ..estudos.util import (
    downloadMinuta, 
    MINUTA
)

from .config import __workflow_debugging__
from .enums import WORK_ACTIVITY
from .sei import Processo

from .inference import (    
    inferWork
)

from .folders import (
    ProcessPathStorage,
    currentProcessGet
)


class AlreadyPublished(Exception):
  """Raised when a process was already published."""  

def handle_pdf_adicional(psei, dadosx, wpage, process_name):
    """Handles additional PDF download and insertion."""
    pdf_adicional = dadosx['work']['pdf_adicional']
    if pdf_adicional and not pdf_adicional.exists():
        downloadMinuta(wpage, process_name, str(pdf_adicional.absolute()), 
                    MINUTA.fromName(dadosx['work']['minuta']['title']))
    return str(pdf_adicional.absolute()) if pdf_adicional else None

def attribui_salva(psei, dadosx, process):
    psei.insereMarcador(config['sei']['marcador_default'])
    psei.atribuir(config['sei']['atribuir_default'])
    # make sure no other pop-up etc windows are still open    
    psei.closeOtherWindows() 
    if process:
        # prepare to save to db that it was published
        work = dadosx['work']    
        if 'nome_assinatura' in work:
            del work['nome_assinatura']
        work['type'] = str(work['type'])
        work['published'] = True
        # save on db it was published successfully
        process.update(dadosx)

def prepareData(process_name, verbose, republish, wpage, activity=None):
    """Infers work and collects data por publishing the given process."""
    if isinstance(process_name, scm.pud):
        process_name = process_name.str  
    else:
        process_name = scm.pud(process_name).str         
    if process_name not in scm.ProcessManager:
        scm.ProcessManager.GetorCreate(process_name, wpage, task=scm.SCM_SEARCH.BASICOS_POLIGONAL)
    process = scm.ProcessManager[process_name]  
    dados = process.dados 
    if ('work' in dados and 
        'published' in dados['work'] and 
        dados['work']['published'] and 
        not republish):
        raise AlreadyPublished("Process already published - ignoring")
    if process_name not in ProcessPathStorage:     
        raise FileNotFoundError(f"Process {process_name} folder not found! Just checked in ProcessPathStorage. Did you run it?")
    process_folder = ProcessPathStorage[process_name]        
    dadosx = inferWork(process_name, dados, process_folder)             
    if not activity:        
        activity = dadosx['work']['type'] # get from inferred information
    if verbose and __workflow_debugging__:
        if process_folder:
            print("Main path: ", process_folder.parent)     
            print("Process path: ", process_folder.absolute())
            print("Current dir: ", os.getcwd())
        print(f"activity {activity} \n dadosx dict {dadosx}")         
    return dadosx, activity, process 

def PublishDocumentosSEI(sei, process_name, wpage, activity=None, 
        ignore_area_check=False, verbose=True, 
        republish=False, sign=False, **kwargs):
    """
    Inclui process documents from folder specified on `ProcessPathStorage`

    * sei : class
        selenium chrome webdriver instance
        
    * process_name: string of name of process - any format
        folder where documentos are placed will be obtained from `ProcessPathStorage`

    * wpage: wPageNtlm 
        baixa NUP e outros from html salvo
        faz download da minuta 

    * verbose: True
        avisa ausência de pdfs, quando cria documentos sem anexos

    * activity : None or Enum `WORK_ACTIVITY` 
        If None infer from tipo and fase dados basicos processo 
        documents to add. Otherwise specify explicitly what to do.        

    * ignore_area_check: False
        Ignore check of area for disponibilidade 

    * republish: False
        whether to republish a process already published on SEI
        check if dados['work']['published'] === True
    
    * sign: False
        whether to sign after publishing or not                 
    """
    
    if not ProcessPathStorage: # empty process path storage
        currentProcessGet() # get current list of processes
    
    if activity is WORK_ACTIVITY.ARQUIVAMENTO_ERRO_REPEM:         
        # não tem cadastro no SCM - não tem nada só SEI
        psei = Processo.fromSei(sei, process_name) # name must be NUP real in this case            
        process = None 
        dadosx = {}
    else:
        dadosx, activity, process = prepareData(process_name, verbose, republish, wpage, activity)        
        psei = Processo.fromSei(sei, process['NUP'])                    
        
    if (activity in WORK_ACTIVITY.INTERFERENCIA_GENERICO or 
        activity in WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_RESTUDO or
        activity in WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_EDITAL):
        estudo_interferencia_name = "Estudo de Retirada de Interferência"
        if dadosx['work']['bloqueio']:
            estudo_interferencia_name += "(Simulação)"
        # Inclui Estudo Interferência pdf como Doc Externo no SEI
        psei.insereDocumentoExterno(estudo_interferencia_name, 
            dadosx['estudo']['sigareas']['pdf_path'])      
        # Inclui Minuta, Reg. Extração, PLG, Licenciamento (Empty)
        if 'ok' in dadosx['work']['resultado']:
            pdf_adicional = handle_pdf_adicional(psei, dadosx, wpage, process.name)
            psei.insereDocumentoExterno(dadosx['work']['minuta']['title'], pdf_adicional)

    if (activity in WORK_ACTIVITY.INTERFERENCIA_GENERICO_REQUERIMENTO and
        activity is not WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_EDITAL):
        # Formulário de Prioridade
        psei.insereFormPrioridade(dadosx)
        attribui_salva(psei, dadosx, process)

    elif activity is WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_EDITAL:
        # Nota Técnica ao invés de Formulário de Prioridade
        doc_model = "req_edital_son"
        psei.insereNotaTecnicaRequerimento(doc_model, infos=dadosx['work'], 
            requerimento=dadosx['tipo'], 
            minuta=dadosx['work']['minuta']['title'])      
        attribui_salva(psei, dadosx, process)
        # force run for dad just bellow 
        PublishDocumentosSEI(psei, dadosx['work']['edital']['dad'], wpage,        
                             activity=WORK_ACTIVITY.ARQUIVAMENTO_EDITAL_DAD)       
    elif activity in WORK_ACTIVITY.OPCAO_REQUERIMENTO:
        # Nota Técnica ao invés de Formulário de Prioridade
        doc_externo = "Estudo de Opção"
        # Inclui Estudo Interferência pdf como Doc Externo no SEI        
        psei.insereDocumentoExterno(doc_externo, 
            dadosx['estudo']['sigareas']['pdf_path'])      
        if 'ok' in dadosx['work']['resultado']:
            pdf_adicional = handle_pdf_adicional(psei, dadosx, wpage, process.name)
            psei.insereDocumentoExterno(dadosx['work']['minuta']['title'], pdf_adicional)
        doc_model = "req_opcao_feita"            
        psei.insereNotaTecnicaRequerimento(doc_model, dadosx, 
            requerimento=dadosx['tipo'], 
            minuta=dadosx['work']['minuta']['title'])
        attribui_salva(psei, dadosx, process)

    elif activity in WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_RESTUDO:        
        doc_model = "req_restudo"            
        psei.insereNotaTecnicaRequerimento(doc_model, dadosx, 
            requerimento=dadosx['tipo'], 
            minuta=dadosx['work']['minuta']['title'])
        attribui_salva(psei, dadosx, process)
        
    elif activity in WORK_ACTIVITY.ARQUIVAMENTO_EDITAL_DAD:                
        dad, son = dadosx['work']['edital']['dad'], dadosx['work']['edital']['son']        
        dad, son = scm.ProcessManager[dad], scm.ProcessManager[son]     
        def check_get_polygon(proc):
            if 'polygon' not in proc or not proc['polygon']: 
                proc._wpage =  wpage.copy()            
                proc.runTask(scm.SCM_SEARCH.BASICOS_POLIGONAL) 
        check_get_polygon(dad)
        check_get_polygon(son)
        # this is where we will put documents - fly to there - since we were in the son above
        psei = Processo.fromSei(sei, dad['NUP'])         
        # calculate again: check in case area was not checked by infer method
        areadiff = dad['polygon'][0]['area']-son['polygon'][0]['area']
        # SOMETIMES it'll fail before comming here, when son not found
        # TODO deal with more participants on edital                
        if areadiff > 0.1 and not ignore_area_check: # compare areas if difference > 0.1 ha stop! - not same area
            raise NotImplementedError(f"Not same Area! dad {dad['polygon'][0]['area']:.2f} ha son {son['polygon'][0]['area']:.2f} ha")
        doc_model = "req_edital_dad"
        psei.insereNotaTecnicaRequerimento(doc_model, dadosx, edital=dadosx['work']['edital']['tipo'], 
                            processo_filho=son['NUP'])
        process = dad # this is what was done
        attribui_salva(psei, dadosx, process)

    elif activity in WORK_ACTIVITY.ARQUIVAMENTO_ERRO_REPEM:
        psei.insereNotaTecnicaRequerimento('req_erro_repem')            
        attribui_salva(psei, dadosx, process)

    elif activity in WORK_ACTIVITY.NOTA_TECNICA_GENERICA:
        psei.insereNotaTecnicaRequerimento(kwargs['doc_template_name'], dadosx)    
        attribui_salva(psei, dadosx, process)

    # elif activity in WORK_ACTIVITY.FORMULARIO_1_DIREITO_RLAVRA:
    #     psei.insereDocumentoExterno( "Estudo de Retirada de Interferência", 
    #      dadosx['estudo']['sigareas']['pdf_path'])
    #     if 'ok' in dadosx['work']['resultado']:     
    #         pdf_adicional = dadosx['work']['pdf_adicional']
    #         if pdf_adicional and not pdf_adicional.exists():                          
    #             downloadMinuta(wpage, process.name, 
    #                             str(pdf_adicional.absolute()), MINUTA.fromName(dadosx['work']['minuta']['title']))
    #         # guarantee to insert an empty in any case
    #         pdf_adicional = str(pdf_adicional.absolute()) if pdf_adicional else None 
    #         psei.insereDocumentoExterno(dadosx['work']['minuta']['title'], pdf_adicional)     
    # elif activity in WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento
    #     psei.insereDocumentoExterno(3, str(dadosx['pdf_sigareas'].absolute()))  # estudo opção
    #     if not dadosx['pdf_adicional'].exists():
    #         downloadMinuta(wpage, process.name, 
    #                     str(dadosx['pdf_adicional'].absolute()), dadosx['minuta']['code'])     
    #                     # guarantee to insert an empty in any case
    #     pdf_adicional = str(dadosx['pdf_adicional'].absolute()) if dadosx['pdf_adicional'].exists() else None 
    #     psei.insereDocumentoExterno(dadosx['minuta']['doc_ext'], pdf_adicional) # minuta alvará           
    #     psei.insereNotaTecnicaRequerimento("opção_feita", dadosx) 
    # elif activity in WORK_ACTIVITY.REQUERIMENTO_MUDANCA_REGIME: # mudança de regimen com redução
    #     psei.insereDocumentoExterno(8, str(dadosx['pdf_sigareas'].absolute()))  # estudo opção
    #     if not dadosx['pdf_adicional'].exists():
    #         downloadMinuta(wpage, process.name, 
    #                     str(dadosx['pdf_adicional'].absolute()), dadosx['minuta']['code'])     
    #                     # guarantee to insert an empty in any case
    #     pdf_adicional = str(dadosx['pdf_adicional'].absolute()) if dadosx['pdf_adicional'].exists() else None 
    #     psei.insereDocumentoExterno(dadosx['minuta']['doc_ext'], pdf_adicional) # minuta alvará           
    #     psei.insereNotaTecnicaRequerimento("sem_redução", dadosx)  # need a new one for mudança regime

   
    # TODO: I need another database to save these - like an Archive
    # process._dados['estudo].update( {'sei-sent': True, 'time' : datetime.datetime.now()} )
    # process.changed() # update database 
    



def PublishDocumentosSEI_list(sei, wpage, process_names, **kwargs):
    """
    Wrapper for `PublishDocumentosSEI` 
    
    Aditional args should be passed as keyword arguments

    Use list of names of process to incluir documents on SEI, folder don't need to exist.
    """
    done = '' 
    for process_name in tqdm.tqdm(process_names):
        try:
            PublishDocumentosSEI(sei, process_name, wpage, **kwargs)
        except AlreadyPublished:
            print(f"Ignored {process_name} already published", file=sys.stderr)           
            continue 
        except Exception:
            print(f"Process {process_name} Exception: ", traceback.format_exc(), file=sys.stderr)           
            continue       
        nup = process_name # case of process not on SCM
        if process_name in scm.ProcessManager:
            nup = scm.ProcessManager[process_name]['NUP']
        done +=  nup + '\n'
    print(f"Done:\n{done}")     
    return done 


def PublishDocumentosSEIFirstN(sei, wpage, nfirst=1, path=None, **kwargs):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI. Follow order of glob(*) 
    
    Wrapper for `PublishDocumentosSEI` 
    
    Aditional args should be passed as keyword arguments
    """
    currentProcessGet(path)    
    process_folders = list(ProcessPathStorage.keys())[:nfirst]
    done = PublishDocumentosSEI_list(sei, wpage, process_folders, **kwargs)
    return done 

