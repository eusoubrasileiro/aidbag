import os 
from bs4 import BeautifulSoup
import pandas as pd 
from ..config import config 
from ....web import htmlscrap
from ..scm import (
    numberyearPname,
    fmtPname
)

def fetch_save_Html(wpage, number, year, html_file, download=True):
    if not os.path.exists(html_file) or download:
        wpage.get('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1')
        formcontrols = {
            'ctl00$cphConteudo$txtNumProc': number,
            'ctl00$cphConteudo$txtAnoProc': year,
            'ctl00$cphConteudo$btnEnviarUmProcesso': 'Processar'
        }
        formdata = htmlscrap.formdataPostAspNet(wpage.response, formcontrols)
        wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/ConsultaProcesso.aspx?estudo=1',
                data=formdata, timeout=config['secor_timeout'])
        if not ( wpage.response.url == r'http://sigareas.dnpm.gov.br/Paginas/Usuario/Mapa.aspx?estudo=1'):
            soup = BeautifulSoup(wpage.response.text, 'html.parser')                        
            # falhou salvar Retirada de Interferencia return error message                        
            return  soup.find('span', { 'class' : 'MensagemErro' }).text.strip() 
        wpage.save(html_file)
    return ''    

def cancelaUltimo(wpage, number, year):
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
    formdata = htmlscrap.formdataPostAspNet(wpage.response, formcontrols)    
    wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata) # Consulta
    formcontrols = { # Cancela
        'ctl00$cphConteudo$txtNumero': number,
        'ctl00$cphConteudo$txtAno': year,
        'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.x': '12',
        'ctl00$cphConteudo$rptEstudo$ctl00$btnCancelar.y': '12'
    }
    formdata = htmlscrap.formdataPostAspNet(wpage.response, formcontrols)
    wpage.post('http://sigareas.dnpm.gov.br/Paginas/Usuario/CancelarEstudo.aspx', data=formdata)
    if 'Estudo excluído com sucesso.' in wpage.response.text:
        return True 
    return False

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
    df.Processo = df.Processo.apply(lambda x: fmtPname(x)) # standard names
    return df