from selenium.webdriver import Chrome
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.common.by import By

class SEI:
    def __init__(self, user, passwd, headless=False, implicit_wait=10):
        """Makes Login on start

        user: str
            user
        passwd : str
            password
        headless : True
              don't start visible window

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
        self.driver.switch_to.default_content() # go back from iframe or not
        processo = self.driver.find_element_by_id("txtPesquisaRapida")
        processo.send_keys(ProcessoNUP)
        processo.send_keys(Keys.ENTER)

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
        self.driver.switch_to.default_content() # go back from iframe or not
        self.driver.switch_to.frame(1) # barra de botoes
        incluir_doc = self.driver.find_elements_by_class_name("botaoSEI")[0]
        incluir_doc.click()
        items = self.driver.find_elements_by_class_name("ancoraOpcao")
        items[code].click()






















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
# import re
# key, value = re.findall('name="(hdnToken.{32}).*value="(.{32})',wpage.response.text)[0]
# formdata.update({key : value})
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
# soup = BeautifulSoup(wpage.response.text)
# iframes = soup.find_all('iframe')
# iframes[0]
#
# # from IPython.core.display import display, HTML
# # display(HTML(wpage.response.text))
