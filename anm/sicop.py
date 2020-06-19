import sys

sys.path.append("..") # Adds higher directory to python modules path.
from web import htmlscrap as hscrap
from anm import scm

from bs4 import BeautifulSoup
import pandas as pd
import re

def sicopNUP(NUPstr):
    """from a SICOP NUP string like
    27203..833157////2003xxx`
    return 3 member tuple using regex
    uorg, number, year = ('27203', '833157', '2003')
    """
    uorg, number, year = re.findall('(\d{5}).*(\d{6}).*(\d{4}).*', NUPstr)[0]
    return (uorg, number, year)

def fisicoHistoricoCompleto(wpage, sicopNUPstr):
    """
    Pesquisa Simples DIRETA URL: uorg + number +  year (SICOP NUP)
    link e.g.:
        https://sistemas.anm.gov.br/sicopii/P/UnicoProcesso.asp?Numero=272038302301995

    resultado tabela esquisita numero de rows par:

    SITUAÇÃO	UF	ÓRGÃO	DATA	HORA	PRIORIDADE	MOVIMENTADO	RECEBIDO	DATA REC.	REC. POR	GUIA
    TRAMITANDO	MG	MG_SEGDO - ARQUIVO	04/03/2009	17:28	NORMAL	eugenio.rocha	Sim	24/03/2009	paulo.avila	-
    Motivo: DESCONHECIDO
    Despacho:
    DESCONHECIDO	MG	MG_MG	04/03/2009	17:28	NORMAL	eugenio.rocha	Sim	-	-	-
    Motivo: DESCONHECIDO
    Despacho:
    """
    uorg, number, year = sicopNUP(sicopNUPstr) # NUP w/out s. chars
    NUPstr = uorg+number+year
    # must be here to get Asp Cookie for SICOP
    wpage.get('https://sistemas.anm.gov.br/sicopii/SICOP.asp')
    wpage.get('https://sistemas.anm.gov.br/sicopii/P/UnicoProcesso.asp?Numero='+NUPstr)
    soup = BeautifulSoup(wpage.response.content, features="lxml")
    return hscrap.tableDataText(soup.find('table', border="1"))

def fisicoSicopNUPs(wpage, processostr):
    """
    from scm-process str like '833157/2003' find volumes fisicos SICOP NUPs

    E.g.
    27203.833157/2003-45 no SEI corresponde ao fisico
    48403.833157/2003-45 no SICOP
    Assim a uorg do SEI é inutil, o processo físico pode usar outra uorg.

    Notes:
        must be authenticated with a aspnet Session Id
        be aware that Fiddler causes problems with SSL authenthication making 1 impossible
    """
    number, year = scm.numberyearPname(processostr)
    # must be here to get Asp Cookie for SICOP
    wpage.get('https://sistemas.anm.gov.br/sicopii/SICOP.asp')
    wpage.get('https://sistemas.anm.gov.br/sicopii/P/Procurar/ProcuraProcesso.asp')
    soup = BeautifulSoup(wpage.response.content, features="lxml")
    botao = soup.select_one('input[type=image]')
    # dimensions of botao changes from browser to browser etc.
    h, w = botao['height'], botao['width'] # maximum dimensions of botao Pesquisar
    h, w = int(h)/2, int(w)/2 # click on the center exactly
    formdata = {
        'CodProcessoOrgao' : '',
        'CodProcessoSeq': number,
        'CodProcessoAno': year,
        'I1.x': str(int(w)),
        'I1.y': str(int(h)),
    }
    # consulta
    wpage.post('https://sistemas.anm.gov.br/sicopii/p/alterar/atualizarprocesso.asp?Origem=PesquisaSimples',
        data=formdata)

    if not wpage.response.text.find(number+'-'+year):
        print('Nao achou! Não autenticado em sistemas.anm.gov.br?')
        raise Exception()
        return False

    soup = BeautifulSoup(wpage.response.content, features="lxml")
    table = hscrap.tableDataText(soup)
    table = pd.DataFrame(table[1:], columns=['Processo', 'Interessado'])

    return table['Processo'].to_list()

def whereFisico(wpage, processostr, prefer_uorg='48403'):
    """

    """

    NUPs = getNUPs(wpage, number, year)
    if len(NUPs) > 1:
        # unidade preferencial em caso de mais de um processo
        processostr = re.findall('48403.\d{6}.\d{4}',NUPs.to_string())
    else:
        processostr = table.Processo.values[0].split('.')

    uorg = processostr[0]
    processostr = processostr[1]
    processo_number, processo_year = scm.numberyearPname(processostr)

    table = getHistoricoCompleto(wpage, uorg, processo_number, processo_year)

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
