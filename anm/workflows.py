### Inclui todos os pdfs nas pastas specificadas no SEI
# Seguindo nome se é licença ou minuta
import tqdm
import importlib
import glob
import os
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from anm import secor
from anm import scm
from web import htmlscrap
from .SEI import *

docs_externos_sei_tipo = [ 'Estudo',
        'Minuta', 'Minuta', 'Estudo', 'Minuta', 'Minuta', u'Formulário']

# needs u"" unicode string because of latim characters
docs_externos_sei_txt = [ u"de Retirada de Interferência", # Nome na Arvore
        u"Pré de Alvará", 'de Licenciamento', u"de Opção", 'de Portaria de Lavra',
        u"de Permissão de Lavra Garimpeira", u"1 Análise de Requerimento de Lavra SECOR-MG"]

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

# 0 -  1537881	Retificação Resumida Alvará e Aprovo do RFP
# 1 - 1947449	Parecer Técnico - Correção áreas e deslocamentos
# 2 - 1618347	Formulário 1 - Lavra - Pré-Prenchido
# 3 - 1132737	Chefe SECOR Requerimento: Recomendo Analise de Plano
# 4 - 1133380	Chefe SECOR Requerimento: Recomenda publicar exigência opção
# 5 - 1197141	Chefe SECOR Requerimento: Recomenda publicar indeferimento por Interferência Total
# 6 - 1206693	Chefe SECOR Requerimento: Recomendo Analise de Cessão Parcial
# 7 - 1243175	Chefe SECOR Requerimento: Recomendo Analise de Plano (híbrido)
# 8 - 1453503	Chefe SECOR Requerimento de Lavra: Recomendo aguardar cumprimento de exigências
# 9 - 1995116	Chefe SECOR Requerimento de Lavra: com Retificação de Alvará
# 10 - 1995741	Chefe SECOR Requerimento de Lavra: Recomendo encaminhar para preenchimento de check-list
# 11 - 2052065	Chefe SECOR Requerimento de Lavra: Encaminhar avaliar necessidade de reavaliar reservas - redução de área
mcodigos = ['1537881', '1947449', '1618347', '1132737', '1133380', '1197141', '1206693', '1243175', '1453503', '1995116', '1995741', '2052065']

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

def EstudoBatchRun(wpage, processos, option=3, verbose=False):
    """
    - Analise de Requerimento de Pesquisa - opcao 0
    - Analise de Formulario 1 - opcao 1
    - Analise de Opcao de Area - opcao 2
    - Batch Requerimento de Pesquisa - opcao 3
    """
    NUPs = []
    for processo in tqdm.tqdm(processos):
        estudo = secor.Estudo(processo, wpage, 0, verbose=verbose)
        estudo.salvaDadosBasicosSCM()
        estudo.salvaDadosPoligonalSCM()
        if estudo.salvaRetiradaInterferencia():
            if not estudo.cancelaUltimoEstudo():
                raise Exception("Couldn't cancel ultimo estudo")
            if estudo.getTabelaInterferencia() is not None:
                estudo.getTabelaInterferenciaTodos()
                estudo.excelInterferencia()
                estudo.excelInterferenciaAssociados()
        else:
            print("Couldn't download retirada de interferencia")
        NUPs.append(estudo.processo.NUP)
    # print all NUPS
    print('SEI NUP:')
    for nup in NUPs:
        print(nup)



def IncluiDocumentosSEIFolder(sei, process_folder, path='', empty=False, wpage=None, verbose=True):
    """
    Inclui process documents from specified folder:
    `__secor_path__\\path\\process_folder`
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    * verbose: True
        avisa ausência de pdfs, quando cria documentos sem anexos
    * empty : True
        cria documentos sem anexos

    """
    cur_path = os.getcwd() # for restoring after
    main_path = os.path.join(secor.__secor_path__, path)
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
        processostr = scm.fmtPname(process_folder) # from folder name
        secor.dadosBasicosRetrieve(processostr, wpage)
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
    # Inclui termo de abertura de processo eletronico
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
            IncluiDespacho(sei, NUP, 3) # - Recomenda análise de plano
    #     pass
    sei.ProcessoAtribuir() # default chefe
    os.chdir(cur_path) # restore original path , to not lock the folder-path
    if verbose:
        print(NUP)

def IncluiDocumentosSEIFolders(sei, nfirst=1, path='', wpage=None, verbose=True):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI.
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    - Estudo
    - Minuta
    - Marca Acompanhamento Especial

    TODO:
        - Despacho
    """
    os.chdir(os.path.join(secor.__secor_path__, path))
    files_folders = glob.glob('*')
    # get only process folders with '-' on its name like 830324-1997
    process_folders = []
    for cur_path in files_folders: # remove what is NOT a process folder
        if cur_path.find('-') != -1 and os.path.isdir(cur_path):
            process_folders.append(cur_path)
    process_folders = process_folders[:nfirst]
    for folder_name in process_folders:
        try:
            IncluiDocumentosSEIFolder(sei, folder_name, path, verbose=verbose)
        except Exception as e:
            print("Exception: ", e, " - Process: ", folder_name, file=sys.stderr)
            continue
