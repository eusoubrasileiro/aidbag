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

from .sei import Processo
from .config import __workflow_debugging__

from .inference import (
    WORK_ACTIVITY,
    inferWork
)

from .folders import (
    ProcessPathStorage,
    currentProcessGet
)


def IncluiDocumentosSEI(sei, process_name, wpage, activity=None, usefolder=True,
        empty=False, termo_abertura=False, verbose=True, **kwargs):
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

    * usefolder: True
        If False, only add documents on SEI don't use folder
        And uses 'req_custom.html' for 'Nota Técnica'.        
        
    * empty : True
        cria documentos sem anexos

    * activity : None or Enum `WORK_ACTIVITY` 
        If None infer from tipo and fase dados basicos processo 
        documents to add. Otherwise specify explicitly what to do.
        
    * termo_abertura: False
        To add for process older than < 2020
                
    """
    
    if not ProcessPathStorage: # empty process path storage
        currentProcessGet() # get current list of processes

    process_name = scm.fmtPname(process_name)         

    if (activity is WORK_ACTIVITY.REQUERIMENTO_EDITAL_DAD or 
        activity is WORK_ACTIVITY.NOTA_TECNICA_GENERICA):
        usefolder = False

    if not usefolder:
        # Only writes on SEI (don't need folder and pdf's)
        # but needs scm data, probably not downloaded yet, e.g. parent edital 
        if process_name not in scm.ProcessManager:
            scm.ProcessManager.GetorCreate(process_name, wpage, task=scm.SCM_SEARCH.BASICOS_POLIGONAL)
    
    process = scm.ProcessManager[process_name]  
    process_folder = None     
    if usefolder: # needs folder docs and information  
        if process_name not in ProcessPathStorage:     
            raise FileNotFoundError(f"Process {process_name} folder not found! Just checked in ProcessPathStorage. Did you run it?")
        process_folder = ProcessPathStorage[process_name]
    info = inferWork(process, process_folder)       
    if not activity:        
        activity = info['work'] # get from inferred information

    if verbose and __workflow_debugging__:
        if process_folder:
            print("Main path: ", process_folder.parent)     
            print("Process path: ", process_folder.absolute())
            print("Current dir: ", os.getcwd())
        print(f"activity {activity} \n info dict {info}")         
    
    # finally opens SEI with selenium
    psei = Processo.fromSei(sei, process['NUP'])            
    # inclui vários documentos, se desnecessário é só apagar
    # Inclui termo de abertura de processo eletronico se data < 2020 (protocolo digital nov/2019)
    if termo_abertura and process['data_protocolo'].year < 2020:  
        psei.InsereTermoAberturaProcessoEletronico()    
        
    if (activity in WORK_ACTIVITY.REQUERIMENTO_GENERICO_NOT_EDITAL or 
        activity in WORK_ACTIVITY.REQUERIMENTO_REGISTRO_EXTRAÇÃO):
        # formulário de prioridade
        # Inclui Estudo Interferência pdf como Doc Externo no SEI
        psei.insereDocumentoExterno("Estudo Interferência", str(info['pdf_sigareas'].absolute()))   
        if 'ok' in info['estudo']:                
            if not info['pdf_adicional'].exists():
                downloadMinuta(wpage, process.name, 
                    str(info['pdf_adicional'].absolute()), MINUTA.fromName(info['minuta']['title']))                   
            pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
            psei.insereDocumentoExterno(info['minuta']['title'], pdf_adicional)
        psei.insereFormPrioridade(info)

    # EDITAL GOES ABOVE TOO! but for now .. let's wait

    # elif activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL:
    #     psei.insereDocumentoExterno("Estudo Interferência", str(info['pdf_sigareas'].absolute()))   
    #     if not info['pdf_adicional'].exists():
    #         downloadMinuta(wpage, process.name, 
    #                 str(info['pdf_adicional'].absolute()), info['minuta']['code'])
    #     # guarantee to insert an empty in any case
    #     pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
    #     psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional)                        
    #     psei.insereNotaTecnicaRequerimento("edital_son", info)            
    #     # guarantee to insert an empty in any case
    #     pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
    #     psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional)        
    #         psei.insereNotaTecnicaRequerimento("com_redução", info, # com notificação titular
    #                 area_porcentagem=str(info['areas']['percs'][0]).replace('.',','))                            
    #     else:
    #         psei.insereNotaTecnicaRequerimento("sem_redução", info) 
    #         # Recomenda Só análise de plano s/ notificação titular (mais comum)

    # elif activity in WORK_ACTIVITY.DIREITO_RLAVRA_FORMULARIO_1:
    #     psei.insereDocumentoExterno(0, str(info['pdf_sigareas'].absolute())) 
    #     if 'ok' in info['estudo']:                
    #         if not info['pdf_adicional'].exists():
    #             downloadMinuta(wpage, process.name, 
    #                             str(info['pdf_adicional'].absolute()), info['minuta']['code'])
    #         # guarantee to insert an empty in any case
    #         pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
    #         psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) 
    # elif activity in WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento
    #     psei.insereDocumentoExterno(3, str(info['pdf_sigareas'].absolute()))  # estudo opção
    #     if not info['pdf_adicional'].exists():
    #         downloadMinuta(wpage, process.name, 
    #                     str(info['pdf_adicional'].absolute()), info['minuta']['code'])     
    #                     # guarantee to insert an empty in any case
    #     pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
    #     psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) # minuta alvará           
    #     psei.insereNotaTecnicaRequerimento("opção_feita", info) 
    # elif activity in WORK_ACTIVITY.REQUERIMENTO_MUDANCA_REGIME: # mudança de regimen com redução
    #     psei.insereDocumentoExterno(8, str(info['pdf_sigareas'].absolute()))  # estudo opção
    #     if not info['pdf_adicional'].exists():
    #         downloadMinuta(wpage, process.name, 
    #                     str(info['pdf_adicional'].absolute()), info['minuta']['code'])     
    #                     # guarantee to insert an empty in any case
    #     pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
    #     psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) # minuta alvará           
    #     psei.insereNotaTecnicaRequerimento("sem_redução", info)  # need a new one for mudança regime
    # elif activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL_DAD:
    #     # doesn't matter if son or dad was passed, here it's sorted!
    #     dad, son = dispDadSon(process_name)
    #     for p in [dad, son]:
    #         if p not in scm.ProcessManager:
    #             scm.ProcessManager.GetorCreate(p, wpage, scm.SCM_SEARCH.BASICOS_POLIGONAL)
    #     dad, son = scm.ProcessManager[dad], scm.ProcessManager[son]     
    #     # this is where we will put documents - fly to there - since we were in the son above
    #     psei = Processo.fromSei(sei, dad['NUP']) 
    #     # calculate again: check in case area was not checked by infer method
    #     areadiff = dad['polygon'][0]['area']-son['polygon'][0]['area']
    #     # SOMETIMES it'll fail before comming here, when son not found
    #     # TODO deal with more participants on edital                
    #     if areadiff > 0.1: # compare areas if difference > 0.1 ha stop! - not same area
    #         raise NotImplementedError(f"Not same Area! dad {dad['polygon'][0]['area']:.2f} ha son {son['polygon'][0]['area']:.2f} ha")
    #     psei.insereNotaTecnicaRequerimento("edital_dad", info, edital=editalTipo(son), 
    #                         processo_filho=son['NUP'])
    #     process = dad # this is what was done
    # elif activity in WORK_ACTIVITY.NOTA_TECNICA_GENERICA:
    #     psei.insereNotaTecnicaRequerimento(kwargs['doc_template_name'], info)    

    psei.insereMarcador(config['sei']['marcador_default'])
    psei.atribuir(config['sei']['atribuir_default'])
    # should also close the openned text window - going to previous state
    psei.closeOtherWindows()        
    # TODO: I need another database to save these - like an Archive
    # process._dados['iestudo'].update( {'sei-sent': True, 'time' : datetime.datetime.now()} )
    # process.changed() # update database 



def IncluiDocumentosSEI_list(sei, wpage, process_names, **kwargs):
    """
    Wrapper for `IncluiDocumentosSEI` 
    
    Aditional args should be passed as keyword arguments

    Use list of names of process to incluir documents on SEI, folder don't need to exist.
    """
    done = '' 
    for process_name in tqdm.tqdm(process_names):
        try:
            IncluiDocumentosSEI(sei, process_name, wpage, **kwargs)
        except Exception:
            print("Process {:} Exception: ".format(process_name), traceback.format_exc(), file=sys.stderr)           
            continue       
        done += scm.ProcessManager[process_name]['NUP'] + '\n'
    print(f"Done:\n{done}")     


def IncluiDocumentosSEIFirstN(sei, wpage, nfirst=1, path=None, **kwargs):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI. Follow order of glob(*) 
    
    Wrapper for `IncluiDocumentosSEI` 
    
    Aditional args should be passed as keyword arguments
    """
    currentProcessGet(path)    
    process_folders = list(ProcessPathStorage.keys())[:nfirst]
    IncluiDocumentosSEI_list(sei, wpage, process_folders, **kwargs)