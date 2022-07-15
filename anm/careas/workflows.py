import tqdm
import glob
import os
import sys
import traceback
import shutil
import json
import re 
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from . import estudos
from . import scm
from ...web import htmlscrap
from .SEI import *
from .scm.parsing import (
    select_fields
    )


from .constants import (
    mcodigos,
    docs_externos,
    config,    
    SEI_DOCS
    )

from .scm.util import regex_process

from aidbag.anm.careas import constants

# Current Processes being worked on - features
# tha means that workflows.py probably should be a package 
# with this being another .py 

ProcessPathStorage = {} # stores paths for current process being worked on 
processpath_json = os.path.join(os.path.join(config['secor_path'],"Processos","processes_path.json"))

try: # Read paths for current process being worked on from file 
    with open(processpath_json, "r") as f:
        ProcessPathStorage = json.load(f)
except:
    pass 

def currentProcessGet(path='Processos', clear=False):
    """update `ProcessPathStorage` dict with process names and paths
    * clear : clear `ProcessPathStorage` before updating (ignore json file)"""
    cwd = os.getcwd() # save path state
    process_path = os.path.join(config['secor_path'], path) 
    os.chdir(process_path)
    if clear: # ignore json file 
        ProcessPathStorage.clear()
    files_folders = glob.glob('*')    
    for cur_path in files_folders: # remove what is NOT a process folder
        if regex_process.search(cur_path) and os.path.isdir(cur_path):
            ProcessPathStorage.update({ scm.fmtPname(cur_path) : os.path.join(process_path, cur_path)})    
    with open(processpath_json, "w") as f: # Serialize data into file
        json.dump(ProcessPathStorage, f)
    os.chdir(cwd) # restore path state 


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
    dest_path =  Path(rootpath).joinpath(dest_folder).joinpath(folder_process(process_str)).resolve() # resolve, solves "..\" to an absolute path 
    shutil.move(ProcessPathStorage[process_str], dest_path)    
    if delpath: 
        del ProcessPathStorage[process_str]
    else:
        ProcessPathStorage[process_str] = str(dest_path)
    with open(processpath_json, "w") as f: # Serialize 
        json.dump(ProcessPathStorage, f)



from PyPDF2 import PdfReader
    
def readPdfText(filename):
    reader = PdfReader(filename)   
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    return text  
    
    
__debugging__ = False

def IncluiDocumentoExternoSEI(sei, ProcessoNUP, doc=0, pdf_path=None):
    """
    Inclui pdf como documento externo no SEI

    doc :
        0  - Estudo      - 'de Retirada de Interferência'
        1  - Minuta      - 'Pré de Alvará'
        2  - Minuta      - 'de Licenciamento'
        3  - Estudo      - 'de Opção'
        4  - Minuta      - 'de Portaria de Lavra'
        5  - Minuta      - 'de Permissão de Lavra Garimpeira'
        6  - Formulario  - '1 Análise de Requerimento de Lavra'

    pdf_path :
        if None cria sem anexo
    """
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(0) # Inclui Externo
    # Preenchendo
    sei.driver.find_element(By.ID,'selSerie').send_keys(docs_externos[doc]['tipo']) # Tipo de Documento
    # Data do Documento
    sei.driver.find_element(By.ID,'txtDataElaboracao').send_keys(datetime.today().strftime('%d/%m/%Y')) # put TODAY
    sei.driver.find_element(By.ID,'txtNumero').send_keys(docs_externos[doc]['desc']) # Nome na Arvore
    sei.driver.find_element(By.ID,'optNato').click() #   Nato-digital
    sei.driver.find_element(By.ID,'lblPublico').click() # Publico
    if pdf_path is not None: # existe documento para anexar
        file = sei.driver.find_element(By.ID,'filArquivo') # Upload PDF
        file.send_keys(pdf_path)
    # save = sei.driver.find_element(By.ID,'btnSalvar')
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

def IncluiDeclaracao(sei, ProcessoNUP, idxcodigo):
    """
    Inclui Declaração - por index código modelo favorito
    """
    mcodigo = mcodigos[idxcodigo]
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(4) # modelo favorito
    sei.driver.find_element(By.ID,'lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    sei.driver.find_element(By.ID,'txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    sei.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

#Divisão de Fiscalização da Mineração de Não Metálicos (DFMNM-MG)
#Setor de Controle e Registro (SECOR-MG)
def IncluiDespacho(sei, ProcessoNUP, idxcodigo, 
    setor=u"Setor de Controle e Registro (SECOR-MG)", 
    assinar=False):
    """
    Inclui Despacho - por index código
    """
    mcodigo = mcodigos[idxcodigo]
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(1) # Despacho
    sei.driver.find_element(By.ID,'lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    sei.driver.find_element(By.ID,'txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    sei.driver.find_element(By.ID,'txtDestinatario').send_keys(setor)
    destinatario_set = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'divInfraAjaxtxtDestinatario')))
    destinatario_set.click() # wait a little pop-up show up to click or send ENTER
    # sei.driver.find_element(By.ID,'txtDestinatario').send_keys(Keys.ENTER) #ENTER
    sei.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

def EscreveDespacho(sei, ProcessoNUP, texto):
    """
    Escreve Despacho no `ProcessoNUP` usando string `texto`
    """
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(1) # Despacho
    sei.driver.find_element(By.ID,'txtDestinatario').send_keys(u"Setor de Controle e Registro (SECOR-MG)")
    destinatario_set = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'divInfraAjaxtxtDestinatario')))
    destinatario_set.click() # wait a little pop-up show up to click or send ENTER
    # sei.driver.find_element(By.ID,'txtDestinatario').send_keys(Keys.ENTER) #ENTER
    sei.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try : # may take a long time to lood the pop up
        # wait 10 seconds
        alert = wait(sei.driver, 10).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass

    wait(sei.driver, 10).until(expected_conditions.number_of_windows_to_be(2))
    # text window now open, but list of handles is not ordered
    textwindow = [hnd for hnd in sei.driver.window_handles if hnd != sei.mainwindow ][0]
    sei.driver.switch_to.window(textwindow) # go to text pop up window
    sei.driver.switch_to.default_content() # go to parent main document
    
    # this is the one that can take the longest time of ALL
    wait(sei.driver, 20).until( # then go to frame of input text 
        expected_conditions.frame_to_be_available_and_switch_to_it(
        (By.CSS_SELECTOR,"iframe[aria-describedby='cke_244']")))

    inputtext = sei.driver.find_element(By.CSS_SELECTOR, 'body[contenteditable="true"]')

    inputtext.clear()
    for line in texto.split('\n'):  # split by lines
        inputtext.send_keys(line) # type in each line - must use keys like bellow
        inputtext.send_keys(Keys.ENTER) # create a new line
        #inputtext.send_keys(Keys.BACKSPACE) # go back to its beginning

    sei.driver.switch_to.default_content() # go to parent main iframe document    
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'cke_202')))
    save.click() 
    # to make sure it has finnished saving we have to wait until 
    # 1. save button becames visible inactive and 
    wait(sei.driver, 10).until(expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, 
        "#cke_202[class='cke_button cke_button__save cke_button_disabled']")))    
    # 2. any other button becomes clickable again (like button assinar)
    wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, 
        "#cke_204[class='cke_button cke_button__assinatura cke_button_off']")))    
    # than we can close
    sei.driver.close() # close text window

    wait(sei.driver, 10).until(expected_conditions.number_of_windows_to_be(1))
    sei.driver.switch_to.window(sei.mainwindow) # go back to main window
    sei.driver.switch_to.default_content() # go to parent main document
    # to not stale the window have to go to it again to the following task
    sei.Pesquisa(ProcessoNUP) 

def IncluiParecer(sei, ProcessoNUP, idxcodigo=0):
    """
    Inclui Parecer
    idxcodigo : int index
        default retificaçaõ de alvará = 0
    """
    mcodigo = mcodigos[idxcodigo]
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(2) # Parecer
    sei.driver.find_element(By.ID,'lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    sei.driver.find_element(By.ID,'txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    sei.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

def IncluiTermoAberturaPE(sei, ProcessoNUP):
    """
    Inclui Termo de Abertura de Processo Eletronico
    """
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(3) # Termo de Abertura
    sei.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

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
                proc.salvaDadosBasicosHtml(constants.processPathSecor(proc))
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



def IncluiDocumentosSEIFolder(sei, process_folder, path='', infer=True, sei_doc=None, 
        empty=False, wpage=None, verbose=True):
    """
    Inclui process documents from specified folder:
    `__secor_path__\\path\\process_folder`
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    * sei : class
        selenium chrome webdriver instance
    * process_folder: string
        name of process folder where documentos are placed
        eg. 832125-2005 (MUST use name xxxxxx-xxx format)
    * path : string
        parent folder inside estudos.__secor_path__ to search
        for `process_folder`
        __secor_path__ defaults to '~\Documents\Controle_Areas'
        e.g
        path='Processos' final parent folder is
        '~\Documents\Controle_Areas\Processos'

    * wpage: wPageNtlm 
        defaul None
        na ausência de página html salva, baixa NUP diretamente

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
    cur_path = os.getcwd() # for restoring after
    main_path = os.path.join(config['secor_path'], path)
    if verbose and __debugging__:
        print("Main path: ", main_path)
    process_path = os.path.join(main_path, process_folder)
    os.chdir(process_path) # enter on process folder
    if verbose and __debugging__:
        print("Process path: ", process_path)
        print("Current dir: ", os.getcwd())

    if not empty: # busca pdfs e adiciona só os existentes
        # Estudo de Interferência deve chamar 'R.pdf' ou qualquer coisa
        # que glob.glob("R*.pdf")[0] seja o primeiro
        pdf_interferencia = glob.glob("R*.pdf")
        # turn empty list to None
        pdf_interferencia = pdf_interferencia[0] if pdf_interferencia else None
        if not pdf_interferencia is None:
            pdf_interferencia = os.path.join(process_path, pdf_interferencia)
            pdf_interferencia_text = readPdfText(pdf_interferencia)
            pct_text="PORCENTAGEM ENTRE ESTA ÁREA E A ÁREA ORIGINAL DO PROCESSO:"
            if pdf_interferencia_text.find(pct_text):
                p_area = re.findall(f"(?<={pct_text}) +([\d,]+)", pdf_interferencia_text)
                p_area = float(p_area[0].replace(',','.'))
            else: # interferência total 
                p_area = -1                
        elif verbose:
            print('Nao encontrou pdf R*.pdf', file=sys.stderr)            
        # pdf adicional Minuta de Licenciamento ou Pré Minuta de Alvará
        # deve chamar 'Imprimir.pdf'
        # ou qualquer coisa que glob.glob("Imprimir*.pdf")[0] seja o primeiro
        pdf_adicional = glob.glob("Imprimir*.pdf")
        # turn empty list to None
        pdf_adicional = pdf_adicional[0] if pdf_adicional else None
        if not pdf_adicional is None:
            pdf_adicional = os.path.join(process_path, pdf_adicional)
            pdf_adicional_text = readPdfText(pdf_adicional)    
        elif verbose:
            print('Nao encontrou pdf Imprimir*.pdf', file=sys.stderr)

    html = None
    process = scm.Processo.fromHtml(verbose=False) # default from current folder
    # get everything needed
    NUP, tipo, fase = process['NUP'], process['tipo'], process['fase']
    data_protocolo = process['data_protocolo']    
       
    if empty:
        pdf_adicional = None
        pdf_interferencia = None
    # inclui vários documentos, se desnecessário é só apagar
    # Inclui termo de abertura de processo eletronico se data < 2020 (protocolo digital nov/2019)
    # to avoid placing IncluiTermoAberturaPE on processos puro digitais 
    if data_protocolo.year < 2020:  
        IncluiTermoAberturaPE(sei, NUP)

    if infer: # infer from tipo, fase 
        if 'licen' in tipo.lower():
            # Inclui Estudo pdf como Doc Externo no SEI
            IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)
            # 2 - Minuta - 'de Licenciamento'
            IncluiDocumentoExternoSEI(sei, NUP, 2, pdf_adicional)
            IncluiDespacho(sei, NUP, 3) # - Recomenda análise de plano
        elif 'garimpeira' in tipo.lower():
            if 'requerimento' in fase.lower(): # Minuta de P. de Lavra Garimpeira
                # Inclui Estudo pdf como Doc Externo no SEI
                IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)
                IncluiDocumentoExternoSEI(sei, NUP, 5, pdf_adicional)
                IncluiDespacho(sei, NUP, 3) # - Recomenda análise de plano
        else:
            # tipo - requerimento de cessão parcial ou outros
            if 'lavra' in fase.lower(): # minuta portaria de Lavra
                # parecer de retificação de alvará
                IncluiParecer(sei, NUP, 0)
                # Inclui Estudo pdf como Doc Externo no SEI
                IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)
                IncluiDocumentoExternoSEI(sei, NUP, 4, pdf_adicional)
                # Adicionado manualmente depois o PDF gerado
                # com links p/ SEI
                IncluiDocumentoExternoSEI(sei, NUP, 6, None)
                IncluiDeclaracao(sei, NUP, 14) # 14 Informe: Requerimento de Lavra Formulario 1 realizado
                # 15 - Para DFMNM: Requerimento aguardar cunprimento de exigências
                IncluiDespacho(sei, NUP, 15, 
                    setor=u"Divisão de Fiscalização da Mineração de Não Metálicos (DFMNM-MG)") 
                # 16 - Para SECOR-MG Expedição: Requerimento de Lavra para análise
                IncluiDespacho(sei, NUP, 16)
                # IncluiDespacho(sei, NUP, 9) # - Recomenda c/ retificação de alvará
            elif 'pesquisa' in tipo.lower(): # Requerimento de Pesquisa - 1 - Minuta - 'Pré de Alvará'
                # Inclui Estudo pdf como Doc Externo no SEI
                IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)                
                if pdf_adicional is None:
                    if p_area == -1:                    
                        IncluiDespacho(sei, NUP, 2) # - Recomenda interferencia total
                    else:
                        IncluiDespacho(sei, NUP, 3) # - Recomenda opção
                else:
                    IncluiDocumentoExternoSEI(sei, NUP, 1, pdf_adicional)
                    if p_area < 96.0: # > 4% change notificar 
                        IncluiDespacho(sei, NUP, 0) # - Recomenda análise de plano c/ notificação titular
                    else:
                        IncluiDespacho(sei, NUP, 1) # - Recomenda Só análise de plano s/ notificação titular (mais comum)
        #     pass
    else: # dont infer, especify explicitly        
        if sei_doc == SEI_DOCS.REQUERIMENTO_OPCAO_ALVARA: # opção de área na fase de requerimento                
            IncluiDocumentoExternoSEI(sei, NUP, 3, pdf_interferencia) # estudo opção
            IncluiDocumentoExternoSEI(sei, NUP, 1, pdf_adicional)  # minuta alvará
            IncluiDespacho(sei, NUP, 13)  # despacho  análise de plano alvará

    sei.ProcessoAtribuir() # default elaine - better do by hand
    os.chdir(cur_path) # restore original path , to not lock the folder-path
    # should also close the openned text window - going to previous state
    sei.closeOtherWindows()
    if verbose:
        print(NUP)


def IncluiDocumentosSEIFolders(sei, process_folders, path='Processos', **kwargs):
    """
    Inclui docs. from process folders [list of process-folder-names] on SEI.  

    Wrapper for `IncluiDocumentosSEIFolder` 
    
    Aditional args should be passed as keyword arguments
    """
    for folder_name in process_folders:
        try:
            IncluiDocumentosSEIFolder(sei, folder_name, path, **kwargs)
        except Exception:
            print("Process {:} Exception: ".format(folder_name), traceback.format_exc(), file=sys.stderr)           
            continue

def IncluiDocumentosSEIFoldersFirstN(sei, nfirst=1, path='Processos', **kwargs):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI. Follow order of glob(*) 
    
    Wrapper for `IncluiDocumentosSEIFolder` 
    
    Aditional args should be passed as keyword arguments
    """
    os.chdir(os.path.join(config['secor_path'], path))
    files_folders = glob.glob('*')
    process_folders = []
    for cur_path in files_folders: # remove what is NOT a process folder
        if scm.util.regex_process.search(cur_path) and os.path.isdir(cur_path):
            process_folders.append(cur_path)
    process_folders = process_folders[:nfirst]
    IncluiDocumentosSEIFolders(sei, process_folders, path, **kwargs)
