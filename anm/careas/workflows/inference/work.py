import re
from enum import Flag, auto
from ...config import config
from ...util import processPath
from .util import readPdfText, getNUP
from .edital import dispDadSon


class WORK_ACTIVITY(Flag):        
    REQUERIMENTO_PESQUISA = auto()
    REQUERIMENTO_LICENCIAMENTO = auto()
    REQUERIMENTO_PLG = auto()    
    REQUERIMENTO_REGISTRO_EXTRAÇÃO = auto()    
    REQUERIMENTO_EDITAL = auto()
    REQUERIMENTO_EDITAL_DAD = auto() # old process to archive 
    REQUERIMENTO_OPCAO_ALVARA = auto()  # opção de área na fase de requerimento  
    DIREITO_RLAVRA_FORMULARIO_1 = auto()        
    REQUERIMENTO_GENERICO_NOT_EDITAL = REQUERIMENTO_PLG | REQUERIMENTO_LICENCIAMENTO | REQUERIMENTO_PESQUISA  
    REQUERIMENTO_GENERICO = REQUERIMENTO_GENERICO_NOT_EDITAL | REQUERIMENTO_EDITAL
    REQUERIMENTO_MUDANCA_REGIME = auto()


def inferWork(process, folder=None):
    """
    From Processo object and work-folder try to infer the work done.
    Fill in a dictionary with information to fill out docs and forms.     
    returns dict with lots of infos key,value pairs    
    """
    infos = {}   
    dados = process.dados # needed by reg. extração and ?
    infos['dados'] = dados

    infos['minuta']  = {}
    infos['edital'] = {}

    match dados['tipo'].lower(), dados['fase'].lower():
        case ('requerimento', fase) if 'garimpeira' in fase:
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_PLG
            infos['minuta']['title'] = 'Minuta de Permissão de Lavra Garimpeira'
        case ('requerimento', fase) if 'lavra' in fase:
            infos['work'] = WORK_ACTIVITY.DIREITO_RLAVRA_FORMULARIO_1
            infos['minuta']['title'] = 'Minuta de Portaria de Lavra'
        case ('requerimento', fase) if 'licenciamento' in fase:
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_LICENCIAMENTO
            infos['minuta']['title'] = 'Minuta de Licenciamento'
            infos['minuta']['code'] = 5  # must be inserted empty so it's inserted by hand after
        case ('requerimento', fase) if 'extração' in fase:
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_REGISTRO_EXTRAÇÃO
            infos['minuta']['title'] = 'Minuta de Registro de Extração'
        case ('requerimento', fase) if 'pesquisa' in fase:
            infos['work'] = WORK_ACTIVITY.REQUERIMENTO_PESQUISA
            infos['minuta']['title'] = 'Minuta de Alvará de Pesquisa'
        case (tipo, _) if 'leilão' in tipo or 'pública' in tipo:
            son, dad = dispSonDad(process)
            dadnup = getNUP(dad)            
            if 'leilão' in tipo:
                infos['edital'] = {'tipo': 'Leilão', 'pai': dadnup}
            else:
                infos['edital'] = {'tipo': 'Oferta Pública', 'pai': dadnup}

    infos['pdf_sigareas'] = None
    infos['pdf_adicional'] = None 
    infos['nome_assinatura'] = config['sei']['nome_assinatura']

    if folder is not None:
        # search/parse local folder
        # Estudo de Interferência deve chamar 'R@&.pdf' glob.glob("R@&*.pdf")[0] seja o primeiro encontrado        
        pdf_sigareas = [ file for file in folder.glob(config['sigares']['doc_prefix'] + '*.pdf') ]
        # turn empty list to None
        infos['pdf_sigareas'] = pdf_sigareas[0] if pdf_sigareas else None        
        if infos['pdf_sigareas']:
            pdf_sigareas_text = readPdfText(infos['pdf_sigareas'].absolute())            
            if 'Bloqueio' in pdf_sigareas_text and (
                'LT' in pdf_sigareas_text or 'PCH' in pdf_sigareas_text): 
                # BLOQUEIO PROVISÓRIO SÓ SERVE PARA EMPREENDIMENTOS ELÉTRICOS PROG 500
                # isto é Hidroelétrica ('PCH'), Linha de Transmissão 'LT'
                # Se é PROVISÓRIO, Infelizmente, só tem jeito de ver no GIS do SIGAREAS ou no QGIS 
                infos['estudo'] = 'bloqueio'
                # if 'bloqueio' in dados['iestudo']['clayers']                
            if 'OPÇÃO DE ÁREA' in pdf_sigareas_text:
                infos['work'] = WORK_ACTIVITY.REQUERIMENTO_OPCAO_ALVARA
                infos['estudo'] = 'ok' # minuta de alvará
            elif 'MUDANÇA DE REGIME COM REDUÇÃO' in pdf_sigareas_text:
                infos['work'] = WORK_ACTIVITY.REQUERIMENTO_MUDANCA_REGIME
                infos['estudo'] = 'ok'
            elif 'ENGLOBAMENTO' in pdf_sigareas_text:
                infos['estudo'] = 'ok' 
            else:
                area_text='ÁREA EM HECTARES:' # para cada area poligonal
                perc_text='PORCENTAGEM ENTRE ESTA ÁREA E A ÁREA ORIGINAL DO PROCESSO:'  
                count = pdf_sigareas_text.count(perc_text)            
                infos['areas'] = {'count' : count, 'percs' : [], 'values' : []}
                if count == 0:
                    infos['estudo'] = 'interferencia total'
                elif count > 0:  
                    percs = re.findall(f"(?<={perc_text}) +([\d,]+)", pdf_sigareas_text)
                    areas = re.findall(f"(?<={area_text}) +([\d,]+)", pdf_sigareas_text)
                    percs = [ float(x.replace(',', '.')) for x in percs ]  
                    areas = [ float(x.replace(',', '.')) for x in areas ]  
                    infos['areas']['percs'] = percs                 
                    infos['areas']['values'] = areas 
 
        if 'estudo' in infos and 'ok' in infos['estudo']:                
            infos['pdf_adicional'] = folder / "minuta.pdf"

    if __workflow_debugging__:
        print(infos)              
    return infos 
