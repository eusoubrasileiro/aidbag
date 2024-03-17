from ....web import htmlscrap
import sys 

from .util import (
    fmtPname
)

# SCM URL LIST
# TODO complete the list of links
#'https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx' # might change again
scm_dados_processo_main_url='https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx'
scm_timeout=(2*60)

urls = { 'basic' : scm_dados_processo_main_url,
         'poligon' : scm_dados_processo_main_url } 

class ErrorProcessSCM(Exception):
    """ Scm Page Request errors.
    
    Like: 
    Object reference not set to an instance of an object. 
    Could not fetch process from SCM. Probably missing or corrupted on the database.

    Or others like not found errors
    """

def pageRequest(pagename, processostr, wpage, fmtName=True):
    """   Get & Post na página dados do Processo do Cadastro  Mineiro (SCM)
        * pagename : str
            page name to requets from `urls`
        * processostr:  str
            process unique name 
        * wpage: requests.wpage        
            copied before using, nothing is persisted            
        * fmtName: True (default)
            wether to call `fmtPname` on `processostr` before http-request
        
        returns: 
            wpage.response.text, url, wpage.session
    """
    
    if fmtName:
        processostr = fmtPname(processostr)        
    wpage = wpage.copy() # to make session unique across each proces/request
    if pagename == 'basic':         
        wpage.get(urls['basic'])
        formcontrols = {
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
            'ctl00$conteudo$txtNumeroProcesso': processostr,
            'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
            '__VIEWSTATEENCRYPTED': ''}
        formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)
        try:
            wpage.post(scm_dados_processo_main_url,
                    data=formdata, timeout=scm_timeout)
        except htmlscrap.requests.exceptions.HTTPError as http_error:
            if "Object reference not set to an instance of an object" in wpage.response.text:                
                raise ErrorProcessSCM(f"Processo {processostr} corrupted on SCM database. Couldn't download.")
            else: # connection, authentication errors or others... must re-raise
                raise                
        # alert('Processo não encontrado') present
        if "Processo não encontrado" in wpage.response.text:            
            raise ErrorProcessSCM(f"Processo {processostr} not found! Couldn't download.") 
    elif pagename == 'poligon': # first connection to 'dadosbasicos' above MUST have been made before
        html, _ = pageRequest('basic', processostr, wpage) # ask basicos first        
        formcontrols = {
            'ctl00$conteudo$btnPoligonal': 'Poligonal',
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
        formdata = htmlscrap.formdataPostAspNet(html, formcontrols)
        wpage.post(scm_dados_processo_main_url, 
                   data=formdata, timeout=scm_timeout)
        if 'Erro ao mudar a versão para a data selecionada.' in wpage.response.text:
            raise ErrorProcessSCM(f"Processo {processostr} failed download poligonal from SCM database.")
    return wpage.response.text, urls['basic']