from ....web import (
    htmlscrap,
    wPageNtlm
    )
from ..config import config
import sys 

from .util import (
    fmtPname
)

# SCM URL LIST
# TODO complete the list of links
#'https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx' # might change again
scm_processo_main_url='https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx'


class ErrorProcessSCM(Exception):
    """ Scm Page Request errors.
    
    Like: 
    Object reference not set to an instance of an object. 
    Could not fetch process from SCM. Probably missing or corrupted on the database.

    Or others like not found errors
    """

def pageRequest(pagename : str, processostr : str, wpage : wPageNtlm, 
    fmtName: bool = True , retry_on_error : int = 3):
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
    # remind: wpage-requests-session is unique for each thread/process
    if fmtName:
        processostr = fmtPname(processostr)
    try:
        if pagename == 'basic':            
            wpage.get(scm_processo_main_url, timeout=config['scm']['scm_timeout'])     
            formcontrols = {
                'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
                'ctl00$conteudo$txtNumeroProcesso': processostr,
                'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
                '__VIEWSTATEENCRYPTED': ''}
            formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)        
            wpage.post(scm_processo_main_url,
                    data=formdata, timeout=config['scm']['scm_timeout'])
            if "Processo não encontrado" in wpage.response.text:            
                raise ErrorProcessSCM(f"Processo {processostr} not found! Couldn't download.") 
        elif pagename == 'polygon': # first connection to 'dadosbasicos' above MUST have been made before
            if (not hasattr(wpage, 'response') or 
                'ctl00$conteudo$btnPoligonal' not in wpage.response.text or 
                processostr not in wpage.response.text): # must be response to same process
                pageRequest('basic', processostr, wpage, retry_on_error=retry_on_error) # goto basicos page first
            formcontrols = {    
                'ctl00$conteudo$btnPoligonal': 'Poligonal',
                'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
            formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)
            wpage.post(scm_processo_main_url, 
                    data=formdata, timeout=config['scm']['scm_timeout'])
            if 'Erro ao mudar a versão para a data selecionada.' in wpage.response.text:
                if retry_on_error:
                    return pageRequest(pagename, processostr, wpage, retry_on_error=retry_on_error-1)
                raise ErrorProcessSCM(f"Processo {processostr} failed download poligonal from SCM database.")
    except htmlscrap.requests.exceptions.HTTPError as http_error:
        if "Object reference not set to an instance of an object" in wpage.response.text:                
            raise ErrorProcessSCM(f"Processo {processostr} corrupted on SCM database. Couldn't download.")
        elif 'xxxxxxxxxxx' in str(http_error): #  another case not yet implemented
            if retry_on_error: 
                return pageRequest(pagename, processostr, wpage, retry_on_error=retry_on_error-1)
            raise
        else: # connection, authentication errors or others... must re-raise???             
            raise                
    return wpage.response.text, wpage.response.url