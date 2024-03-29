from datetime import datetime
from enum import auto, Enum
import requests
import pathlib
from bs4 import BeautifulSoup
import urllib3

from .. import util
from ....web.selenium import *
from .cls import Sei
from .config import *


class BARRACOMANDOS_STATE(Enum):
    MAIN_OPEN = 1 # it's the main barra comandos and the process is open
    MAIN_CLOSED_CAN_OPEN = 2
    MAIN_CLOSED_CANT_OPEN = 3 # it's the main barra comandos and the process is closed
    DOC = 4 # it's and documents bar 

class Processo(Sei):
    def __init__(self, processnup, user, passwd, headless=True, login=False, webdriver=None):
        """Login on sei and search for process `processnup`

        Args:
            processnup (str): process NUP
            user (str):  
            passwd (str): 
            headless (bool, optional): run webdriver headless. Defaults to True.
            login (bool, optional): weather to login or not. Defaults to False.
                False if webdriver not None 
            webdriver (_type_, optional): selenium webdriver. Defaults to None.
        """
        if webdriver:
            login = False            
        super().__init__(user, passwd, headless, login)  
        self.user = user 
        self.passwd = passwd 
        self.headless = headless
        self.login = login 
        self.driver = webdriver
        self.mainwindow = self.driver.current_window_handle
        self.nup = processnup        
        
    @staticmethod
    def fromSei(sei, processnup):
        """re-using an existing webdriver window opened on sei"""
        processo = Processo(processnup, sei.user, sei.passwd, sei.headless, False, sei.driver)
        processo.pesquisaProcesso(processnup)
        return processo 
    
    def mainMenu(self):
        """back to main menu processo"""            
        wait_for_ready_state_complete(self.driver)
        self.driver.switch_to.default_content() # go to default frame  
        switch_to_frame(self.driver, "iframe#ifrArvore") # frame panel left
        click(self.driver, '#topmenu :nth-child(2)') # open menu on processo name to the right
        wait_for_ready_state_complete(self.driver)
        self.driver.switch_to.default_content()        
        
    def _barraComandos(self):
        try:
            # if div#detalhes is present barra commands is alredy openned
            find_element(self.driver,'div#divArvoreHtml div#detalhes')
        except NoSuchElementException:
            self.mainMenu()
            switch_to_frame(self.driver, 'iframe#ifrVisualizacao')            
            try: # wait for infraBarraComandos botoes available   
                wait_for_element_visible(self.driver, 'div#divArvoreAcoes.infraBarraComandos')    
            except (ElementNotVisibleException, NoSuchElementException):
                self._barraComandos()

            
    def barraComandosState(self):
        self._barraComandos()
        nbuttons = len(find_elements(self.driver, ".botaoSEI"))
        if nbuttons == 22:
            return BARRACOMANDOS_STATE.MAIN_OPEN
        elif nbuttons == 9:
            try : 
                find_element(self.driver, "div#divArvoreAcoes.infraBarraComandos a[onclick*='reabrir']")                
            except NoSuchElementException:
                return BARRACOMANDOS_STATE.MAIN_CLOSED_CANT_OPEN   
            return  BARRACOMANDOS_STATE.MAIN_CLOSED_CAN_OPEN       

    def barraComandos(self, index):           
        """
        barra comandos list of by index
            1 - incluir documento
            8 - atribuir
            20 - gerenciar marcador
        """
        state = self.barraComandosState()
        if state == BARRACOMANDOS_STATE.MAIN_CLOSED_CAN_OPEN :            
            click(self.driver, "img[title='Reabrir Processo']")
        elif state == BARRACOMANDOS_STATE.MAIN_CLOSED_CANT_OPEN:
            raise Exception(f"Processo {self.nup} nunca aberto nesta unidade")  
        # safer and more efficient to use click
        click(self.driver, f'div.infraBarraComandos a:nth-of-type({index})')   
                 
    def isOpen(self):
        """processo aberto nesta unidade"""
        return self.barraComandosState() == BARRACOMANDOS_STATE.MAIN_OPEN

    def atribuir(self, pessoa):
        self.barraComandos(8)         
        dropdown = wait_for_element_visible(self.driver,'select#selAtribuicao')
        select = Select(dropdown)
        select.select_by_visible_text(pessoa)
        select.first_selected_option.click()
        click(self.driver, "button#sbmSalvar")
        
    def _abrirPastas(self):
        """abrir pastas documentos on processo
        must switch_to.default_content() after"""        
        self.driver.switch_to.default_content()
        switch_to_frame(self.driver, "iframe#ifrArvore") # frame panel left   
        try:         
            fechar_pastas = find_element(self.driver, "a[href*='fechar_pastas'")
            if not fechar_pastas.is_displayed(): # não aberto
                click(self.driver, "a[href*='abrir_pastas'") # open
                # esperar ate uns 20 segundos para abrir as pastas de muitos volumes                
                wait_for_element_presence(self.driver, "a[href*='fechar_pastas'", timeout=20)
        except NoSuchElementException: 
            # sem documentos suficientes para pastas serem formadas
            pass         

    def listaDocumentos(self):
        """return a list of documents with a dict each containing
            { title , doc protocol number, and inner soup element ...}
            for each doc on documents tree
        ISSUE: Very very slow for multiple volume process
        """        
        self._abrirPastas()
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        self.driver.switch_to.default_content() # was focused on frame left!
        edocs = soup.select("a.clipboard + a") # getting all docs on process
        # len(docs)
        docs = []
        for edoc in edocs[1:]: #ignore first that's the process 
            title = edoc.contents[0]['title'] # inside span 1st children
            np = re.findall('\d{6,}', str(edoc.contents[0]))[-1]  # numero protocolo é o último
            name = re.sub("[()]", "", title.replace(np, '')).strip() # anything except ( )            
            docs.append({ 'title' : name,  'np' : np, 'soup_element' : edoc , 'selector' : f"a#{edoc['id']}"} )
        return docs 

    def download_latest_documents(self, lastn=5):
        """download lastn documents from listaDocuments to default `processPath` folder"""
        lista = self.listaDocumentos()
        lastn = len(lista) if lastn > len(lista) else lastn 
        for i in range(1,lastn+1):
            self.driver.switch_to.default_content() 
            switch_to_frame(self.driver, "iframe#ifrArvore") # left bar       
            click(self.driver, lista[-i]['selector'])
            self.driver.switch_to.default_content() 
            switch_to_frame(self.driver, "iframe#ifrVisualizacao") # right bar
            try:
                element = find_element(self.driver, "div a.ancoraArvoreDownload")     
            except NoSuchElementException:
                # it's not a downloadable external element it's html doc nota/despacho etc.
                suffix = '.html'        
                wait_for_element_presence(self.driver, 'iframe#ifrArvoreHtml')
                switch_to_frame(self.driver, 'iframe#ifrArvoreHtml') # html iframe         
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                html_doc = soup.select('html')[0]   
                file_content = html_doc.prettify().encode('utf-8')    
            else:        
                suffix = '.pdf'
                uri = element.get_attribute('href')    
                cookies = self.driver.get_cookies() # get selenium cookies
                s = requests.Session() # create requests session
                for cookie in cookies: # fill in session with selenium cookies
                    s.cookies.set(cookie['name'], cookie['value'])
                urllib3.disable_warnings() # ignore SSL warnings
                response = s.get(uri, verify=False) # ignore SSL certificate
                file_content = response.content
            # number prefix to sort/order documents according to their original position
            prefix = f"{len(lista)-i:03d}_" 
            filepath = pathlib.Path(util.processPath(self.nup, create=True)) / ( 
                prefix + lista[-i]['title'] + suffix)
            with open(filepath.absolute(), 'wb') as f:
                f.write(file_content)

    def insereDocumento(self, code=0):
        """
        code:
            0  - ' Externo' - default
            1  - 'Termo de Abertura de Processo Eletrônico'
            2  - 'Nota Tecnica' - only one to be used!
        """
        texts = [ 'Externo', 'Termo de Abertura de Processo Eletronico', 'Nota Tecnica']
        self.barraComandos(1)  # botao incluir doc
        # *= contains text in lowercase
        click(self.driver, f"tr[data-desc*='{texts[code].lower()}'] td a:last-child", delay=DELAY_SMALL)                          
    
    def insereDocumentoExterno(self, doc=0, pdf_path=None):
        """
        Inclui pdf como documento externo no SEI
        * doc :
            0.  - Estudo      - 'de Retirada de Interferência' 
            1.  - Minuta      - 'Pré de Alvará' 
            2.  - Minuta      - 'de Licenciamento' 
            3.  - Estudo      - 'de Opção' 
            4.  - Minuta      - 'de Portaria de Lavra' 
            5.  - Minuta      - 'de Permissão de Lavra Garimpeira' 
            6.  - Formulario  - '1 Análise de Requerimento de Lavra' 
            7.  - Minuta      - 'de Registro de Extração'
            8.  - Estudo      - 'de Mudança de Regime'
        * pdf_path :
            if None cria sem anexo
        """
        self.insereDocumento(0) # Inclui Externo
        send_keys(self.driver, '#selSerie.infraSelect', docs_externos[doc]['tipo']) # Tipo de Documento 
        send_keys(self.driver, '#txtDataElaboracao.infraText', datetime.today().strftime('%d/%m/%Y')) # Data do Documento put today
        send_keys(self.driver, '#txtNumero.infraText', docs_externos[doc]['desc']) # Nome na Arvore
        click(self.driver, '#optNato.infraRadio') #  Nato-digital
        click(self.driver, '#lblPublico.infraLabelRadio') # Publico
        if pdf_path is not None: # existe documento para anexar
            send_keys(self.driver, 'input#filArquivo', pdf_path) # upload by path
        click(self.driver, 'button#btnSalvar') # this was problematic       
        # alert may sometimes show for 'duplicated' documents             
        try_accept_alerts(self.driver)   
        wait_for_ready_state_complete(self.driver) # wait for upload complete
        self.driver.switch_to.default_content() # go back to main document
        
        
        
    def insereNotaTecnica(self, htmltext):
        self.insereDocumento(2) # Inclui Nota Tecnica
        click(self.driver, '#lblPublico.infraLabelRadio') # Publico
        click(self.driver, 'button#btnSalvar')        
        self.driver.switch_to.default_content() # go back to main document    
        # insert htmltext code 
        # select text-editor
        wait(self.driver, 10).until(expected_conditions.number_of_windows_to_be(2))
        # text window now open, but list of handles is not ordered
        textwindow = [hnd for hnd in self.driver.window_handles if hnd != self.mainwindow ][0]
        self.driver.switch_to.window(textwindow) # go to text pop up window
        htmltext = htmltext.replace('\n', '') # just to make sure dont mess with jscript                                
        def write_html_on_iframe():
            self.driver.switch_to.default_content() # go to parent main document
            switch_to_frame(self.driver, "#cke_6_contents iframe")
            editor = find_element(self.driver, "body") # just to enable save button        
            editor.clear()
            editor.send_keys(Keys.BACK_SPACE*42)        
            self.driver.switch_to.default_content() # go to parent main document                   
            # insert html code of template doc using javascript iframe.write 
            # using arguments 
            # https://stackoverflow.com/questions/52273298/what-is-arguments0-while-invoking-execute-script-method-through-webdriver-in
            jscript = f"""iframe = document.querySelector('#cke_6_contents iframe');
            iframe.contentWindow.document.open();
            iframe.contentWindow.document.write(arguments[0]); 
            iframe.contentWindow.document.close();"""
            self.driver.execute_script(jscript, htmltext)        
            wait_for_ready_state_complete(self.driver) # it stalls the page                                    
            click(self.driver, "a[title*='Salvar']")            
        def check_write_on_iframe():
            self.driver.switch_to.default_content() # go to parent main document
            switch_to_frame(self.driver, "#cke_6_contents iframe")
            wait_for_element_presence(self.driver, "body#sei_edited") # body id to check it wrote            
        while True: # to guarantee it really gets written
            write_html_on_iframe() 
            # to garantee save, wait for button salvar to be disabled
            wait_for_element_presence(self.driver, 
                "a#cke_262[class='cke_button cke_button__save cke_button_disabled' ]", 
                timeout=60) # very high timeout for save to no keep waiting                                          
            try:
                check_write_on_iframe()
            except NoSuchElementException:
                continue  
            else:
                break 
        self.driver.close() # close this page         
        self.driver.switch_to.window(self.mainwindow) # go to main window

    def InsereTermoAberturaProcessoEletronico(self):
        """Inclui Termo de Abertura de Processo Eletronico"""
        self.insereDocumento(1) # Termo de Abertura
        click(self.driver, '#lblPublico.infraLabelRadio') # Publico
        click(self.driver, 'button#btnSalvar')   
        # alert may sometimes show for 'duplicated' documents     
        try_accept_alerts(self.driver)   
        self.closeOtherWindows()
        self.driver.switch_to.default_content() # go back to main document        
        
    def insereNotaTecnicaRequerimento(self, template_name, infos, **kwargs):
        """analisa documentos e cria nota técnica sobre análise de interferência
        based on jinja2 template
        'area_porcentagem' must be passed as **kwargs"""
        def latest_doc_by_title(docs, title):
            selected = [ doc for doc in docs if title.lower() in doc['title'].lower() ]
            return selected[-1]['np'] if selected else '' # instead of None put empty string on the nota tecnica
        docs = self.listaDocumentos()              
        # get numero protocolo minuta and interferencia
        minuta_np = latest_doc_by_title(docs, 'Minuta') 
        interferencia_np = latest_doc_by_title(docs, 'Interferência')         
        # find the template by name 
        doc_templates = pathlib.Path(config['sei']['doc_templates'])            
        template_path = next(doc_templates.glob(f"*{template_name}*.html"))
        template = templateEnv.get_template(template_path.name) 
        # additional and uncessary variables will just be ignored by jinja         
        # for example, interferencia_sei, minuta_sei if not on the template will be ignored
        html_text = template.render(infos=infos, interferencia_sei=interferencia_np, minuta_sei=minuta_np, 
                                        **kwargs)  # 'area_porcentagem' was passed as kwargs                       
        self.insereNotaTecnica(html_text)
        
    def insereMarcador(self, marcador):
        self.barraComandos(20)                  
        click(self.driver, 'div.dd-select')
        click(self.driver, f"//li//label[text()='{marcador}']", by=By.XPATH)        
        click(self.driver, "button[type=submit]")