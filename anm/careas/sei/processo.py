from . import *

class Processo(Sei):
    def __init__(self, processnup, user, passwd, headless=False, implicit_wait=10, login=True):
        # will open another window with another webdriver
        # it's ok but sometimes may fail having multiple windows?
        super().__init__(user, passwd, headless, implicit_wait, login)         
        self.nup = processnup
        self.pesquisaProcesso(processnup)
        
    @staticmethod(function)
    def fromSei(sei, processnup):
        # re-using an existing webdriver window opened
        processo = Processo(sei.user, sei.passwd, False, sei.implicit_wait, login=False)
        processo.driver = sei.driver 
        processo.mainwindow = sei.mainwindow
        processo.pesquisaProcesso(processnup)
        return processo 
    
    from .docs import (
        InsereDeclaracao,
        IncluiDespacho,
        InsereDocumentoExternoSEI,
        IncluiParecer,
        IncluiTermoAberturaPE,
        EscreveDespacho
    )

    def _mainMenu(self):
        """back to main menu processo"""

        self.driver.switch_to.default_content() # go to parent main document
        wait(self.driver, 10).until( # then go to frame panel left
            expected_conditions.frame_to_be_available_and_switch_to_it(
            (By.CSS_SELECTOR,'iframe#ifrArvore')))
            
        anchors = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CSS_SELECTOR,'#topmenu a')))

        anchors[1].click() # # 1 click to open main menu on processo name

        # not working with above
        # # guarantee the right frame has been refreshed too
        # wait(self.driver, 10).until(
        #    expected_conditions.staleness_of(botao))
        # solved all problems created above
        # of refreshing delay
        time.sleep(3)
        self.driver.switch_to.default_content()


    def abrirPastas(self):
        """abrir pastas documentos on processo"""
        
        self.driver.switch_to.default_content()
        
        wait(self.driver, 10).until( # then go to frame panel left
            expected_conditions.frame_to_be_available_and_switch_to_it(
            (By.CSS_SELECTOR,'iframe#ifrArvore')))
        
        webe = self.driver.find_element(By.CSS_SELECTOR, "a[href*='fechar_pastas'")
        
        if not webe.is_displayed(): # if not openned already
            abrir_pastas = wait(self.driver, 10).until(
                expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR,"a[href*='abrir_pastas'")))
            # since it is in a permanent overlay by other elements of the page
            # https://stackoverflow.com/a/46601444/1207193
            # no other option then click in it using javascript
            id = abrir_pastas.get_attribute('id')
            self.driver.execute_script(f"document.getElementById('{id}').click()")
        
    def listDocs(self):
        """return a list of pairs
            [ doc title, doc protocol number ...]
            for each doc on documents tree
        """        
        self.abrirPastas()
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        edocs = soup.select("a.clipboard + a span:first-child") # getting all docs on process
        # len(docs)
        docs = []
        for edoc in edocs[1:]: #ignore first that's the process NUP
            nup = re.search('(\d{6,})', edoc['title']).group() 
            name = re.sub("[()]", "", edoc['title'].replace(nup, '')).strip() # anything except ( )            
            docs.append([name, nup])
        return docs 

    def barCmdsReopen(self):
        """Return reopen button from `processBarCmds`
        if process can be reopened 
        return reopen button or
        None if such button doesn't exist"""
        bts = self.barCmdsGet()
        try : 
            if bts[4].find_element(By.TAG_NAME, 'img').get_property('title') == 'Reabrir Processo':
                return bts[4]
        except:
            return None    
 
    def barCmdsGet(self):
        self._mainMenu()
        wait(self.driver, 10).until(
            expected_conditions.frame_to_be_available_and_switch_to_it(
            (By.CSS_SELECTOR,'iframe#ifrVisualizacao')))
        # wait for infraBarraComandos botoes available
        wait(self.driver, 10).until(
            expected_conditions.element_to_be_clickable(
            (By.CSS_SELECTOR,'div#divArvoreAcoes.infraBarraComandos')))
        botoes = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".botaoSEI")))
        return botoes
    
    def barCmdsClick(self, index):
        """
        get barra botoes (list) and botao by index
            0 - incluir documento
            3 - acompanhamento especial
        """
        botoes = self.barCmdsGet()
        if len(botoes) <= 9:
            raise Exception(f"Processo {self.ProcessoNUP} não aberto na sua unidade")
        botoes[index].click()
                 
    def isOpen(self):
        """return True if `processBarCmds` len is 22"""
        try : 
            lenbarcmds = len(self.barCmdsGet())
        except: # if not open may not even show the processbar buttons
            return False 
        else:
            return lenbarcmds == 22
        # 4 reabrir processo if len <=9     

    def incluiDoc(self, code=0):
        """
        Precisa estar na página de um processo. E com frame de commands selected.

        code:
            0  - ' Externo' - default
            1  - 'Termo de Abertura de Processo Eletrônico'
            2  - 'Nota Técnica' - only one to be used!
        """
        texts = [ ' Externo', 'Termo de Abertura de Processo Eletrônico', 'Nota Técnica']
        self.barCmdsClick(0)  # botao[0] incluir doc
        items = wait(self.driver, 10).until(
            expected_conditions.visibility_of_all_elements_located(
            (By.CLASS_NAME, "ancoraOpcao")))
        # a ordem dos elementos está mudando
        # melhor usar xpath by value
        # items[code].click() # Externo / Analise / Declaracao etc....
        element = self.driver.find_element(By.XPATH, "//a[.='"+texts[code]+"']")
        element.click()

    def acompEspecial(self, option=1, obs=None):
        """ 1 == analises andre """
        self.barCmdsClick(3) # botao[3] acompanhamento especial
        drop_down = wait(self.driver, 10).until(
            expected_conditions.element_to_be_clickable((By.ID, 'selGrupoAcompanhamento')))
        select = Select(drop_down)
        select.options[option].click()
        botoes = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CLASS_NAME, "infraButton")))
        botoes[0].click() # Salvar

    def atribuir(self, pessoa='elaine.marques - Elaine Cristina Pimenta Marques'):
        self.barCmdsClick(7) # botao[7] atribuir
        drop_down = wait(self.driver, 10).until(
            expected_conditions.element_to_be_clickable((By.ID, 'selAtribuicao')))
        select = Select(drop_down)
        select.select_by_visible_text(pessoa)
        select.first_selected_option.click()
        botoes = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CLASS_NAME, "infraButton")))
        botoes[0].click() # Salvar