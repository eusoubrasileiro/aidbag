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
        'Minuta', 'Minuta', 'Estudo', 'Minuta', 'Minuta']

docs_externos_sei_txt = [ 'de Retirada de Interferência', # Nome na Arvore
        'Pré de Alvará', 'de Licenciamento', 'de Opção', 'de Portaria de Lavra',
        'de Permissão de Lavra Garimpeira']


def IncluiDocumentoExternoSEI(sei, ProcessoNUP, doc=0, pdf_path=None):
    """
    Inclui pdf como documento externo no SEI

    doc :
        0 - Estudo - 'de Retirada de Interferência'
        1 - Minuta - 'Pré de Alvará'
        2 - Minuta - 'de Licenciamento'
        3 - Estudo - 'de Opção'
        4 - Minuta - 'de Portaria de Lavra'
        6 - Minuta - 'de Permissão de Lavra Garimpeira'

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



def IncluiDocumentosSEIFolder(sei, process_folder, tipo='Requerimento', path='', empty=False, verbose=True):
    """
    Inclui process on specified folder:
    `__secor_path__\\tipo\\path\\process_folder`
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    * verbose: True
        avisa ausência de pdfs, quando cria documentos sem anexos
    * empty : True
        cria documentos sem anexos

    - Estudo
    - Minuta
    - Marca Acompanhamento Especial

    TODO:
        - Despacho
    """
    os.chdir(os.path.join(secor.__secor_path__, tipo , path))
    process_path = os.path.join(os.getcwd(), process_folder)
    os.chdir(process_folder) # enter on process folder
    #  GET NUP and tipo from html
    # GetProcesso(fathername, self.wpage))
    scm_html = glob.glob('*.html')[0] # first html file on folder
    with open(scm_html, 'r') as f: # get NUP by html scm
        html = f.read()

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
        os.chdir('..') # go back from process folder

    # get NUP
    soup = BeautifulSoup(html, features="lxml")
    data = htmlscrap.dictDataText(soup, scm.scm_data_tags)
    NUP = data['NUP'].strip()
    tipo = data['tipo'].strip()
    fase = data['fase'].strip()

    if empty:
        pdf_adicional = None
        pdf_interferencia = None

    # Inclui Estudo pdf como Doc Externo no SEI
    IncluiDocumentoExternoSEI(sei, NUP, 0, pdf_interferencia)
    # Inclui pdf adicional Minuta de Licenciamento ou Pré Minuta de Alvará
    if 'licen' in tipo.lower():
        # 2 - Minuta - 'de Licenciamento'
        IncluiDocumentoExternoSEI(sei, NUP, 2, pdf_adicional)
    elif 'garimpeira' in tipo.lower():
        if 'requerimento' in fase.lower(): # Minuta de P. de Lavra Garimpeira
            IncluiDocumentoExternoSEI(sei, NUP, 5, pdf_adicional)
    else:
        # tipo - requerimento de cessão parcial ou outros
        if 'lavra' in fase.lower(): # minuta portaria de Lavra
            IncluiDocumentoExternoSEI(sei, NUP, 4, pdf_adicional)
        elif 'pesquisa' in tipo.lower(): # 1 - Minuta - 'Pré de Alvará'
            IncluiDocumentoExternoSEI(sei, NUP, 1, pdf_adicional)

    # IncluiDespacho(sei, NUP, 6) - Recomenda análise de plano
    # else: # Despacho diferente se não existe segundo pdf
    #     pass
    # sei.ProcessoIncluiAEspecial(1) # 1 - me desnecessario e
    # lota todos os Acompanhamentos

def IncluiDocumentosSEIFolders(sei, nfirst=1, tipo='Requerimento', path=''):
    """
    Inclui first process folders `nfirst` (list of folders) docs on SEI.
    Follow order of glob(*) using `chdir(tipo) + chdir(path)`

    - Estudo
    - Minuta
    - Marca Acompanhamento Especial

    TODO:
        - Despacho
    """
    os.chdir(os.path.join(secor.__secor_path__, tipo, path))

    process_folders = glob.glob('*')
    process_folders = process_folders[:nfirst]

    for process_folder in process_folders:
        IncluiDocumentosSEIFolder(sei, process_folder, tipo, path)
