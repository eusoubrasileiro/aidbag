from ....web import htmlscrap

from .util import (
    fmtPname
)

# SCM URL LIST
# TODO complete the list of links
#'https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx' # might change again
scm_dados_processo_main_url='https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx'
scm_timeout=(2*60)

urls = { 'dadosbasicos' : scm_dados_processo_main_url,
         'poligonal' : scm_dados_processo_main_url } 

def pageRequest(pagename, processostr, wpage, fmtName=True):
    """   Get & Post na página dados do Processo do Cadastro  Mineiro (SCM)
        * pagename : str
            page name to requets from `urls`
        * processostr:  str
            process unique name 
        * wpage: *WARNING*   
            it is CHANGED because it is passed by reference (Python default behavior)
            and `request.response` is returned nonetheless 
        * fmtName: True (default)
            wether to call `fmtPname` on `processostr` before http-request
    """
    if fmtName:
        processostr = fmtPname(processostr)
    if pagename == 'dadosbasicos': 
        wpage.get(urls['dadosbasicos'])
        formcontrols = {
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnConsultarProcesso',
            'ctl00$conteudo$txtNumeroProcesso': processostr,
            'ctl00$conteudo$btnConsultarProcesso': 'Consultar',
            '__VIEWSTATEENCRYPTED': ''}
        formdata = htmlscrap.formdataPostAspNet(wpage.response, formcontrols)
        wpage.post(scm_dados_processo_main_url,
                    data=formdata, timeout=scm_timeout)
        return wpage.response
    if pagename == 'poligonal': # first connection to 'dadosbasicos' above MUST have been made before
        pageRequest('dadosbasicos', processostr, wpage) # ask basicos first
        formcontrols = {
            'ctl00$conteudo$btnPoligonal': 'Poligonal',
            'ctl00$scriptManagerAdmin': 'ctl00$scriptManagerAdmin|ctl00$conteudo$btnPoligonal'}
        formdata = htmlscrap.formdataPostAspNet(wpage.response, formcontrols)
        wpage.post(scm_dados_processo_main_url,
                        data=formdata)
        return wpage.response