import tqdm
import glob
import os
import sys
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from . import estudos
from . import scm
from ...web import htmlscrap
from .SEI import *

from .constants import (
    mcodigos,
    docs_externos_sei_tipo,
    docs_externos_sei_txt,
    __secor_path__
    )

def folder_process(process_str):
    """get folder name used to store a process from NUP like 
    '48054.831282/2021-23' is '831282-2021'
    """
    return '-'.join(scm.numberyearPname(process_str))


__debugging__ = False

def IncluiDocumentoExternoSEI(sei, ProcessoNUP, doc=0, pdf_path=None):
    """
    Inclui pdf como documento externo no SEI

    doc :
        0  - Estudo     - 'de Retirada de Interferência'
        1  - Minuta     - 'Pré de Alvará'
        2  - Minuta     - 'de Licenciamento'
        3  - Estudo     - 'de Opção'
        4  - Minuta     - 'de Portaria de Lavra'
        5  - Minuta     - 'de Permissão de Lavra Garimpeira'
        6 - Formulario  - '1 Análise de Requerimento de Lavra'

    pdf_path :
        if None cria sem anexo
    """
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(0) # Inclui Externo
    # Preenchendo
    sei.driver.find_element_by_id('selSerie').send_keys(docs_externos_sei_tipo[doc]) # Tipo de Documento
    # Data do Documento
    sei.driver.find_element_by_id('txtDataElaboracao').send_keys(datetime.today().strftime('%d/%m/%Y')) # put TODAY
    sei.driver.find_element_by_id('txtNumero').send_keys(docs_externos_sei_txt[doc]) # Nome na Arvore
    sei.driver.find_element_by_id('optNato').click() #   Nato-digital
    sei.driver.find_element_by_id('lblPublico').click() # Publico
    if pdf_path is not None: # existe documento para anexar
        file = sei.driver.find_element_by_id('filArquivo') # Upload PDF
        file.send_keys(pdf_path)
    # save = sei.driver.find_element_by_id('btnSalvar')
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document


def IncluiDespacho(sei, ProcessoNUP, idxcodigo):
    """
    Inclui Despacho - por index código
    """
    mcodigo = mcodigos[idxcodigo]
    sei.Pesquisa(ProcessoNUP) # Entra neste processo
    sei.ProcessoIncluiDoc(1) # Despacho
    sei.driver.find_element_by_id('lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    sei.driver.find_element_by_id('txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    sei.driver.find_element_by_id('txtDestinatario').send_keys(u"Setor de Controle e Registro (SECOR-MG)")
    destinatario_set = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'divInfraAjaxtxtDestinatario')))
    destinatario_set.click() # wait a little pop-up show up to click or send ENTER
    # sei.driver.find_element_by_id('txtDestinatario').send_keys(Keys.ENTER) #ENTER
    sei.driver.find_element_by_id('lblPublico').click() # Publico
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
    sei.driver.find_element_by_id('txtDestinatario').send_keys(u"Setor de Controle e Registro (SECOR-MG)")
    destinatario_set = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'divInfraAjaxtxtDestinatario')))
    destinatario_set.click() # wait a little pop-up show up to click or send ENTER
    # sei.driver.find_element_by_id('txtDestinatario').send_keys(Keys.ENTER) #ENTER
    sei.driver.find_element_by_id('lblPublico').click() # Publico
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

    inputtext = sei.driver.find_element_by_css_selector('body[contenteditable="true"]')

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
    sei.driver.find_element_by_id('lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    sei.driver.find_element_by_id('txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    sei.driver.find_element_by_id('lblPublico').click() # Publico
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
    sei.driver.find_element_by_id('lblPublico').click() # Publico
    save = wait(sei.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(sei.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    sei.driver.switch_to.default_content() # go back to main document

def EstudoBatchRun(wpage, processos, option=0, verbose=False):
    """
    - Analise de Requerimento de Pesquisa - opcao 0
    TODO implement:
    - Analise de Formulario 1 - opcao 1
    - Analise de Opcao de Area - opcao 2    
    """
    succeed_NUPs = [] # suceed 
    failed_NUPS = [] # failed
    estudo = None
    for processo in tqdm.tqdm(processos):
        try:            
            estudo = estudos.Interferencia.make(wpage, processo, verbose=verbose)                 
        except Exception as e:  # too generic is masking errors that I don't care for??             
            print("Exception: ", type(e).__name__, " - Process: ", processo, file=sys.stderr)           
            traceback.print_exc()          
            failed_NUPS.append(scm.ProcessStorage[scm.fmtPname(processo)].NUP)            
        else:
            succeed_NUPs.append(estudo.processo.NUP)  
        
    # print all NUPS
    if verbose:
        print('SEI NUPs sucess:')
        for nup in succeed_NUPs:
            print(nup)
        print('SEI NUPs failed:')
        for nup in failed_NUPS:
            print(nup)
    return succeed_NUPs, failed_NUPS



def IncluiDocumentosSEIFolder(sei, process_folder, path='', empty=False, wpage=None, verbose=True):
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
    """
    cur_path = os.getcwd() # for restoring after
    main_path = os.path.join(__secor_path__, path)
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
        elif verbose:
            print('Nao encontrou pdf Imprimir*.pdf', file=sys.stderr)

    #  GET NUP and tipo from html
    # GetProcesso(fathername, self.wpage))

    html = None
    try:
        html_file = glob.glob('*.html')[0] # first html file on folder
        with open(html_file, 'r') as f: # get NUP by html scm
            html = f.read()
    except IndexError: # list index out of range
        if wpage is None:
            raise Exception("Não há página html, please set wpage parameter")
        processostr = scm.fmtPname(process_folder) # from folder name
        scm.dadosBasicosPageRetrieve(processostr, wpage)
        html = wpage.response.text
    # get everything needed
    soup = BeautifulSoup(html, features="lxml")
    data = htmlscrap.dictDataText(soup, scm.scm_data_tags)
    NUP = data['NUP'].strip()
    tipo = data['tipo'].strip()
    fase = data['fase'].strip()

    if empty:
        pdf_adicional = None
        pdf_interferencia = None

    # inclui vários documentos, se desnecessário é só apagar
    # Inclui termo de abertura de processo eletronico se data < 2020 (protocolo digital nov/2019)

    try : # to avoid placing IncluiTermoAberturaPE on processos puro digitais 
        data_protocolo = datetime.strptime(data['data_protocolo'].strip(), 
            "%d/%m/%Y %H:%M:%S")
        if data_protocolo.year < 2020:  
            IncluiTermoAberturaPE(sei, NUP)
    except Exception as e:
        IncluiTermoAberturaPE(sei, NUP)

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
            IncluiDespacho(sei, NUP, 8) # - Recomenda aguardar cunprimento de exigências
            IncluiDespacho(sei, NUP, 9) # - Recomenda c/ retificação de alvará
        elif 'pesquisa' in tipo.lower(): # 1 - Minuta - 'Pré de Alvará'
            # Inclui Estudo pdf como Doc Externo no SEI
            IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)
            IncluiDocumentoExternoSEI(sei, NUP, 1, pdf_adicional)
            if pdf_adicional is None:
                IncluiDespacho(sei, NUP, 4) # - 4 - Recomenda opção
                IncluiDespacho(sei, NUP, 5) # - 5 - Recomenda interferencia total
            else:
                # IncluiDespacho(sei, NUP, 3) # - Recomenda análise de plano c/ notificação titular
                IncluiDespacho(sei, NUP, 12) # - Recomenda Só análise de plano s/ notificação titular
    #     pass
    sei.ProcessoAtribuir() # default chefe
    os.chdir(cur_path) # restore original path , to not lock the folder-path
    # should also close the openned text window - going to previous state
    sei.closeOtherWindows()
    if verbose:
        print(NUP)


def IncluiDocumentosSEIFolders(sei, process_folders, path='Processos', wpage=None, verbose=True):
    """
    Inclui docs. from process folders [list of process-folder-names] on SEI.

    - Estudo
    - Minuta
    - Marca Acompanhamento Especial
    - Despacho

    """
    for folder_name in process_folders:
        try:
            IncluiDocumentosSEIFolder(sei, folder_name, path, verbose=verbose)
        except Exception as e:
            print("Exception: ", e, " - Process: ", folder_name, file=sys.stderr)
            continue

def IncluiDocumentosSEIFoldersFirstN(sei, nfirst=1, path='Processos', wpage=None, verbose=True):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI.
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    - Estudo
    - Minuta
    - Marca Acompanhamento Especial
    - Despacho

    """
    os.chdir(os.path.join(__secor_path__, path))
    files_folders = glob.glob('*')
    # very dirty approach
    # get only process folders with '-' on its name like 830324-1997
    # TODO: use Regex
    process_folders = []
    for cur_path in files_folders: # remove what is NOT a process folder
        if scm.regex_process.search(cur_path) and os.path.isdir(cur_path):
            process_folders.append(cur_path)
    process_folders = process_folders[:nfirst]
    IncluiDocumentosSEIFolders(sei, process_folders, path, wpage, verbose)