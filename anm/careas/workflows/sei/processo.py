from datetime import datetime
from enum import auto, Enum
import requests
import pathlib
from bs4 import BeautifulSoup
import urllib3
from unidecode import unidecode 

from .....general import closest_string
from ... import util
from .....web.selenium import *
from .cls import Sei
from .config import *
from .forms import fillFormPrioridade
from .docs import insertHTMLDoc, HTMLDOC

class BARRACOMANDOS_STATE(Enum):
    MAIN_OPEN = 1 # it's the main barra comandos and the process is open
    MAIN_CLOSED_CAN_OPEN = 2
    MAIN_CLOSED_CANT_OPEN = 3 # it's the main barra comandos and the process is closed

class BARRACOMANDOS_BUTTONS(Enum): #barra comandos list of by index        
        INCLUIR_DOCUMENTO = 1
        ATRIBUIR = 8
        GERENCIAR_MARCADOR = 20

class ProcessoSeiNotOpen(BlockingIOError):    
    pass


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
        self.pesquisaProcesso(processnup) # go-to processo
        if not self._isOpen():
            raise  ProcessoSeiNotOpen("Não aberto nesta unidade! Movimente-o para cá.")

    def _isOpen(self):
        """processo aberto nesta unidade"""
        return self.barraComandosState() == BARRACOMANDOS_STATE.MAIN_OPEN

    @staticmethod
    def fromSei(sei, processnup):
        """re-using an existing webdriver window opened on sei"""
        return Processo(processnup, sei.user, sei.passwd, sei.headless, False, sei.driver)
    
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

    def barraComandos(self, button):           
        """
        button in BARRACOMANDOS_BUTTONS
        """
        state = self.barraComandosState()
        if state == BARRACOMANDOS_STATE.MAIN_CLOSED_CAN_OPEN :            
            click(self.driver, "img[title='Reabrir Processo']")
        elif state == BARRACOMANDOS_STATE.MAIN_CLOSED_CANT_OPEN:
            raise Exception(f"Processo {self.nup} nunca aberto nesta unidade")  
        # safer and more efficient to use click
        click(self.driver, f'div.infraBarraComandos a:nth-of-type({button.value})')   
                 
    def atribuir(self, pessoa):
        self.barraComandos(BARRACOMANDOS_BUTTONS.ATRIBUIR)         
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
        for index, edoc in enumerate(edocs[1:]): #ignore first that's the process 
            title = edoc.contents[0]['title'] # inside span 1st children
            np = re.findall('\d{6,}', str(edoc.contents[0]))[-1]  # numero protocolo é o último
            name = re.sub("[()]", "", title.replace(np, '')).strip() # anything except ( )            
            docs.append({ 'title' : name,  'np' : np, 'index': index, # real index position of doc
                         'soup_element' : edoc , 'selector' : f"a#{edoc['id']}"} )
        return docs 
    

    def _downloadDocument(self, doc : dict):
        """
        download document from tree at default process folder

        * doc: dict 
            { title , doc protocol number, and inner soup element ...}    
            from listaDocumentos(self)

        """
        # for safety - go back to main document
        self.driver.switch_to.default_content() 
        switch_to_frame(self.driver, "iframe#ifrArvore") # left bar       
        click(self.driver, doc['selector'])
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
        prefix = f"{doc['index']:03d}_"  # maximum 999 index
        filepath = pathlib.Path(util.processPath(self.nup, create=True)) / ( 
            prefix + doc['title'] + suffix)
        with open(filepath.absolute(), 'wb') as f:
            f.write(file_content)


    def downloadDocumentosFiltered(self, filterfunc):
        """apply filterfunc on listaDocumentos and 
        download the resulting list 
        Note 1: filter function returns true or false
        Note 2: listaDocumentos items are dicts with keys 'title' etc...
        e. g.:
        downloaDocumentosFiltered(lambda x: True if 'municip' in x['title'].lower() else False)
        """
        lista = self.listaDocumentos()
        lista = list(filter(filterfunc, lista))
        for doc in lista:            
            self._downloadDocument(doc)

    def downloadDocumentos(self, lastn=5):
        """download lastn documents from listaDocuments to default `processPath` folder"""
        lista = self.listaDocumentos()        
        for doc in lista[-lastn:]:
            self._downloadDocument(doc)


    def insereDocumento(self, partial_text):
        """
        * partial_text : can be any string that partially matchs the following doc names
            'Externo', 'Termo de Abertura de Processo Eletrônico', 'Nota Técnica', '            
        """
        docnames = [ 'Externo', 
            'Termo de Abertura de Processo Eletrônico', 
            'Nota Técnica', # here can use accents and ç anything Unicode but bellow you need ASCII
            'Formulário de Análise do Direito de Prioridade']
        docname = closest_string(partial_text, docnames)
        self.barraComandos(BARRACOMANDOS_BUTTONS.INCLUIR_DOCUMENTO)  
        # *= contains text in lowercase - before convert to ASCII        
        # constant exception here of cannot find element
        click(self.driver, f"tr[data-desc*='{unidecode(docname.lower())}'] td a:last-child", 
                delay=DELAY_SMALL, timeout=TIMEOUT_LARGE)                          
        
    
    def insereDocumentoExterno(self, docname, pdf_path=None):
        """
        Inclui pdf como documento externo no SEI name it properly. 
        * partial_title: any partial text that matchs one title on {config.docs_externos}
        * pdf_path : path to pdf to upload
            if None cria sem anexo
        """
        self.insereDocumento("Externo") 
        pieces = docname.split(' ')
        tipo, desc = pieces[0], ' '.join(pieces[1:]) # Tipo de Documento (e.g Estudo) e Nome na Arvore (e.g. Retirada de Interferência)
        send_keys(self.driver, '#selSerie.infraSelect', tipo) # Tipo de Documento 
        send_keys(self.driver, '#txtDataElaboracao.infraText', datetime.today().strftime('%d/%m/%Y')) # Data do Documento put today
        send_keys(self.driver, '#txtNumero.infraText', desc) # Nome na Arvore
        click(self.driver, '#optNato.infraRadio') #  Nato-digital
        click(self.driver, '#lblPublico.infraLabelRadio') # Publico
        pdf_path = str(pdf_path) # convert to string case pathlib.Path
        if pdf_path is not None: # existe documento para anexar
            send_keys(self.driver, 'input#filArquivo', pdf_path) # upload by path
        click(self.driver, 'button#btnSalvar') # this was problematic       
        # alert may sometimes show for 'duplicated' documents             
        try_accept_alerts(self.driver)   
        wait_for_ready_state_complete(self.driver) # wait for upload complete
        self.driver.switch_to.default_content() # go back to main document        
        
        
    def insereNotaTecnica(self, htmltext):
        self.insereDocumento("Nota Técnica") # Inclui Nota Tecnica
        insertHTMLDoc(self.driver, htmltext, self.mainwindow, HTMLDOC.NOTA_TECNICA)
        self.driver.switch_to.window(self.mainwindow) # go to main window

    def InsereTermoAberturaProcessoEletronico(self):
        """Inclui Termo de Abertura de Processo Eletronico"""
        self.insereDocumento("Termo de Abertura")
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

    def insereFormPrioridade(self, infos, **kwargs):
        """
        Formulário de analise de prioridade para 
        Requerimento de Autorização de Pesquisa, Registro de Licença, 
        Permissão de Lavra Garimpeira e Registro de Extração
        Analisa documentos e cria nota técnica sobre análise de interferência
        based on jinja2 template on `req_form_analise`
        """
        htmltext = fillFormPrioridade(infos)
        self.insereDocumento("Formulário Prioridade") # Inclui Nota Tecnica   
        insertHTMLDoc(self.driver, htmltext, self.mainwindow, HTMLDOC.FORMULARIO_PRIORIDADE)
        self.driver.switch_to.window(self.mainwindow) # go to main window
        
    def insereMarcador(self, marcador):
        self.barraComandos(BARRACOMANDOS_BUTTONS.GERENCIAR_MARCADOR)                  
        click(self.driver, 'div.dd-select')
        click(self.driver, f"//li//label[text()='{marcador}']", by=By.XPATH)        
        click(self.driver, "button[type=submit]")


        