import sys

sys.path.append("..") # Adds higher directory to python modules path.
from web import htmlscrap as hscrap
from anm import scm

from bs4 import BeautifulSoup
import pandas as pd


def PesquisaSICOPSimples(wpage, uorg, number, year):
    """
    Pesquisa Simples DIRETA URL - precisa uorg
    link e.g.:
        https://sistemas.dnpm.gov.br/sicopii/P/UnicoProcesso.asp?Numero=272038302301995
    """
    processwget = uorg+number+year # NUP w/out s. chars
    # must be here to get Asp Cookie for SICOP
    wpage.get('https://sistemas.dnpm.gov.br/sicopii/SICOP.asp')
    wpage.get('https://sistemas.dnpm.gov.br/sicopii/P/UnicoProcesso.asp?Numero='+processwget)
    soup = BeautifulSoup(wpage.response.content, features="lxml")
    return hscrap.tableDataText(soup.find('table', border="1"))

def PesquisaSICOP(wpage, processo_number, processo_year):
    """
    1. Must be authenticated with a aspnet Session Id
    2. Be aware that Fiddler causes problems with SSL authenthication making 1 impossible
    """
    # must be here to get Asp Cookie for SICOP
    wpage.get('https://sistemas.dnpm.gov.br/sicopii/SICOP.asp')

    formdata = {
        'CodProcessoAno': processo_year,
        'CodProcessoOrgao': '',
        'CodProcessoSeq': processo_number,
        'Pesquisar.x': '59',
        'Pesquisar.y': '18'
    }
    # consulta
    wpage.post('https://sistemas.dnpm.gov.br/sicopii/P/Alterar/AtualizarProcesso.asp?Origem=PesquisaSimples', data=formdata)

    if not wpage.response.text.find(processo_number+'-'+processo_year):
        print('Nao achou! Não autenticado em sistemas.dnpm.gov.br?')
        return False

    soup = BeautifulSoup(wpage.response.content, features="lxml")
    table = hscrap.tableDataText(soup)
    table = pd.DataFrame(table[1:], columns=['Processo', 'Interessado'])

    if len(table) > 1:
        # unidade preferencial em caso de mais de um processo
        prefer_uorgao='48403'#'CodProcessoOrgao'
        processostr = table[table.Processo.str.contains(prefer_uorgao)].Processo.values[0].split('.')
    else:
        processostr = table.Processo.values[0].split('.')

    uorg = processostr[0]
    processostr = processostr[1]

    processo_number, processo_year = scm.numberyearPname(processostr)

    table = PesquisaSICOPSimples(wpage, uorg, processo_number, processo_year)

    # just first line, where it is now
    return pd.DataFrame(table[1:2], columns=table[0])


def PesquisasSICOP(wpage, listprocessostr, verbose=True):
    df = pd.DataFrame()
    for processostr in listprocessostr:
        processo_number, processo_year = scm.numberyearPname(processostr)
        #print(processo_number, processo_year)
        result = PesquisaSICOP(wpage, processo_number, processo_year)
        result['PROCESSO'] = processostr
        newcolumns = [result.columns[-1],  *result.columns[:-1]]
        result = result[newcolumns]
        df = df.append(result)
    if verbose:
        print(df)
    else:
        return df
