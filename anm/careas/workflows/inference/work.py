import re
import pathlib
from ..config import __workflow_debugging__
from ...config import config
from ...util import processPath
from .util import getNUP
from .....general.pdf import readPdfText
from .edital import dispDadSon
from ..enums import WORK_ACTIVITY

def activityFromDados(dados):
    """
    Determines the appropriate work activity.
    """
    match dados['tipo'].lower(), dados['fase'].lower():
        # case (tipo, fase) if 'leilão' in tipo or 'pública' in tipo: # will block following cases
        #     return WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_EDITAL
        case (tipo, fase) if 'garimpeira' in fase and 'requerimento' in tipo:
            return WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_PLG
        case (tipo, fase) if 'lavra' in fase and 'requerimento' in tipo:
            return WORK_ACTIVITY.FORMULARIO_1_DIREITO_RLAVRA
        case (tipo, fase) if 'licenciamento' in fase and 'requerimento' in tipo:
            return WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_LICENCIAMENTO
        case (tipo, fase) if 'extração' in fase and 'requerimento' in tipo:
            return WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_REGISTRO_EXTRAÇÃO
        case (tipo, fase) if 'pesquisa' in fase and 'requerimento' in tipo:
            return WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_PESQUISA  

def minutaName(tipo, fase):    
    """
    minuta name for docs publishing based on the given data
    """
    tipo, fase = tipo.lower(), fase.lower()
    if 'lavra' in fase and 'garimpeira' not in tipo and not 'plg' in tipo:
        return "Minuta de Portaria de Lavra"
    elif "pesquisa" in tipo:
        return "Minuta de Alvará de Pesquisa"
    elif "licen" in tipo:
        return "Minuta de Licenciamento"
    elif "extração" in tipo:
        return "Minuta de Registro de Extração"
    elif "garimpeira" in tipo or "plg": # req. mudança para PLG
        return "Minuta de Lavra Garimpeira"


def inferWork(processname, dados, folder='.'):
    """
    From a Processo object and work-folder, infer the work done and fill in a dictionary with information to fill out documents and forms.
    
    Returns a dictionary with various key-value pairs containing the inferred information.

    From Processo object and work-folder try to infer the work done.
    Fill in a dictionary with information to fill out docs and forms.     
    returns dict with lots of infos key,value pairs    
    """
    
    infos = dados # needed by reg. extração and ?
    infos['work'] = { 
        'type' : None, 
        'minuta' : {'title' : None, 'code' : None},
        'edital' :  None,
        'pdf_adicional' : None,
        'nome_assinatura' : config['sei']['nome_assinatura'],
        'bloqueio' : False,
        'areas' : {'count' : None, 'percs' : [], 'values' : []},
        'resultado' : ''
        }
    work = infos['work']
    work['type'] = activityFromDados(infos)

    tipo = infos['tipo'].lower()
    if 'leilão' in tipo or 'pública' in tipo:  
        work['type'] = WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_EDITAL      
        dad, son = dispDadSon(processname)
        dadnup = getNUP(dad)   
        sonnup = getNUP(son)         
        if 'leilão' in tipo:
            work['edital'] = {'tipo': 'Leilão', 'dad': dadnup, 'son' : sonnup}
        else:
            work['edital'] = {'tipo': 'Oferta Pública', 'dad': dadnup, 'son' : sonnup}

    folder = pathlib.Path(folder) if not isinstance(folder, pathlib.Path) and folder is not None else folder

    if isinstance(folder, pathlib.Path):
        # backward compatibility - search/parse local folder
        # Estudo de Interferência deve chamar config['sigareas']['doc_prefix']*.pdf' 
        # glob.glob [0] seja o primeiro encontrado   
        if 'sigareas' not in infos['estudo']:
            infos['estudo']['sigareas'] = {'pdf_path' : None, 'pdf_text' : None}        
            pdf_sigareas = [ file for file in folder.glob(config['sigareas']['doc_prefix'] + '*.pdf') ]
            infos['estudo']['sigareas']['pdf_path'] = pdf_sigareas[0] if pdf_sigareas else None
            infos['estudo']['sigareas']['pdf_text'] = readPdfText(infos['estudo']['sigareas']['pdf_path']) if pdf_sigareas else None                
        sigareas = infos['estudo']['sigareas']
        if sigareas['pdf_text']:            
            pdf_sigareas_text = sigareas['pdf_text']               
            if 'Bloqueio' in pdf_sigareas_text and (
                'LT' in pdf_sigareas_text or 'PCH' in pdf_sigareas_text): 
                # BLOQUEIO PROVISÓRIO SÓ SERVE PARA EMPREENDIMENTOS ELÉTRICOS PROG 500
                # isto é Hidroelétrica ('PCH'), Linha de Transmissão 'LT'
                # Se é PROVISÓRIO, Infelizmente, só tem jeito de ver no GIS do SIGAREAS ou no QGIS 
                work['bloqueio'] = True
                # if 'bloqueio' in infos['estudo]['clayers']                
            if 'OPÇÃO DE ÁREA' in pdf_sigareas_text:
                work['type'] = WORK_ACTIVITY.OPCAO_REQUERIMENTO
                work['resultado'] = 'ok' # minuta de alvará
            elif 'MUDANÇA DE REGIME COM REDUÇÃO' in pdf_sigareas_text:
                infos['work'] = WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_MUDANCA_REGIME
                work['resultado'] = 'ok'
            elif 'ENGLOBAMENTO' in pdf_sigareas_text:
                work['resultado'] = 'ok' 
            else:
                area_text='ÁREA EM HECTARES:' # para cada area poligonal
                perc_text='PORCENTAGEM ENTRE ESTA ÁREA E A ÁREA ORIGINAL DO PROCESSO:'  
                count = pdf_sigareas_text.count(perc_text)  
                work['areas']['count'] = count 
                match count:
                    case 1:
                        work['resultado'] = 'ok'
                    case 0:
                        work['resultado'] = 'interferência total'
                    case n if n > 1:
                        work['resultado'] = 'opção'
                if count > 0:                                  
                    percs = re.findall(f"(?<={perc_text}) +([\\d,]+)", # \\ due f string
                                       pdf_sigareas_text)
                    areas = re.findall(f"(?<={area_text}) +([\\d,]+)",  # \\ due f string
                                       pdf_sigareas_text)
                    percs = [ float(x.replace(',', '.')) for x in percs ]  
                    areas = [ float(x.replace(',', '.')) for x in areas ]  
                    work['areas']['percs'] = percs                 
                    work['areas']['values'] = areas
        if 'ok' in work['resultado']:                
            infos['work']['pdf_adicional'] = folder / "minuta.pdf"   
            infos['work']['minuta']['title'] = minutaName(infos['tipo'], infos['fase'])
    

    if __workflow_debugging__:
        print(infos)              
    return infos 
