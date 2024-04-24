from concurrent.futures import process
from . import *
from .config import *
from ..prework import WORK_ACTIVITY
from datetime import datetime

def xget(fdict, choice):
    keys = list(fdict.keys())
    closest_key = closest_string(choice, keys)
    return fdict[closest_key]

def xset(fdict, choice, value='X'):
    keys = list(fdict.keys())
    closest_key = closest_string(choice, keys)
    fdict[closest_key] = value

"""
dict key-values 1-1 match to html form fields on req_form_analise at docs_models 
"""
form_data = {
    'Regime - Autorizacao de Pesquisa': '',
    'Regime - Registro de Licenca': '',
    'Regime - Permissao de Lavra Garimpeira': '',
    'Registro de Extracao': '',
    'Data de prioridade': '',
    'Licenca Municipal - Nao': '',
    'Licenca Municipal - Sim': '',
    'Licenca Municipal - Satisfatoria': '',
    'Licenca Municipal - Insatisfatoria': '',
    'Licenca Municipal - Especificacao condicao nao atendida': '',
    'Anuencia de Titular de Direito Minerario - Nao': '',
    'Anuencia de Titular de Direito Minerario - Sim': '',  # PLG ou Registro de Extracao
    'Memorial Descritivo - Sim': '',
    'Memorial Descritivo - Nao': '',
    'Memorial Descritivo - Especificacao condicao nao atendida Os lados nao atendem': '',
    'Memorial Descritivo - Especificacao condicao nao atendida ligadas': '', # ligadas por corredor
    'Memorial Descritivo - Especificacao condicao nao atendida corredor': '', # e um corredor
    'Memorial Descritivo - Especificacao condicao nao atendida Outros': '',
    'Area objetivada incide em area especial de restricao parcial - Nao': '',
    'Area objetivada incide em area especial de restricao parcial - Sim': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Faixa de Fronteira': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Bloqueio provisorio': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Unidade de Conservacao de Uso Sustentavel': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Territorio Quilombola': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Reserva Garimpeira': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Area urbana': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Assentamento': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Sitios Arqueologicos': '',
    'Area objetivada incide em area especial de restricao parcial - Especifique - Outras': '',
    'Area objetivada incide em area especial de restricao total - Nao': '',
    'Area objetivada incide em area especial de restricao total - Sim': '',
    'Area objetivada incide em area especial de restricao total - Especifique - Unidade de Conservacao de Protecao Integral': '',
    'Area objetivada incide em area especial de restricao total - Especifique - Reserva Extrativista e Reserva Particular do Patrimonio Natural': '',
    'Area objetivada incide em area especial de restricao total - Especifique - Terra indigena homologada': '',
    'Area objetivada incide em area especial de restricao total - Especifique - Outros': '',
    'Area objetivada incide em area especial de restricao total - Especifique - Especifique': '',
    'Resultado da Analise - A area e livre': '',
    'Resultado da Analise - A area interfere totalmente': '',
    'Resultado da Analise - parcial 1 area remanescente': '',
    'Resultado da Analise - parcial n areas remanescente': '',
    'Resultado da Analise - A descricao da area nao atende': '',
    'Resultado da Analise - Ausencia de licenca municipal ou licenca instruindo varios requerimentos': '',
    'Resultado da Analise - Deve ser indeferido com base no art 167-I Portaria 155 12/05/2016': '',
    'Resultado da Analise - Observacoes': ''
}



def fillFormPrioridade(infos, **kwargs):
    form = form_data.copy()
    Obs=""    
    xset(form, 'data prioridade', infos['dados']['prioridade'])    
    xset(form, 'Memorial Descritivo Sim') # default        
    match infos: # awesome powerful match - multiple matches allowed and strong pattern matching
        case { 'estudo' : 'ok' }:            
            if infos['areas']['count'] == 1:
                if infos['areas']['percs'][0] >= 100:
                    xset(form, 'Resultado área livre')
                else: 
                    xset(form, 'Resultado 1 área')
            else:
                xset(form, 'Resultado n áreas')
        case { 'estudo' : 'interferencia total'}:
            xset(form, 'Resultado interfere totalmente') 
        case { 'work': activity }:
            match activity:
                case WORK_ACTIVITY.REQUERIMENTO_PESQUISA: 
                    xset(form, 'Regime Autorização Pesquisa')
                case WORK_ACTIVITY.REQUERIMENTO_LICENCIAMENTO:
                    xset(form, 'Regime Registro Licença')
                    xset(form, 'Licença Municipal Sim')
                    xset(form, 'Licença Municipal Satisfatório')
                case WORK_ACTIVITY.REQUERIMENTO_PLG:
                    xset(form, 'Regime Permissão Lavra')
                case WORK_ACTIVITY.REQUERIMENTO_REGISTRO_EXTRAÇÃO:
                    xset(form, 'Regime Registro Extracao')
                    xset(form, 'Anuência de Titular Sim')
        case { 'edital' : {'tipo' : tipo, 'pai' : nup_pai} }:
            if nup_pai == infos['dados']['NUP']:  # processo é originário do edital (não é filho!)                
                raise Exception(f"Este processo  {nup_pai} é Pai e foi à edital {tipo} e seu arquivamento é por nota técnica")
            Obs += f"Proveniente de edital de disponibilidade {tipo} sendo sua origem do processo {nup_pai}"

    layer = list(map(lambda x: unicode(x.lower()), infos['dados']['iestudo']['clayers']))
    match layer:
        case layer if 'bloqueio' in layer:
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Bloqueio')
        case layer if 'sustentavel' in layer:            
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Conservação')
        case layer if 'quilombola' in layer:            
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Quilombola')
        case layer if 'garimpeira' in layer:            
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Garimpeira')
        case layer if 'urbana' in layer:
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Urbana')
        case layer if 'assentamento' in layer:
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Assentamento')
        case layer if 'sitios' in layer:
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área restrição parcial Arqueologicos')    
        case layer if 'integral' in layer:
            xset(form, 'Área restrição total Sim')
            xset(form, 'Área restrição total Integral')    
        case layer if 'extrativista' in layer:
            xset(form, 'Área restrição total Sim')
            xset(form, 'Área restrição total Reserva')
        case layer if 'indigena' in layer:
            xset(form, 'Área restrição total Sim')
            xset(form, 'Área restrição total Indígena')                
    xset(form, 'observacoes', Obs)   
    doc_templates = pathlib.Path(config['sei']['doc_templates'])            
    template_path = next(doc_templates.glob(f"*form_analise*.html")) # get the template by name 
    template = templateEnv.get_template(template_path.name) 
    return template.render(fm=form, xget=xget)  
    
