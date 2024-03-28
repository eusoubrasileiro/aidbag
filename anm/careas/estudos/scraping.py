import os 
from bs4 import BeautifulSoup
import pandas as pd 
from ..config import config 
from ....web import htmlscrap
from ..scm import (
    numberyearPname,
    fmtPname
)

class CancelaUltimoEstudoFailed(Exception):
    """could not cancel ultimo estudo sigareas"""
    pass

class DownloadInterferenciaFailed(Exception):
    """could not download retirada de interferencia"""
    pass 

def cancelaUltimo(wpage, number, year, retry_on_error=3):
    """Danger Zone - cancela ultimo estudo em aberto sem perguntar mais nada:
    - estudo de retirada de Interferencia
    - estudo de opcao de area        
    """
    wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx')
    formcontrols = {
        'ctl00$cphConteudo$txtNumero': number,
        'ctl00$cphConteudo$txtAno': year,
        'ctl00$cphConteudo$btnConsultar': 'Consultar'
    }
    formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)    
    wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata) # Consulta
    formcontrols = { # Cancela
        'ctl00$cphConteudo$txtNumero': number,
        'ctl00$cphConteudo$txtAno': year,
        'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.x': '12',
        'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.y': '12'
    }
    formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)
    wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
    if not 'Estudo excluído com sucesso.' in wpage.response.text:   
        if retry_on_error:
            return cancelaUltimo(wpage, number, year, retry_on_error-1)
        else:
            raise CancelaUltimoEstudoFailed()
    return True
            

def fetch_save_Html(wpage, number, year, html_file, retry_on_error=3):
    wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1')
    formcontrols = {
        'ctl00$cphConteudo$txtNumProc': number,
        'ctl00$cphConteudo$txtAnoProc': year,
        'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
    }
    formdata = htmlscrap.formdataPostAspNet(wpage.response.text, formcontrols)
    wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1',
            data=formdata, timeout=config['sigareas']['timeout'])
    if not ( wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'):
        soup = BeautifulSoup(wpage.response.text, 'html.parser')                        
        # falhou salvar Retirada de Interferencia return error message                        
        error_status = soup.find('span', { 'class' : 'MensagemErro' }).text.strip()                     
        if ('O sistema se comportou de forma inesperada.' in error_status):
            if retry_on_error: 
                fetch_save_Html(wpage, number, year, html_file, retry_on_error-1)                          
            else:
                raise DownloadInterferenciaFailed(error_status)     
        if ('Cancele o estudo existente para realizar novo estudo.' in error_status):
            cancelaUltimo(wpage, number, year)
            fetch_save_Html(wpage, number, year, html_file, retry_on_error)
    else:
        wpage.saveSimpleHTML(html_file)    
 



def getEventosSimples(wpage, processostr):
    """ Retorna tabela de eventos simples para processo especificado
    wpage : class wPage
    processostr : str
    return : (Pandas DataFrame)"""
    processo_number, processo_year = numberyearPname(processostr)
    wpage.get(('http://sigareas.dnpm.gov.br/Paginas/Usuario/ListaEvento.aspx?processo='+
          processo_number+'_'+processo_year))
    htmltxt = wpage.response.content
    soup = BeautifulSoup(htmltxt, features="lxml")
    eventstable = soup.find("table", {'class': "BordaTabela"})
    rows = htmlscrap.tableDataText(eventstable)
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return df