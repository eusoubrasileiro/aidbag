from selenium.webdriver import Chrome
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select # drop down select
from selenium.common import exceptions
import time, sys
from bs4 import BeautifulSoup
import re 




class Sei:
    def __init__(self, user, passwd, headless=False, implicit_wait=10, login=True):
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
        self.options = options 
        self.implicit_wait = implicit_wait
        self.user = user 
        self.passwd = passwd 
        if login:
            login()
        

    def login(self):
        driver = Chrome(options=self.options)
        self.driver = driver
        driver.implicitly_wait(self.implicit_waitt) # seconds
        driver.get("https://sei.anm.gov.br/")
        username = driver.find_element(By.ID,"txtUsuario")
        password = driver.find_element(By.ID,"pwdSenha")
        orgao = driver.find_element(By.ID,"selOrgao")
        username.send_keys(self.user)
        password.send_keys(self.passwd)
        orgao.send_keys("ANM")
        driver.find_element(By.NAME,"sbmLogin").click()
        
        # to avoid problems start saving main window handle
        self.mainwindow = self.driver.current_window_handle
        # close disturbing and problematic popups if showing up
        try:  # I disabled it ... just try
            wait(self.driver, 10).until(expected_conditions.number_of_windows_to_be(2))
            self.closeOtherWindows()
        except exceptions.TimeoutException:
            print("Ignoring start pop-up. Did you disabled it?", file=sys.stderr)
        

    # context manager support so bellow works.
    # with SEI(user, pass) as sei:
    #   do something.
    # https://book.pythontips.com/en/latest/context_managers.html
    # sei.driver.quit() works out of the box
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.driver.quit()
        #return True # excetions were handled if True is returned 

    def pesquisaProcesso(self, ProcessoNUP):
        self.driver.switch_to.default_content() # go back main document
        processo = wait(self.driver, 10).until(
            expected_conditions.visibility_of_element_located((By.ID, 'txtPesquisaRapida')))
        processo.send_keys(ProcessoNUP)
        processo = wait(self.driver, 10).until( # migth be unnecessary
            expected_conditions.visibility_of_element_located((By.ID, 'txtPesquisaRapida')))
        processo.send_keys(Keys.ENTER)

    def closeOtherWindows(self):
        """close all other windows different from initial main window (e.g. popups)"""
        for windowh in self.driver.window_handles:
            # window list of handles is not ordered            
            if windowh != self.mainwindow:
                self.driver.switch_to.window(windowh)
                self.driver.switch_to.default_content() 
                self.driver.close()    
        self.driver.switch_to.window(self.mainwindow)
        self.driver.switch_to.default_content()        

















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
