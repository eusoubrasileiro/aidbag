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
        SEI_DOCS
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

def currentProcessGet(path=None, sort='name', clear=False):
    """
    Return dict of processes paths currently on work folder.
    Update `ProcessPathStorage` dict with process names and paths.
        
    * sort:
        to sort glob result by 
        'time' modification time recent modifications first
        'name' sort by name 
        
    * return: list [ pathlib.Path's ...]
        current process folders working on from default careas working env.
        
    * clear : default False
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
        if scm.util.regex_process.search(str(cur_path)) and cur_path.is_dir():
            process_folders.append(cur_path.absolute())   
            ProcessPathStorage.update({ scm.fmtPname(str(cur_path)) : str(cur_path.absolute())})        
    with open(config['wf_processpath_json'], "w") as f: # Serialize data into file
        json.dump(ProcessPathStorage, f)
    return ProcessPathStorage


def currentProcessFromHtml(path='Processos', clear=True):
    """load `scm.ProcessStorage` using `Processo.fromHtml` from paths in `ProcessPathStorage`"""
    cwd = os.getcwd() # save path state
    process_path = os.path.join(config['secor_path'], path) 
    if clear:
        scm.ProcessStorage.clear()
    for _, process_path in tqdm.tqdm(ProcessPathStorage.items()):    
        scm.Processo.fromHtml(process_path, verbose=False)
    os.chdir(cwd) # restore path state 
    

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


def EstudoBatchRun(wpage, processos, tipo='interferencia', verbose=False):
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
                estudo = estudos.Interferencia.make(wpage, processo, verbose=verbose)   
                proc = estudo.processo              
            elif tipo == 'opção':
                proc = scm.Processo.Get(processo, wpage, dados=scm.SCM_SEARCH.BASICOS,verbose=False)
                proc.salvaDadosBasicosHtml(config.processPathSecor(proc))
        except Exception as e:  # too generic is masking errors that I don't care for??             
            print("Process {:} Exception: ".format(processo), traceback.format_exc(), file=sys.stderr)                       
            failed_NUPS.append(scm.ProcessStorage[scm.fmtPname(processo)]['NUP'])            
        else:
            succeed_NUPs.append(proc['NUP'])  
    # print all NUPS
    if verbose:
        print('SEI NUPs sucess:')
        for nup in succeed_NUPs:
            print(nup)
        print('SEI NUPs failed:')
        for nup in failed_NUPS:
            print(nup)
    return succeed_NUPs, failed_NUPS



def IncluiDocumentosSEIFolder(sei, process_folder, wpage, infer=True, sei_doc=None, 
        empty=False, verbose=True):
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

    * infer : True 
        infer from tipo and fase dados basicos processo 
        documents to add 
    
    * sei_doc : enum 
        Enum `SEI_DOCS`

    """
    if type(process_folder) is str: 
        process_folder = pathlib.Path(config['processos_path']).joinpath(process_folder)

    os.chdir(process_folder.absolute()) # enter on process folder
    if verbose and __debugging__:
        print("Main path: ", process_folder.parent)     
        print("Process path: ", process_folder.absolute())
        print("Current dir: ", os.getcwd())

    # get nup, fase, tipo etc... 
    process = scm.Processo.fromHtml(verbose=False) # default from current folder

    pdf_adicional = None
    pdf_interferencia = None            

    if not empty: # busca pdfs e adiciona só os existentes
        # Estudo de Interferência deve chamar 'R.pdf' glob.glob("R*.pdf")[0] seja o primeiro
        pdf_interferencia = [ file for file in process_folder.glob("R*.pdf") ]
        # turn empty list to None
        pdf_interferencia = pdf_interferencia[0] if pdf_interferencia else None
        if pdf_interferencia:                
            pdf_interferencia_text = readPdfText(pdf_interferencia.absolute())
            area_text="PORCENTAGEM ENTRE ESTA ÁREA E A ÁREA ORIGINAL DO PROCESSO:" # para cada area poligonal 
            count_areas = pdf_interferencia_text.count(area_text)            
            if count_areas == 1: # só uma área
                p_area = re.findall(f"(?<={area_text}) +([\d,]+)", pdf_interferencia_text)
                p_area = float(p_area[0].replace(',','.'))
                # pdf minuta alvará, licenciamento etc... 
                pdf_adicional = pathlib.Path("minuta.pdf")
                if not pdf_adicional.exists():
                    downloadMinuta(wpage, process.name, "minuta.pdf") # use current folder to save pdf 
                    pdf_adicional = pathlib.Path("minuta.pdf") # chamar-se-a minuta.pdf 
                    pdf_adicional = pdf_adicional.absolute()
                    readPdfText(pdf_adicional)  
            elif count_areas > 1: # multiplas áreas opção 
                p_area = ['33,222', '22,120', '0,153'] # exemple TODO implement!
                pdf_adicional = None  
            elif count_areas == 0: # interferência total 
                p_area = -1                
        else:
            RuntimeError('Nao encontrou pdf R*.pdf')
    
    psei = Processo.fromSei(sei, process['NUP'])    
    if verbose and __debugging__:
        print(f"percentage_area {p_area}")
        print(f"pdf_interferencia {pdf_interferencia}")
        print(f"pdf_adicional {pdf_adicional}")
        print(f"tipo {process['tipo'].lower()}")
        print(f"fase {process['fase'].lower()}")        
        
    # inclui vários documentos, se desnecessário é só apagar
    # Inclui termo de abertura de processo eletronico se data < 2020 (protocolo digital nov/2019)
    # to avoid placing IncluiTermoAberturaPE on processos puro digitais 
    if process['data_protocolo'].year < 2020:  
        psei.InsereTermoAberturaProcessoEletronico(process['NUP'])

    if infer: # infer from tipo, fase 
        processo_tipo=None
        if 'requerimento' in process['tipo'].lower(): 
            if 'requerimento de lavra' in process['fase'].lower():
                raise NotImplementedError() 
                #Formulário 1            
            if 'requerimento de pesquisa' in process['fase'].lower():
                processo_tipo = 'pesquisa' 
            elif 'requerimento de licenciamento' in process['fase'].lower():
                processo_tipo = 'licenciamento'                    
            # Inclui Estudo pdf como Doc Externo no SEI
            psei.insereDocumentoExterno(0, str(pdf_interferencia.absolute()))
            if pdf_adicional is None:
                if p_area == -1:                    
                    # Recomenda interferencia total
                    psei.insereNotaTecnicaRequerimento("interferência_total", tipo=processo_tipo) 
                else:
                    # Recomenda interferencia total
                    psei.insereNotaTecnicaRequerimento("opção", tipo=processo_tipo)                          
            else:
                psei.insereDocumentoExterno(1, str(pdf_adicional.absolute()))   
                if p_area < 96.0: # > 4% change notificar 
                    psei.insereNotaTecnicaRequerimento("com_redução", tipo=processo_tipo, # com notificação titular
                            area_porcentagem=str(p_area).replace('.',',')) 
                else:
                    psei.insereNotaTecnicaRequerimento("sem_redução", tipo=processo_tipo) 
                    # Recomenda Só análise de plano s/ notificação titular (mais comum)
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
    else: # dont infer, especify explicitly        
        if sei_doc == SEI_DOCS.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento                
            # InsereDocumentoExternoSEI(sei, nup, 3, pdf_interferencia) # estudo opção
            # InsereDocumentoExternoSEI(sei, nup, 1, pdf_adicional)  # minuta alvará
            # IncluiDespacho(sei, nup, 13)  # despacho  análise de plano alvará
            raise NotImplementedError() 
    psei.insereMarcador(config['sei']['marcador_default'])
    psei.atribuir(config['sei']['atribuir_default'])
    # should also close the openned text window - going to previous state
    psei.closeOtherWindows()
    
    os.chdir(process_folder.parent) # restore original path , to not lock the folder-path
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
