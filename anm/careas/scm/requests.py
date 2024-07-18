import sys 
from typing import Literal
from ....web import (    
    htmlscrap,
    wPageNtlm
    )
from requests.exceptions import (
    HTTPError,
    ReadTimeout
)
from ..config import config

# SCM URL LIST
# TODO complete the list of links
#'https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx' # might change again
scm_processo_main_url='https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx'


class RequestsSCMException(Exception):
    """
    Generic Scm Page request error
    """

class BasicosErrorSCM(RequestsSCMException):
    """
    Basicos Page Tab related errors. Like:
    1. Object reference not set to an instance of an object. 
    2. Could not fetch process from SCM. (Probably corrupted on the database)    
    """

class PoligonalErrorSCM(RequestsSCMException):
    """
    Poligonal Page Tab related errors. Like:
    Not accessible on page or not found etc.
    """

class NotFoundErrorSCM(RequestsSCMException):
    """
    Process not found
    """
    

def pageRequest(pagename : Literal['basic', 'polygon'], processopud : str, wpage : wPageNtlm, retry_on_error : int = 2):
    """   Get & Post na página dados do Processo do Cadastro  Mineiro (SCM)
        * pagename : str
            page name to requets from `urls`
        * processopud:  str
            process unique name 
        * wpage: requests.wpage        
            copied before using, nothing is persisted            
        
        returns: 
            wpage.response.text, url, wpage.session
    """    
    # remind: wpage-requests-session is unique for each thread/process
    try:
        if pagename == 'basic':            
            wpage.get(scm_processo_main_url, timeout=config['scm']['timeout'])     
            formcontrols = {
                'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
                'ctl00$conteudo$txtNumeroProcesso': processopud,
                'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
                '__VIEWSTATEENCRYPTED': ''}
            formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)        
            wpage.post(scm_processo_main_url,
                    data=formdata, timeout=config['scm']['timeout'])
            if "Processo não encontrado" in wpage.response.text:            
                raise NotFoundErrorSCM(f"Processo {processopud} not found! Couldn't download.") 
            elif ("ctl00_conteudo_gridPessoas" not in wpage.response.text or 
                    "ctl00_conteudo_gridEventos" not in wpage.response.text): # integrity check of 'gridPessoas'
                raise BasicosErrorSCM(f"Processo {processopud} download error.")
        elif pagename == 'polygon': # first connection to 'dadosbasicos' above MUST have been made before
            if (not hasattr(wpage, 'response') or 
                'ctl00$conteudo$btnPoligonal' not in wpage.response.text or 
                processopud not in wpage.response.text): # must be response to same process
                pageRequest('basic', processopud, wpage, retry_on_error=retry_on_error) # goto basicos page first
            formcontrols = {    
                'ctl00$conteudo$btnPoligonal': 'Poligonal',
                'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
            formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)
            wpage.post(scm_processo_main_url, 
                    data=formdata, timeout=config['scm']['timeout'])
            if 'Erro ao mudar a versão para a data selecionada.' in wpage.response.text:
                raise PoligonalErrorSCM(f"Processo {processopud} failed download poligonal from SCM database.")    
    except (RequestsSCMException, HTTPError, ReadTimeout) as e:
        if retry_on_error: 
            return pageRequest(pagename, processopud, wpage, retry_on_error=retry_on_error-1)
        elif isinstance(e, RequestsSCMException):
            raise
        elif isinstance(e, HTTPError):
            if "Object reference not set to an instance of an object" in wpage.response.text:                
                raise BasicosErrorSCM(f"Processo {processopud} corrupted on SCM database. Couldn't download.")
            ## todo implement error check for other specific http errors
        elif isinstance(e, ReadTimeout):
            if pagename == 'basic':
                raise BasicosErrorSCM(f"Processo {processopud} Couldn't download. Timeout error x2.") 
            elif pagename == 'polygon':
                raise PoligonalErrorSCM(f"Processo {processopud} Couldn't download. Timeout error x2.") 
    return wpage.response.text, wpage.response.url