from selenium import webdriver

from .....web.selenium import (
    send_keys,
    click
)

class Sei:
    # https://book.pythontips.com/en/latest/context_managers.html
    # sei.driver.quit() works out of the box
    """
    Use as a context manager __enter___ and __exit___ methods
    
    with SEI(user, pass) as sei:
        do something.

    """
    def __init__(self, user, passwd, headless=True, login=True):
        """
        user: str
            user
        passwd : str
            password
        headless : True
            don't start visible window
        login: bool 
            Makes Login on start
        """
        self.headless : bool = headless         
        self.user : str = user 
        self.passwd : str = passwd 
        self.driver : webdriver.Chrome | None = None
        if login:
            self._login()

    def __enter__(self): 
        return self

    def __exit__(self, type, value, traceback):        
        self.driver.quit()        
          
    def _login(self):
        options = webdriver.ChromeOptions()
        # not exactly needed since I am downloading pdfs with requets
        # but keeping it since it makes navigation faster ? when not loading pdf's 
        options.add_experimental_option('prefs', {            
            "download.prompt_for_download": False, # To auto download the file
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True # It will not show PDF directly in chrome
        })
        if self.headless:
            options.add_argument("headless") # to hide window in 'background'
        self.driver = webdriver.Chrome(options=options)        
        self.driver.get("https://sei.anm.gov.br/")        
        send_keys(self.driver, "input#txtUsuario", self.user, clear=True)
        send_keys(self.driver, "input#pwdSenha", self.passwd, clear=True)        
        send_keys(self.driver, "select#selOrgao", "ANM")
        click(self.driver, "button#sbmLogin")        
        # to avoid problems start saving main window handle
        self.mainwindow = self.driver.current_window_handle
        self.closeOtherWindows()        

    def pesquisaProcesso(self, ProcessoNUP):
        self.driver.switch_to.default_content() # go back main document        
        send_keys(self.driver, "input#txtPesquisaRapida", ProcessoNUP + "\n") # "\n" in the end to Hit Enter        

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
