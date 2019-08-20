import time
from requests_ntlm import HttpNtlmAuth
import re

import os, sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class wPage: # html  webpage scraping with soup and requests
    def __init__(self, session): # requests session
        self.session = session

    def __init__(self, user, passwd):
        self.session = requests.Session()
        self.session.auth = HttpNtlmAuth(user, passwd)

    def findAllnSave(self, pagefolder, tag2find='img', inner='src', verbose=False):
        if not os.path.exists(pagefolder): # create only once
            os.mkdir(pagefolder)
        for res in self.soup.findAll(tag2find):   # images, css, etc..
            try:
                filename = os.path.basename(res[inner])
                # dealing with weird resource names (RENAME it to save)
                if len(filename) > 30: # too big  weird names
                    extension = os.path.splitext(filename)[1]
                    if len(extension) > 5: # weird string with dots
                        extension = ''
                    filename = 'file_' + tag2find + '_' +str(hash(filename)) + extension # RENAMED file
                #fileurl = url.scheme + '://' + url.netloc + urljoin(url.path, res.get(inner))
                fileurl = urljoin(self.url, res.get(inner))
                # renamed and saved file path
                # res[inner] # may or may not exist
                filepath = os.path.join(pagefolder, filename)
                res[inner] = filepath
                # like a '<script' tag where the script is inplace
                if not os.path.isfile(filepath): # was not downloaded
                    with open(filepath, 'wb') as file:
                        filebin = self.session.get(fileurl)
                        file.write(filebin.content)
            except Exception as exc:
                if verbose:
                    print(exc, '\n', file=sys.stderr)

    def save(self, pagefilename='page'):
        """
        save html page and supported contents
        pagefilename  : specified folder
        """
        self.url = self.response.url
        self.soup = BeautifulSoup(self.response.text, features="lxml")
        pagefolder = pagefilename+'_files' # page contents
        self.findAllnSave(pagefolder, 'img', inner='src')
        self.findAllnSave(pagefolder, 'link', inner='href')
        self.findAllnSave(pagefolder, 'script', inner='src')
        with open(pagefilename+'.html', 'w') as file:
            file.write(self.soup.prettify())

    def post(self, arg, save=True, **kwargs):
        """save : save response overwriting the last"""
        resp = self.session.post(arg, **kwargs)
        if save:
            self.response = resp
        return resp

    def get(self, arg, save=True, **kwargs):
        """save : save response overwrites the last"""
        resp = self.session.get(arg, **kwargs)
        if save:
            self.response = resp
        return resp

def formdataPostAspNet(response, formcontrols):
    """
    Creates a formdata dict based on dict of formcontrols to make a post request
    to an AspNet html page. Use the previous html get `response` to extract the AspNet
    states of the page.

    response : from page GET request
    formcontrols : dict from webpage with values assigned
    """
    # get the aspnet form data neeed with bsoup
    soup = BeautifulSoup(response.content, features="lxml")
    aspnetstates = ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION', '__EVENTTARGET',
                    '__EVENTARGUMENT', '__VIEWSTATEENCRYPTED' ];
    formdata = {}
    for aspnetstate in aspnetstates: # search for existing aspnet states and get its values when existent
        result = soup.find('input', {'name': aspnetstate})
        if not (result is None):
            formdata.update({aspnetstate : result['value']})

    # include aditional form controls params
    formdata.update(formcontrols)
    #return formdata
    return formdata


class Form1:
    """Analise de Formulario 1"""
    def __init__(self, processostr, wpage):
        """
        processostr : numero processo format xxx.xxx/ano
        wpage : wPage html webpage scraping class com login e passwd preenchidos
        """
        self.processostr = processostr
        self.processo_number = processostr.split('/')[0].replace('.', '')
        self.processo_year = processostr.split('/')[1]
        self.wpage = wpage
        # pasta padrao salvar processos formulario 1
        self.secorpath = r"D:\Users\andre.ferreira\Documents\Controle de Áreas"
        # pasta deste processo
        self.processo_path = os.path.join(self.secorpath,
                    self.processo_number+'-'+self.processo_year )
        if not os.path.exists(self.processo_path): # cria a pasta  se nao existir
            os.mkdir(self.processo_path)

    def salvaDadosGeraisSCM(self):
        ### Abre página dados do Processo do Cadastro  Mineiro
        # portal ortoga Cadastro mineiro
        self.wpage.get('https://sistemas.dnpm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx')
        formcontrols = {
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
            'ctl00$conteudo$txtNumeroProcesso': self.processostr,
            'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
            '__VIEWSTATEENCRYPTED': ''}
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('https://sistemas.dnpm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx',
                      data=formdata)
        dadosgeraisfname = 'scm_dados_'+self.processo_number+self.processo_year
        # sobrescreve
        self.wpage.save(os.path.join(self.processo_path, dadosgeraisfname))

    def salvaDadosGeraisSCMPoligonal(self):
        formcontrols = {
            'ctl00$conteudo$btnPoligonal': 'Poligonal',
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('https://sistemas.dnpm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx',
                      data=formdata)
        # sobrescreve
        dadosgeraisfname = 'scm_dados_polygonal_'+self.processo_number+self.processo_year
        self.wpage.save(os.path.join(self.processo_path, dadosgeraisfname))

    def salvaRetiradaInterferencia(self):
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1')
        formcontrols = {
            'ctl00$cphConteudo$txtNumProc': self.processo_number,
            'ctl00$cphConteudo$txtAnoProc': self.processo_year,
            'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # must be timout 50
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1',
                data=formdata, timeout=50)
        if not ( self.wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'):
            print("Falhou salvar Retirada de Interferencia",  file=sys.stderr)
            return
        #wpage.response.url # response url deve ser 'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'
        fname = 'sigareas_rinterferencia_'+processo_number+processo_year
        self.wpage.save(os.path.join(self.processo_path, fname))

    def cancelaUltimoEstudoInterferencia(self):
        """Danger Zone - cancela ultimo estudo em aberto sem perguntar mais nada"""
        self.wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx')
        #self.wpage.save('cancelar_estudo')
        formcontrols = {
            'ctl00$cphConteudo$txtNumero': self.processo_number,
            'ctl00$cphConteudo$txtAno': self.processo_year,
            'ctl00$cphConteudo$btnConsultar': 'Consultar'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        # Consulta
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        # wpage.save('cancelar_estudo')
        # Cancela
        formcontrols = {
            'ctl00$cphConteudo$txtNumero': self.processo_number,
            'ctl00$cphConteudo$txtAno': self.processo_year,
            'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.x': '12',
            'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.y': '12'
        }
        formdata = formdataPostAspNet(self.wpage.response, formcontrols)
        self.wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
        #self.wpage.save('cancelar_estudo')
