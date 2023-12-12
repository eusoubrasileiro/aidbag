import os
import pathlib
import sys
import traceback
import shutil
import json
import re 
import tqdm
from PyPDF2 import PdfReader

from aidbag.web.json import json_to_path, path_to_json

from . import estudos
from .config import config
from . import scm
from .scm.util import (
    regex_process,
    fmtPname
    )

from .scm.parsing import (
    select_fields
    )

from .sei import (
        Sei,
        Processo,
        docs_externos,
        WORK_ACTIVITY
    )
        

from .estudos.util import downloadMinuta


# Current Processes being worked on - features
# that means that workflows.py probably should be a package 
# with this being another .py 

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
    process_folders = []
    paths = path.glob('*') 
    if 'time' in sort:
        paths = sorted(paths, key=os.path.getmtime)[::-1]        
    elif 'name' in sort:
        paths = sorted(paths)   
    for cur_path in paths: # remove what is NOT a process folder
        if regex_process.search(str(cur_path)) and cur_path.is_dir():
            process_folders.append(cur_path.absolute())   
            ProcessPathStorage.update({ scm.fmtPname(str(cur_path)) : cur_path.absolute()})            
    with open(config['wf_processpath_json'], "w") as f: # Serialize data into file
        json.dump(ProcessPathStorage, f, default=path_to_json)
    return ProcessPathStorage
    
    
def ProcessManagerFromHtml(path=None):    
    """fill in `scm.ProcessManager` using html from folders of processes"""    
    if not path:
        path = pathlib.Path(config['processos_path']).joinpath("Concluidos")    
    currentProcessGet(path)
    scm.ProcessManager.fromHtmls(ProcessPathStorage.values())
    

def folder_process(process_str):
    """get folder name used to store a process from NUP or whatever other form like 
    '48054.831282/2021-23' is '831282-2021'
    """
    return '-'.join(scm.numberyearPname(process_str))

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
    process_str = scm.fmtPname(process_str) # just to make sure it is unique
    dest_path =  pathlib.Path(rootpath).joinpath(dest_folder).joinpath(folder_process(process_str)).resolve() # resolve, solves "..\" to an absolute path 
    shutil.move(ProcessPathStorage[process_str].absolute(), dest_path)    
    if delpath: 
        del ProcessPathStorage[process_str]
    else:
        ProcessPathStorage[process_str] = dest_path
    with open(config['wf_processpath_json'], "w") as f: # Serialize 
        json.dump(ProcessPathStorage, f, default=path_to_json)

    
def readPdfText(filename):
    reader = PdfReader(filename)   
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    return text  
    
    
__debugging__ = False


def EstudoBatchRun(wpage, processos, tipo='interferencia', verbose=False, overwrite=False):
    """
    * tipo : str
        'interferencia' - Analise de Requerimento de Pesquisa  
        'opção'- Analise de Opcao de Area 
      
    TODO?
    - Analise de Formulario 1
    """
    succeed_NUPs = [] # suceed 
    failed_NUPS = [] # failed
    estudo = None
    for processo in tqdm.tqdm(processos):        
        try:            
            if tipo == 'interferencia':
                estudo = estudos.Interferencia.make(wpage, processo, verbose=verbose, overwrite=overwrite)   
                proc = estudo.processo              
            elif tipo == 'opção':
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

def editalTipo(obj):
    tipo = obj['tipo'].lower()  
    if 'leilão' in tipo:
        return 'Leilão'
    elif 'oferta' in tipo:                
        return 'Oferta Pública' 
    return None

def dispDadSon(name, infer=True, areatol=0.1):
    """
    return 'dad' and 'son' from name
    * infer: bool (defaul True)
        infer from area-fase
    * areatol: float (default 0.1)
        tolerance area in heactare to found process 
        if infer=True
    """
    def dispSearch(name):
        """
        Try to infer based on search on 
            * Same área 
            * Fase name: disponibilidade/leilão/oferta
        Search for son-dad (or vice-versa) relation leilão or oferta pública.
            Get first son with tipo leilão or oferta publica, when multiple                        
            get 1'st 'son' by poligon matching area on the list and edital/oferta tipo
        return standard name or None
        """   
        root = scm.ProcessManager[name]
        found = False
        for ass_name, attrs in scm.ProcessManager[name]['associados'].items():            
            # print('associdado: ', ass_name, attrs, file=sys.stdout)
            Obj = attrs['obj']
            if not 'poligon' in Obj: #ignore 
                continue 
            areadiff = abs(root['poligon']['area']-Obj['poligon']['area'])                        
            edital_tipo = editalTipo(Obj)
            if areadiff <= areatol and edital_tipo is not None:
                found = ass_name
                break # found    
        if not found:
            print('associdados: ', scm.ProcessManager[name]['associados'], file=sys.stdout)
            raise Exception(f'`dispSearch` did not found son-dad from {name}')                
        return found
    p = scm.ProcessManager[scm.fmtPname(name)]
    nparents = len(p['parents'])
    nsons = len(p['sons'])
    if nparents > 1 or nsons > 1:        
        if infer:
            print(f"`dispDadSon` Infering from area-fase {name}", file=sys.stderr)
        # Mais de um associado! Àrea Menor no Leilão? Advindo de Disponibilidade?
        if nsons == 1:
            son = p['sons'][0]
            # search for parent 
            dad = dispSearch(son)
        elif nparents == 1:
            # search for son
            dad = p['dad'][0]
            son = dispSearch(dad)
        else: 
            raise Exception(f'Mais de 1 pai e 1 filho at once {name}')                
    if nparents:
        son, dad = name, p['parents'][0]           
    elif nsons:
        son, dad = p['sons'][0], name 
    return dad, son 

def dispGetNUP(processo, dad=False):
    """get disponibilidade 'dad' or 'son' if dad=False (default)"""    
    dad, son = dispDadSon(processo.name)
    if dad:
        return scm.ProcessManager[dad]['NUP'] 
    return scm.ProcessManager[son]['NUP']  


def inferWork(process, folder=None):
    """
    From Processo object and work-folder try to infer the work and docs to create or add.
    
    returns dict with lots of infos key,value pairs    
    """
    infos = {}   

    infos['pdf_interferencia'] = None
    infos['pdf_adicional'] = None 
    infos['nome_assinatura'] = config['sei']['nome_assinatura']

    if folder is not None:
        # search/parse local folder
        # Estudo de Interferência deve chamar 'R.pdf' glob.glob("R*.pdf")[0] seja o primeiro
        pdf_interferencia = [ file for file in folder.glob("R*.pdf") ]
        # turn empty list to None
        infos['pdf_interferencia'] = pdf_interferencia[0] if pdf_interferencia else None
        # search/parse process object
        if infos['pdf_interferencia']:
            pdf_interferencia_text = readPdfText(infos['pdf_interferencia'].absolute())
            if '(Áreas de Bloqueio)' in  pdf_interferencia_text:
                print(f" { process['NUP'] } com bloqueio ",file=sys.stderr)
                # this is not enough - bloqueio provisório é o que importa              
            if 'ENGLOBAMENTO' in pdf_interferencia_text:
                infos['interferencia'] = 'ok' 
            else:
                area_text="PORCENTAGEM ENTRE ESTA ÁREA E A ÁREA ORIGINAL DO PROCESSO:" # para cada area poligonal 
                count = pdf_interferencia_text.count(area_text)            
                infos['areas'] = {'count' : count}
                infos['areas'] = {'perc' : []}
                if count == 0:
                    infos['interferencia'] = 'total'
                elif count > 0: # só uma área
                    if count == 1:
                        infos['interferencia'] = 'ok'
                    if count > 1:
                        infos['interferencia'] = 'opção'
                    percs = re.findall(f"(?<={area_text}) +([\d,]+)", pdf_interferencia_text)
                    percs = [ float(x.replace(',', '.')) for x in percs ]  
                    infos['areas']['perc'] = percs                 
        else:
            RuntimeError('Nao encontrou pdf R*.pdf')

        if 'ok' in infos['interferencia']:                
            infos['pdf_adicional'] = folder / "minuta.pdf"
        

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
    if __debugging__:
        print(infos)              
    return infos 


def IncluiDocumentosSEI(sei, process_name, wpage, activity=None, usefolder=False,
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
        Like only writting a 'Nota Técnica'.
        
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

    process_name = fmtPname(process_name)         
    if usefolder:  # needs folder docs and information  
        process = scm.ProcessManager[process_name]  
        if process_name not in ProcessPathStorage:     
            print(f"Process {process_name} not found in ProcessPathStorage")
        info = inferWork(process, ProcessPathStorage[process_name])       
        if not activity:        
            activity = info['work'] # get from infer
    else: # Only writes on SEI (don't need folder and pdf's)
        if process_name not in scm.ProcessManager:
            scm.ProcessManager.GetorCreate(process_name, wpage, task=scm.SCM_SEARCH.BASICOS)
        process = scm.ProcessManager[process_name]  
        info = inferWork(process, None) # no folder!
        psei = Processo.fromSei(sei, process['NUP'])  
        psei.insereNotaTecnicaRequerimento("custom", info)    
        psei.insereMarcador(config['sei']['marcador_default'])
        psei.atribuir(config['sei']['atribuir_default'])
        # should also close the openned text window - going to previous state
        psei.closeOtherWindows()        
        if verbose:
            print(process['NUP'])     
        return  

    if verbose and __debugging__:
        process_folder = ProcessPathStorage[process_name]
        if process_folder:
            print("Main path: ", process_folder.parent)     
            print("Process path: ", process_folder.absolute())
            print("Current dir: ", os.getcwd())
        print(f"activity {activity} \n info dict {info}")         

    if not activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL_DAD:
        psei = Processo.fromSei(sei, process['NUP'])            
        # inclui vários documentos, se desnecessário é só apagar
        # Inclui termo de abertura de processo eletronico se data < 2020 (protocolo digital nov/2019)
        if termo_abertura and process['data_protocolo'].year < 2020:  
            psei.InsereTermoAberturaProcessoEletronico()    
        
    if activity in WORK_ACTIVITY.REQUERIMENTO_GENERICO:
        # Inclui Estudo Interferência pdf como Doc Externo no SEI
        psei.insereDocumentoExterno(0, str(info['pdf_interferencia'].absolute()))                    
        if activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL:
            if not info['pdf_adicional'].exists():
                downloadMinuta(wpage, process.name, 
                        str(info['pdf_adicional'].absolute()), info['minuta']['code'])
            # guarantee to insert an empty in any case
            pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
            psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional)                        
            psei.insereNotaTecnicaRequerimento("edital_son", info)            
        elif activity in WORK_ACTIVITY.REQUERIMENTO_GENERICO_NOT_EDITAL:  
            if 'total' in info['interferencia']:
                psei.insereNotaTecnicaRequerimento("interferência_total", info)           
            elif 'opção' in info['interferencia']:
                psei.insereNotaTecnicaRequerimento("opção", info)                            
            elif 'ok' in info['interferencia']:                
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
        psei.insereDocumentoExterno(0, str(info['pdf_interferencia'].absolute())) 
        if 'ok' in info['interferencia']:                
            if not info['pdf_adicional'].exists():
                downloadMinuta(wpage, process.name, 
                                str(info['pdf_adicional'].absolute()), info['minuta']['code'])
            # guarantee to insert an empty in any case
            pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
            psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional) 
    elif activity in WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento                
        # InsereDocumentoExternoSEI(sei, nup, 3, pdf_interferencia) # estudo opção
        # InsereDocumentoExternoSEI(sei, nup, 1, pdf_adicional)  # minuta alvará
        # IncluiDespacho(sei, nup, 13)  # despacho  análise de plano alvará
        raise NotImplementedError() 
    elif activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL_DAD:
        # doesn't matter if son or dad was passed, here it's sorted!
        dad, son = dispDadSon(process_name)
        dad, son = scm.ProcessManager[dad], scm.ProcessManager[son]     
        # this is where we will put documents  
        psei = Processo.fromSei(sei, dad['NUP']) 
        # calculate again: check in case area was not checked by infer method
        areadiff = dad['poligon']['area']-son['poligon']['area']
        # SOMETIMES it'll fail before comming here, when son not found
        # TODO deal with more participants on edital                
        if areadiff > 0.1: # compare areas if difference > 0.1 ha stop! - not same area
            raise NotImplementedError(f"Not same Area! dad {dad['poligon']['area']:.2f} ha son {son['poligon']['area']:.2f} ha")
        psei.insereNotaTecnicaRequerimento("edital_dad", info, edital=editalTipo(son), 
                            processo_filho=son['NUP'])
        process = dad # this is what was done


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
