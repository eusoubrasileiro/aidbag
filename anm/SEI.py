from selenium.webdriver import Chrome
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select # drop down select
import time

class SEI:
    def __init__(self, user, passwd, headless=False, implicit_wait=10):
        """Makes Login on start

        user: str
            user
        passwd : str
            password
        headless : True
              don't start visible window

        TODO:
            Only use explicit wait as recommended in SO

        """
        options = ChromeOptions()
        if headless:
            options.add_argument("headless") # to hide window in 'background'
        driver = Chrome(options=options)
        driver.implicitly_wait(implicit_wait) # seconds
        driver.get("https://sei.anm.gov.br/")
        username = driver.find_element_by_id("txtUsuario")
        password = driver.find_element_by_id("pwdSenha")
        orgao = driver.find_element_by_id("selOrgao")
        username.send_keys(user)
        password.send_keys(passwd)
        orgao.send_keys("ANM")
        driver.find_element_by_name("sbmLogin").click()
        self.driver = driver

    def Pesquisa(self, ProcessoNUP):
        self.driver.switch_to.default_content() # go back main document
        processo = wait(self.driver, 10).until(
            expected_conditions.visibility_of_element_located((By.ID, 'txtPesquisaRapida')))
        processo.send_keys(ProcessoNUP)
        processo = wait(self.driver, 10).until( # migth be unnecessary
            expected_conditions.visibility_of_element_located((By.ID, 'txtPesquisaRapida')))
        processo.send_keys(Keys.ENTER)

    def _processoMainMenu(self):
        """back to main menu processo"""

        # not working
        # # getting when StaleElement happens
        # # getting one element from the right frame
        # # guarantee the right frame has been refreshed too
        # self.driver.switch_to.default_content() # go back parent main document
        # wait(self.driver, 10).until(
        #     expected_conditions.frame_to_be_available_and_switch_to_it(
        #     (By.CSS_SELECTOR,'iframe#ifrVisualizacao')))
        # botoes = wait(self.driver, 10).until(
        #    expected_conditions.presence_of_all_elements_located(
        #    (By.CSS_SELECTOR, ".botaoSEI")))
        # botao = botoes[0]
        self.driver.switch_to.default_content() # go to parent main document
        wait(self.driver, 10).until( # then go to frame panel left
            expected_conditions.frame_to_be_available_and_switch_to_it(
            (By.CSS_SELECTOR,'iframe#ifrArvore')))
        anchors = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CSS_SELECTOR,'#topmenu a')))
        # the click
        # forces a redraw of left frame and after 2/3 seconds
        # of the right frame
        # when that is finished we can return the control
        # otherwise StaleElementReferenceException
        # will be thrown when getting .botaoSEI
        anchors[1].click() # # 1 click to open main menu on processo name

        # not working with above
        # # guarantee the right frame has been refreshed too
        # wait(self.driver, 10).until(
        #    expected_conditions.staleness_of(botao))
        # solved all problems created above
        # of refreshing delay
        time.sleep(3)
        self.driver.switch_to.default_content()


    def _processoBarraBotoes(self, index):
        """
        get barra botoes (list) and botao by index
            0 - incluir documento
            3 - acompanhamento especial
        """
        self._processoMainMenu()
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
        return botoes[index]

    def ProcessoIncluiDoc(self, code=0):
        """
        Precisa estar na página de um processo.

        code:
            0 - Externo - default
            1 - Analise
            2 - Declaração
            3 - Despacho
        ...

        """
        self._processoBarraBotoes(0).click()  # botao[0] incluir doc
        items = wait(self.driver, 10).until(
            expected_conditions.visibility_of_all_elements_located(
            (By.CLASS_NAME, "ancoraOpcao")))
        items[code].click() # Externo / Analise / Declaracao etc....

    def ProcessoIncluiAEspecial(self, option=1, obs=None):
        """ 1 == analises andre """
        self._processoBarraBotoes(3).click() # botao[3] acompanhamento especial
        drop_down = wait(self.driver, 10).until(
            expected_conditions.element_to_be_clickable((By.ID, 'selGrupoAcompanhamento')))
        select = Select(drop_down)
        select.options[option].click()
        botoes = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CLASS_NAME, "infraButton")))
        botoes[0].click() # Salvar

    def ProcessoAtribuir(self, option=12):
        """ 12 == chefe"""
        self._processoBarraBotoes(7).click() # botao[7] atribuir
        drop_down = wait(self.driver, 10).until(
            expected_conditions.element_to_be_clickable((By.ID, 'selAtribuicao')))
        select = Select(drop_down)
        select.options[option].click()
        botoes = wait(self.driver, 10).until(
            expected_conditions.presence_of_all_elements_located(
            (By.CLASS_NAME, "infraButton")))
        botoes[0].click() # Salvar















# Using Python Requests
# Faster but too much work!!
# from anm import secor
# from anm import scm
# import tqdm
# import importlib
# Saved for later
# wpage = secor.wPage()
# wpage.get(r'https://sei.anm.gov.br/sip/login.php?sigla_orgao_sistema=ANM&sigla_sistema=SEI')
# cookies = {'ANM_SEI_dados_login' : 'andre.ferreira/26/',
#           'ANM_SEI_andre.ferreira_menu_tamanho_dados' : '79',
#            'ANM_SEI_andre.ferreira_menu_mostrar' : 'S'}
# formdata = {
#     'txtUsuario': 'andre.ferreira',
#     'pwdSenha': '12345678',
#     'selOrgao': '26',
#     'chkLembrar': 'on',
#     'sbmLogin': 'Acessar'}

## SEI hdnToken
# import re
# key, value = re.findall('name="(hdnToken.{32}).*value="(.{32})',wpage.response.text)[0]
# formdata.update({key : value})
#
# # not using
# #import requests
# #wpage.session.cookies = requests.cookies.merge_cookies(wpage.session.cookies, cookies)
# #wpage.session.cookies
# wpage.post('https://sei.anm.gov.br/sip/login.php?sigla_orgao_sistema=ANM&sigla_sistema=SEI',
#            data=formdata, cookies=cookies)
# wpage.session.cookies
#
# ## Busca processo nome
# # https://sei.anm.gov.br/sei/controlador.php
#
# # **query string parameters**
#
# #     acao = protocolo_pesquisa_rapida
# #     infra_sistema = 100000100
# #     infra_unidade_atual = 110000514
# #     infra_hash = c7be619c09e5197678e76c710d7e7de01c67814c19e66c409b4da5900e4cf493 # by response url
#
# wpage.response.url
#
# cookies['ANM_SEI_andre.ferreira_menu_mostrar'] = 'N'
# cookies
#
# formdata = {
#     'txtPesquisaRapida': r'48054.830302/2020-68' }
#
# # params={'acao': 'protocolo_pesquisa_rapida',
# #         'infra_sistema' : re.findall('infra_sistema=(\d{9})', wpage.response.url)[0],
# #         'infra_unidade_atual' :  re.findall('infra_unidade_atual=(\d{9})', wpage.response.url)[0],
# #         'infra_hash' :  re.findall('infra_hash=(.{64})', wpage.response.url)[0],
# #        }
# # params
# from bs4 import BeautifulSoup
# soup = BeautifulSoup(wpage.response.text)
# # use bsoup to get the correct link that already includes the correct infra_hash
# # above is using the wrong infra_hash
#
# url_query = soup.select('form[id="frmProtocoloPesquisaRapida"]')[0]['action']
# url_query
# 'https://sei.anm.gov.br/sei/'+url_query
# wpage.post('https://sei.anm.gov.br/sei/'+url_query,
#            data=formdata, cookies=cookies)
#
# wpage.get(wpage.response.url, cookies=cookies)
#
# have to search for the correct iframe 2 iframes  on Processo Page
# soup = BeautifulSoup(wpage.response.text)
# iframes = soup.find_all('iframe')
# iframes[1]
#
# # from IPython.core.display import display, HTML
# # display(HTML(wpage.response.text))
