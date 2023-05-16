import glob
import os
import pathlib
import sys
import traceback
import shutil
import json
import re 
import tqdm
from PyPDF2 import PdfReader

from . import estudos
from .config import config
from . import scm
from .scm.util import regex_process

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
"""stores paths for current process being worked on """

# try: # Read paths for current process being worked on from file 
#     with open(config['wf_processpath_json'], "r") as f:
#         ProcessPathStorage = json.load(f)
# except:
#     pass 

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
    if not path:
        path = config['processos_path']        
    path = pathlib.Path(path)    
    process_folders = []
    paths = path.glob('*') 
    if 'time' in sort:
        paths = sorted(paths, key=os.path.getmtime)[::-1]        
    elif 'name' in sort:
        paths = sorted(paths)   
    if clear: # ignore json file 
        ProcessPathStorage.clear()
    for cur_path in paths: # remove what is NOT a process folder
        if regex_process.search(str(cur_path)) and cur_path.is_dir():
            process_folders.append(cur_path.absolute())   
            ProcessPathStorage.update({ scm.fmtPname(str(cur_path)) : str(cur_path.absolute())})        
    with open(config['wf_processpath_json'], "w") as f: # Serialize data into file
        json.dump(ProcessPathStorage, f)
    return ProcessPathStorage
    
    
def ProcessStorageFromHtml(path=None):    
    """fill in `scm.ProcessStorage` using html from folders of processes"""    
    if not path:
        path = pathlib.Path(config['processos_path']).joinpath("Concluidos")    
    currentProcessGet(path)
    scm.ProcessStorage.fromHtmls(ProcessPathStorage.values())
    scm.ProcessStorage.toJSONfile()
    

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
    shutil.move(ProcessPathStorage[process_str], dest_path)    
    if delpath: 
        del ProcessPathStorage[process_str]
    else:
        ProcessPathStorage[process_str] = str(dest_path)
    with open(config['wf_processpath_json'], "w") as f: # Serialize 
        json.dump(ProcessPathStorage, f)

    
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
                proc = scm.Processo.Get(processo, wpage, dados=scm.SCM_SEARCH.BASICOS_POLIGONAL, verbose=verbose)
                proc.salvaPageScmHtml(config.processPathSecor(proc), 'basic', overwrite)
        except estudos.DownloadInterferenciaFailed as e:            
            failed_NUPS.append((scm.ProcessStorage[scm.fmtPname(processo)]['NUP'], f" Message: {str(e)}"))                       
        except Exception as e:              
            print(f"Process {processo} Exception: {traceback.format_exc()}", file=sys.stderr)                       
            failed_NUPS.append((scm.ProcessStorage[scm.fmtPname(processo)]['NUP'],''))            
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


def inferWork(process, folder):
    """
    From Processo object and work-folder try to infer the work and docs to create or add.
    
    returns dict with lots of infos key,value pairs    
    """
    infos = {}    
    # search/parse local folder
    # Estudo de Interferência deve chamar 'R.pdf' glob.glob("R*.pdf")[0] seja o primeiro
    pdf_interferencia = [ file for file in folder.glob("R*.pdf") ]
    # turn empty list to None
    infos['pdf_interferencia'] = pdf_interferencia[0] if pdf_interferencia else None
    infos['pdf_adicional'] = None
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
        
    def editalGetDadNUP(processo):
        if len(process['associados']) > 1:
            raise Exception('Something wrong! Mais de um associado! Àrea Menor no Leilão? ', processo.name)   
        return scm.ProcessStorage[processo['parents'][0]]['NUP']         
   
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
                  infos['edital'] = {'tipo' : 'Leilão', 'pai' : editalGetDadNUP(process)}                  
            if 'pública' in process['tipo'].lower():   
                  infos['work'] = WORK_ACTIVITY.REQUERIMENTO_EDITAL    
                  infos['edital'] = {'tipo' : 'Oferta Pública', 'pai' : editalGetDadNUP(process)}    
    if __debugging__:
        print(infos)              
    return infos 
    
    

def IncluiDocumentosSEIFolder(sei, process_folder, wpage, activity=None, 
        empty=False, termo_abertura=False, verbose=True):
    """
    Inclui process documents from specified folder:
    `__secor_path__\\path\\process_folder`
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    * sei : class
        selenium chrome webdriver instance
        
    * process_folder: string or pathlib.Path 
        string name of process folder where documentos are placed
        eg. 832125-2005 (MUST use name xxxxxx-xxx format)        
        or 
        pathlib.Path for process folder 

    * wpage: wPageNtlm 
        baixa NUP e outros from html salvo
        faz download da minuta 

    * verbose: True
        avisa ausência de pdfs, quando cria documentos sem anexos
        
    * empty : True
        cria documentos sem anexos

    * activity : None or Enum `WORK_ACTIVITY` 
        If None infer from tipo and fase dados basicos processo 
        documents to add. Otherwise specify explicitly what to do.
        
    * termo_abertura: False
        To add for process older than < 2020
                
    """
    if type(process_folder) is str: 
        process_folder = pathlib.Path(config['processos_path']).joinpath(process_folder)

    # get process from folder name    
    name = scm.findfmtPnames(process_folder.absolute().stem)[0]
    process = scm.ProcessStorage[name]
        
    info = inferWork(process, process_folder)

    if verbose and __debugging__:
        print("Main path: ", process_folder.parent)     
        print("Process path: ", process_folder.absolute())
        print("Current dir: ", os.getcwd())
        print(f"activity {activity} \n info dict {info}")      
   
    psei = Processo.fromSei(sei, process['NUP'])            
    # inclui vários documentos, se desnecessário é só apagar
    # Inclui termo de abertura de processo eletronico se data < 2020 (protocolo digital nov/2019)
    if termo_abertura and process['data_protocolo'].year < 2020:  
        psei.InsereTermoAberturaProcessoEletronico()        
    
    if not activity:
        activity = info['work'] # get from infer
        
    if activity in WORK_ACTIVITY.REQUERIMENTO_GENERICO:
        # Inclui Estudo Interferência pdf como Doc Externo no SEI
        psei.insereDocumentoExterno(0, str(info['pdf_interferencia'].absolute()))                    
        if activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL:
            if 'ok' in info['interferencia']:                
                info['pdf_adicional'] = process_folder / "minuta.pdf"
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
                info['pdf_adicional'] = process_folder / "minuta.pdf"
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
            info['pdf_adicional'] = process_folder / "minuta.pdf"
            if not info['pdf_adicional'].exists():
                downloadMinuta(wpage, process.name, 
                                str(info['pdf_adicional'].absolute()), info['minuta']['code'])
            # guarantee to insert an empty in any case
            pdf_adicional = str(info['pdf_adicional'].absolute()) if info['pdf_adicional'].exists() else None 
            psei.insereDocumentoExterno(info['minuta']['doc_ext'], pdf_adicional)
    #psei.insereNotaTecnicaRequerimento("interferência_total", tipo=processo_tipo)     
    #raise NotImplementedError()
    # else:
    #     # tipo - requerimento de cessão parcial ou outros
    #     if 'lavra' in fase.lower(): # minuta portaria de Lavra
    #         # parecer de retificação de alvará
    #         #IncluiParecer(sei, nup, 0)
    #         # Inclui Estudo pdf como Doc Externo no SEI
    #         #InsereDocumentoExternoSEI(sei, nup, 0, pdf_interferencia)
    #         #InsereDocumentoExternoSEI(sei, nup, 4, pdf_adicional)
    #         # Adicionado manualmente depois o PDF gerado
    #         # com links p/ SEI
    #         #InsereDocumentoExternoSEI(sei, nup, 6, None)
    #         #InsereDeclaracao(sei, nup, 14) # 14 Informe: Requerimento de Lavra Formulario 1 realizado
    #         # 15 - xxxxxxxx
    #         #IncluiDespacho(sei, nup, 15, 
    #         #    setor=u"ccccxxxxx") 
    #         # 16 - xxxxxxx
    #         #IncluiDespacho(sei, nup, 16)
    #         # IncluiDespacho(sei, NUP, 9) # - Recomenda c/ retificação de alvará
    #         raise NotImplementedError() 
    #     pass    
    elif activity in WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento                
        # InsereDocumentoExternoSEI(sei, nup, 3, pdf_interferencia) # estudo opção
        # InsereDocumentoExternoSEI(sei, nup, 1, pdf_adicional)  # minuta alvará
        # IncluiDespacho(sei, nup, 13)  # despacho  análise de plano alvará
        raise NotImplementedError() 
    elif activity in WORK_ACTIVITY.REQUERIMENTO_EDITAL_DAD:
        # Possible to get first son with tipo leilão or oferta publica, when multiple                        
        if len(process['associados']) > 1:
            print('Mais de um associado! Àrea Menor no Leilão? Something wrong?', process.name)
        # get 'son' by poligon matching area or first on the list 
        sons = []
        edital_tipo = None 
        for name, attrs in scm.ProcessStorage[name].associados.items():
            son = attrs['obj']
            tipo = son['tipo'].lower()
            if 'leilão' in tipo:
                sons.append([son['NUP'], son['poligon']['area'], abs(process['poligon']['area']-son['poligon']['area'])])     
                edital_tipo = 'Leilão'           
            elif 'oferta' in tipo:
                sons.append([son['NUP'], son['poligon']['area'], abs(process['poligon']['area']-son['poligon']['area'])])
                edital_tipo = 'Oferta Pública'
        if not sons: # could not find son or sons 
            raise Exception('Something wrong! Não é advindo de edital!', process.name)
        # TODO deal with more participants on edital                
        if sons[0] > 0.1: # # compare areas if difference > 0.1 ha stop! - not same area
           raise NotImplemented('Not same Area!')            
        psei.insereNotaTecnicaRequerimento("edital_dad", info, edital=edital_tipo, 
                            processo_filho=sons[0][0])#['NUP']

    psei.insereMarcador(config['sei']['marcador_default'])
    psei.atribuir(config['sei']['atribuir_default'])
    # should also close the openned text window - going to previous state
    psei.closeOtherWindows()    
    
    if verbose:
        print(process['NUP'])


def IncluiDocumentosSEIFolders(sei, wpage, process_folders, **kwargs):
    """
    Wrapper for `IncluiDocumentosSEIFolder` 
    
    Aditional args should be passed as keyword arguments
    """
    for process_folder in process_folders:
        try:
            IncluiDocumentosSEIFolder(sei, process_folder, wpage, **kwargs)
        except Exception:
            print("Process {:} Exception: ".format(process_folder), traceback.format_exc(), file=sys.stderr)           
            continue        


def IncluiDocumentosSEIFoldersFirstN(sei, wpage, nfirst=1, path=None, **kwargs):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI. Follow order of glob(*) 
    
    Wrapper for `IncluiDocumentosSEIFolder` 
    
    Aditional args should be passed as keyword arguments
    """
    currentProcessGet(path)    
    process_folders = list(ProcessPathStorage.values())[:nfirst]
    IncluiDocumentosSEIFolders(sei, wpage, process_folders, **kwargs)
