import sys 
import traceback
import os
import re 

from .. import scm     
from ..config import config
from ..estudos.util import downloadMinuta
from ..sei import (
    docs_externos,
    Processo,    
)
from .tools import (
    dispDadSon,
    dispGetNUP
)
from .folders import (
    ProcessPathStorage,
    currentProcessGet
)

from .config import (
    WORK_ACTIVITY,
    __workflow_debugging__
)

from PyPDF2 import PdfReader


def readPdfText(filename):
    reader = PdfReader(filename)   
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    return text  


def inferWork(process, folder=None):
    """
    From Processo object and work-folder try to infer the work and docs to create or add.
    
    returns dict with lots of infos key,value pairs    
    """
    infos = {}   

    # 'doc_ext' from config.docs_externos
    infos['minuta']  =  {'de' : '', 'code': 0, 'doc_ext': -1}
    infos['edital'] = {}
    
    if 'requerimento' in process['tipo'].lower():     
        if 'garimpeira' in process['fase'].lower():
            infos['requerimento'] = 'Permissão de Lavra Garimpeira'
            infos['minuta']['de']  = 'de ' + infos['requerimento']
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_PLG
            infos['minuta']['code'] = 4  
            infos['minuta']['doc_ext'] = 5          
        elif 'lavra' in process['fase'].lower():
            infos['work'] = WORK_ACTIVITY.DIREITO_RLAVRA_FORMULARIO_1
            infos['minuta']['de']  = 'de ' + 'Portaria de Lavra'
            infos['minuta']['code'] = 2
            infos['minuta']['doc_ext'] = 6
        elif 'licenciamento' in process['fase'].lower():
            infos['requerimento'] = 'Licenciamento'
            infos['minuta']['de']  = 'de ' + infos['requerimento']
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_LICENCIAMENTO
            infos['minuta']['code'] = 5 # must be downloaded by hand
            infos['minuta']['doc_ext'] = 2
        elif 'extração' in process['fase'].lower():
            infos['requerimento'] = 'Registro de Extração'
            infos['minuta']['de']  = 'de ' + infos['requerimento']
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_REGISTRO_EXTRAÇÃO
            infos['minuta']['code'] = 6            
            infos['minuta']['doc_ext'] = 7
        elif 'pesquisa' in process['fase'].lower():       
            infos['requerimento'] = 'Pesquisa'
            infos['minuta']['de']  = 'de Alvará de Pesquisa'
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_PESQUISA
            infos['minuta']['code'] = 1
            infos['minuta']['doc_ext'] = 1
            # advindos de editais de disponibilidade (leilão ou oferta pública)               
            if 'leilão' in process['tipo'].lower():   
                  infos['work'] = WORK_ACTIVITY.REQUERIMENTO_EDITAL    
                  infos['edital'] = {'tipo' : 'Leilão', 'pai' : dispGetNUP(process)}                  
            if 'pública' in process['tipo'].lower():   
                  infos['work'] = WORK_ACTIVITY.REQUERIMENTO_EDITAL    
                  infos['edital'] = {'tipo' : 'Oferta Pública', 'pai' : dispGetNUP(process)}    

    infos['pdf_sigareas'] = None
    infos['pdf_adicional'] = None 
    infos['nome_assinatura'] = config['sei']['nome_assinatura']

    if folder is not None:
        # search/parse local folder
        # Estudo de Interferência deve chamar 'R@&.pdf' glob.glob("R*.pdf")[0] seja o primeiro - 
        # multiple downloads at suffix (1), (2) etc..
        pdf_sigareas = [ file for file in folder.glob(config['sigares']['doc_prefix'] + '*.pdf') ]
        # turn empty list to None
        infos['pdf_sigareas'] = pdf_sigareas[0] if pdf_sigareas else None
        # search/parse process object
        if infos['pdf_sigareas']:
            pdf_sigareas_text = readPdfText(infos['pdf_sigareas'].absolute())
            if 'OPÇÃO DE ÁREA' in pdf_sigareas_text:
                infos['work'] = WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA
                infos['estudo'] = 'ok' # minuta de alvará
            if 'MUDANÇA DE REGIME COM REDUÇÃO' in pdf_sigareas_text:
                infos['work'] = WORK_ACTIVITY.REQUERIMENTO_MUDANCA_REGIME
                infos['estudo'] = 'ok'
            else:
                if '(Áreas de Bloqueio)' in  pdf_sigareas_text:
                    print(f" { process['NUP'] } com bloqueio ",file=sys.stderr)
                    # this is not enough - bloqueio provisório é o que importa              
                if 'ENGLOBAMENTO' in pdf_sigareas_text:
                    infos['estudo'] = 'ok' 
                else:
                    area_text="PORCENTAGEM ENTRE ESTA ÁREA E A ÁREA ORIGINAL DO PROCESSO:" # para cada area poligonal 
                    count = pdf_sigareas_text.count(area_text)            
                    infos['areas'] = {'count' : count}
                    infos['areas'] = {'perc' : []}
                    if count == 0:
                        infos['estudo'] = 'interf_total'
                    elif count > 0: # só uma área
                        if count == 1:
                            infos['estudo'] = 'ok'
                        if count > 1:
                            infos['estudo'] = 'opção'
                        percs = re.findall(f"(?<={area_text}) +([\d,]+)", pdf_sigareas_text)
                        percs = [ float(x.replace(',', '.')) for x in percs ]  
                        infos['areas']['perc'] = percs                 
        else:
            RuntimeError('Nao encontrou pdf R*.pdf')

        if 'estudo' in infos and 'ok' in infos['estudo']:                
            infos['pdf_adicional'] = folder / "minuta.pdf"

    if __workflow_debugging__:
        print(infos)              
    return infos 


def IncluiDocumentosSEI(sei, process_name, wpage, activity=None, usefolder=True,
        empty=False, termo_abertura=False, verbose=True):
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
        
    if activity in WORK_ACTIVITY.REQUERIMENTO_GENERICO:
        # Inclui Estudo Interferência pdf como Doc Externo no SEI
        psei.insereDocumentoExterno(0, str(info['pdf_sigareas'].absolute()))                    
        if activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL:
            if not info['pdf_adicional'].exists():
                downloadMinuta(wpage, process.name, 
                        str(info['pdf_adicional'].absolute()), info['minuta']['code'])
            # guarantee to insert an empty in any case
            pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
            psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional)                        
            psei.insereNotaTecnicaRequerimento("edital_son", info)            
        elif activity in WORK_ACTIVITY.REQUERIMENTO_GENERICO_NOT_EDITAL:  
            if 'interf_total' in info['estudo']:
                psei.insereNotaTecnicaRequerimento("interferência_total", info)           
            elif 'opção' in info['estudo']:
                psei.insereNotaTecnicaRequerimento("opção", info)                            
            elif 'ok' in info['estudo']:                
                if not info['pdf_adicional'].exists():
                    downloadMinuta(wpage, process.name, 
                                str(info['pdf_adicional'].absolute()), info['minuta']['code'])
                # guarantee to insert an empty in any case
                pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
                psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional)
                if info['areas']['perc'][0] < 96.0: # > 4% change notificar 
                    psei.insereNotaTecnicaRequerimento("com_redução", info, # com notificação titular
                            area_porcentagem=str(info['areas']['perc'][0]).replace('.',','))                            
                else:
                    psei.insereNotaTecnicaRequerimento("sem_redução", info) 
                    # Recomenda Só análise de plano s/ notificação titular (mais comum)

    elif activity in WORK_ACTIVITY.DIREITO_RLAVRA_FORMULARIO_1:
        psei.insereDocumentoExterno(0, str(info['pdf_sigareas'].absolute())) 
        if 'ok' in info['estudo']:                
            if not info['pdf_adicional'].exists():
                downloadMinuta(wpage, process.name, 
                                str(info['pdf_adicional'].absolute()), info['minuta']['code'])
            # guarantee to insert an empty in any case
            pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
            psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) 
    elif activity in WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento
        psei.insereDocumentoExterno(3, str(info['pdf_sigareas'].absolute()))  # estudo opção
        if not info['pdf_adicional'].exists():
            downloadMinuta(wpage, process.name, 
                        str(info['pdf_adicional'].absolute()), info['minuta']['code'])     
                        # guarantee to insert an empty in any case
        pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
        psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) # minuta alvará           
        psei.insereNotaTecnicaRequerimento("opção_feita", info) 
    elif activity in WORK_ACTIVITY.REQUERIMENTO_MUDANCA_REGIME: # mudança de regimen com redução
        psei.insereDocumentoExterno(8, str(info['pdf_sigareas'].absolute()))  # estudo opção
        if not info['pdf_adicional'].exists():
            downloadMinuta(wpage, process.name, 
                        str(info['pdf_adicional'].absolute()), info['minuta']['code'])     
                        # guarantee to insert an empty in any case
        pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
        psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) # minuta alvará           
        psei.insereNotaTecnicaRequerimento("sem_redução", info)  # need a new one for mudança regime
    elif activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL_DAD:
        # doesn't matter if son or dad was passed, here it's sorted!
        dad, son = dispDadSon(process_name)
        for p in [dad, son]:
            if p not in scm.ProcessManager:
                scm.ProcessManager.GetorCreate(p, wpage, scm.SCM_SEARCH.BASICOS_POLIGONAL)
        dad, son = scm.ProcessManager[dad], scm.ProcessManager[son]     
        # this is where we will put documents - fly to there - since we were in the son above
        psei = Processo.fromSei(sei, dad['NUP']) 
        # calculate again: check in case area was not checked by infer method
        areadiff = dad['poligon'][0]['area']-son['poligon'][0]['area']
        # SOMETIMES it'll fail before comming here, when son not found
        # TODO deal with more participants on edital                
        if areadiff > 0.1: # compare areas if difference > 0.1 ha stop! - not same area
            raise NotImplementedError(f"Not same Area! dad {dad['poligon'][0]['area']:.2f} ha son {son['poligon'][0]['area']:.2f} ha")
        psei.insereNotaTecnicaRequerimento("edital_dad", info, edital=editalTipo(son), 
                            processo_filho=son['NUP'])
        process = dad # this is what was done
    elif activity in WORK_ACTIVITY.NOTA_TECNICA_GENERICA:
        psei.insereNotaTecnicaRequerimento("custom", info)    

    psei.insereMarcador(config['sei']['marcador_default'])
    psei.atribuir(config['sei']['atribuir_default'])
    # should also close the openned text window - going to previous state
    psei.closeOtherWindows()        
    if verbose:
        print(process['NUP'])    
    # TODO: I need another database to save these - like an Archive
    # process._dados['iestudo'].update( {'sei-sent': True, 'time' : datetime.datetime.now()} )
    # process.changed() # update database 



def IncluiDocumentosSEI_list(sei, wpage, process_names, **kwargs):
    """
    Wrapper for `IncluiDocumentosSEI` 
    
    Aditional args should be passed as keyword arguments

    Use list of names of process to incluir documents on SEI, folder don't need to exist.
    """
    for process_name in process_names:
        try:
            IncluiDocumentosSEI(sei, process_name, wpage, **kwargs)
        except Exception:
            print("Process {:} Exception: ".format(process_name), traceback.format_exc(), file=sys.stderr)           
            continue        


def IncluiDocumentosSEIFirstN(sei, wpage, nfirst=1, path=None, **kwargs):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI. Follow order of glob(*) 
    
    Wrapper for `IncluiDocumentosSEI` 
    
    Aditional args should be passed as keyword arguments
    """
    currentProcessGet(path)    
    process_folders = list(ProcessPathStorage.keys())[:nfirst]
    IncluiDocumentosSEI_list(sei, wpage, process_folders, **kwargs)
