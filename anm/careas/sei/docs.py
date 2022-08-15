from . import *
from .config import *
from datetime import datetime

def InsereDocumentoExternoSEI(self, doc=0, pdf_path=None):
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
    self.ProcessoIncluiDoc(0) # Inclui Externo
    # Preenchendo
    self.driver.find_element(By.ID,'selSerie').send_keys(docs_externos[doc]['tipo']) # Tipo de Documento
    # Data do Documento
    self.driver.find_element(By.ID,'txtDataElaboracao').send_keys(datetime.today().strftime('%d/%m/%Y')) # put TODAY
    self.driver.find_element(By.ID,'txtNumero').send_keys(docs_externos[doc]['desc']) # Nome na Arvore
    self.driver.find_element(By.ID,'optNato').click() #   Nato-digital
    self.driver.find_element(By.ID,'lblPublico').click() # Publico
    if pdf_path is not None: # existe documento para anexar
        file = self.driver.find_element(By.ID,'filArquivo') # Upload PDF
        file.send_keys(pdf_path)
    # save = sei.driver.find_element(By.ID,'btnSalvar')
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(self.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    self.driver.switch_to.default_content() # go back to main document
    
    
def InsereDeclaracao(self, idxcodigo):
    """
    Inclui Declaração - por index código modelo favorito
    """
    mcodigo = mcodigos[idxcodigo]
    self.ProcessoIncluiDoc(4) # modelo favorito
    self.driver.find_element(By.ID,'lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    self.driver.find_element(By.ID,'txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    self.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(self.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    self.driver.switch_to.default_content() # go back to main document

#Divisão de Fiscalização da Mineração de Não Metálicos (DFMNM-MG)
#Setor de Controle e Registro (SECOR-MG)
def IncluiDespacho(self, idxcodigo, 
    setor=u"Setor de Controle e Registro (SECOR-MG)", 
    assinar=False):
    """
    Inclui Despacho - por index código
    """
    mcodigo = mcodigos[idxcodigo]
    self.ProcessoIncluiDoc(1) # Despacho
    self.driver.find_element(By.ID,'lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    self.driver.find_element(By.ID,'txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    self.driver.find_element(By.ID,'txtDestinatario').send_keys(setor)
    destinatario_set = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'divInfraAjaxtxtDestinatario')))
    destinatario_set.click() # wait a little pop-up show up to click or send ENTER
    # sei.driver.find_element(By.ID,'txtDestinatario').send_keys(Keys.ENTER) #ENTER
    self.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(self.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    self.driver.switch_to.default_content() # go back to main document

def EscreveDespacho(self, texto):
    """
    Escreve Despacho usando string `texto`
    """
    self.ProcessoIncluiDoc(1) # Despacho
    self.driver.find_element(By.ID,'txtDestinatario').send_keys(u"Setor de Controle e Registro (SECOR-MG)")
    destinatario_set = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'divInfraAjaxtxtDestinatario')))
    destinatario_set.click() # wait a little pop-up show up to click or send ENTER
    # sei.driver.find_element(By.ID,'txtDestinatario').send_keys(Keys.ENTER) #ENTER
    self.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try : # may take a long time to load the pop up
        # wait 10 seconds
        alert = wait(self.driver, 10).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass

    wait(self.driver, 10).until(expected_conditions.number_of_windows_to_be(2))
    # text window now open, but list of handles is not ordered
    textwindow = [hnd for hnd in self.driver.window_handles if hnd != self.mainwindow ][0]
    self.driver.switch_to.window(textwindow) # go to text pop up window
    self.driver.switch_to.default_content() # go to parent main document
    
    # this is the one that can take the longest time of ALL
    wait(self.driver, 20).until( # then go to frame of input text 
        expected_conditions.frame_to_be_available_and_switch_to_it(
        (By.CSS_SELECTOR,"iframe[aria-describedby='cke_244']")))

    inputtext = self.driver.find_element(By.CSS_SELECTOR, 'body[contenteditable="true"]')

    inputtext.clear()
    for line in texto.split('\n'):  # split by lines
        inputtext.send_keys(line) # type in each line - must use keys like bellow
        inputtext.send_keys(Keys.ENTER) # create a new line
        #inputtext.send_keys(Keys.BACKSPACE) # go back to its beginning

    self.driver.switch_to.default_content() # go to parent main iframe document    
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'cke_202')))
    save.click() 
    # to make sure it has finnished saving we have to wait until 
    # 1. save button becames visible inactive and 
    wait(self.driver, 10).until(expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, 
        "#cke_202[class='cke_button cke_button__save cke_button_disabled']")))    
    # 2. any other button becomes clickable again (like button assinar)
    wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, 
        "#cke_204[class='cke_button cke_button__assinatura cke_button_off']")))    
    # than we can close
    self.driver.close() # close text window

    wait(self.driver, 10).until(expected_conditions.number_of_windows_to_be(1))
    self.driver.switch_to.window(self.mainwindow) # go back to main window
    self.driver.switch_to.default_content() # go to parent main document
    # to not stale the window have to go to it again to the following task
    

def IncluiParecer(self, ProcessoNUP, idxcodigo=0):
    """
    Inclui Parecer
    idxcodigo : int index
        default retificaçaõ de alvará = 0
    """
    mcodigo = mcodigos[idxcodigo]
    self.Pesquisa(ProcessoNUP) # Entra neste processo
    self.ProcessoIncluiDoc(2) # Parecer
    self.driver.find_element(By.ID,'lblProtocoloDocumentoTextoBase').click() # Documento Modelo
    self.driver.find_element(By.ID,'txtProtocoloDocumentoTextoBase').send_keys(mcodigo)
    self.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(self.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    self.driver.switch_to.default_content() # go back to main document

def IncluiTermoAberturaPE(self, ProcessoNUP):
    """
    Inclui Termo de Abertura de Processo Eletronico
    """
    self.Pesquisa(ProcessoNUP) # Entra neste processo
    self.ProcessoIncluiDoc(3) # Termo de Abertura
    self.driver.find_element(By.ID,'lblPublico').click() # Publico
    save = wait(self.driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'btnSalvar')))
    save.click()
    try :
        # wait 5 seconds
        alert = wait(self.driver, 5).until(expected_conditions.alert_is_present()) # may sometimes show
        alert.accept()
    except:
        pass
    self.driver.switch_to.default_content() # go back to main document