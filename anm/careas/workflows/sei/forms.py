from datetime import datetime
from unidecode import unidecode
import pathlib
from . import *
from .config import *
from ..enums import WORK_ACTIVITY
from .....general.string import closest_string

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
    'Memorial Descritivo - Especificacao condicao nao atendida ligadas': '', # ligadas por corredor
    'Memorial Descritivo - Especificacao condicao nao atendida corredor': '', # e um corredor    
    'Area objetivada incide em area especial de restricao parcial - Nao': '',
    'Area objetivada incide em area especial de restricao parcial - Sim': '',    
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
    'Resultado da Analise - A area e livre': '',
    'Resultado da Analise - A area interfere totalmente': '',
    'Resultado da Analise - parcial 1 area remanescente': '',
    'Resultado da Analise - parcial n areas remanescentes': '',            
    'Resultado da Analise - Observacoes': ''
}

"""decimal print"""
pdecimal = lambda x: f"{x:.2f}".replace('.', ',')

def fillFormPrioridade(infos, **kwargs):
    form = form_data.copy()
    Obs=""    
    xset(form, 'data prioridade', infos['prioridade'].strftime("%d/%m/%Y %H:%M:%S")) # better date/view format        
    xset(form, 'Memorial Descritivo Sim') # default   
    xset(form, 'Área especial de restrição parcial - Não')
    xset(form, 'Área especial de restrição total - Não')
    work = infos['work']     
    match work: # awesome powerful match - NO multiple matches allowed but strong pattern matching
        case { 'resultado' : 'ok' }:                        
            if round(infos['work']['areas']['percs'][0], 2) >= 100:
                xset(form, 'Resultado - área livre')
                Obs += "Área livre. Recomenda-se dar seguimento a análise de plano."
            else: 
                xset(form, 'Resultado - parcial 1 área remanescente')
                Obs += (f"Área original requerida foi reduzida "
                    f"à {pdecimal(infos['work']['areas']['percs'][0])}%"
                f" Recomenda-se comunicação e notificação para dar-se seguimento a análise de plano.")
        case { 'resultado' : 'interferência total'}:
            xset(form, 'Resultado - interfere totalmente') 
            Obs += "Recomenda-se o indeferimento por interferência total."
        case { 'resultado' : 'opção'}:
            xset(form, 'Resultado - parcial n áreas remanescentes')
            areas = [f"{pdecimal(area)} ha," for area in infos['work']['areas']['values']]
            areas = ' '.join(areas)
            Obs += ("A área original requerida após interferência foi reduzida"
                f" às seguintes áreas: {areas[:-1]}." # remove last ','
                f" Recomenda-se formular exigência de opção conforme fundamentação acima.")
    match work['type']:        
        case WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_PESQUISA: 
            xset(form, 'Regime Autorização Pesquisa')
        case WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_LICENCIAMENTO:
            xset(form, 'Regime Registro Licença')
            xset(form, 'Licença Municipal Sim')
            xset(form, 'Licença Municipal Satisfatório')
        case WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_PLG:
            xset(form, 'Regime Permissão Lavra')
        case WORK_ACTIVITY.INTERFERENCIA_REQUERIMENTO_REGISTRO_EXTRAÇÃO:
            xset(form, 'Regime Registro Extracao')
            xset(form, 'Anuência de Titular Sim')
    if work['edital']:
        tipo, nup_pai = work['edital']['tipo'], work['edital']['pai']
        if nup_pai == infos['NUP']:  # processo é originário do edital (não é filho!)                
            raise Exception(f"Este processo  {nup_pai} é Pai e foi à edital {tipo} e seu arquivamento é por nota técnica")
        Obs = f"Proveniente de edital de disponibilidade {tipo} sendo sua origem do processo {nup_pai} " + Obs
        # limpar o resultado para evitar confusão sobre opção
        xset(form, 'Resultado - parcial n áreas remanescentes', '')
    layer = list(map(lambda x: unidecode(x.lower()), infos['estudo']['clayers']))
    for text_layer in layer:
        text_layer = unidecode(text_layer)
        if 'bloqueio' in text_layer:
            xset(form, 'Área restrição parcial Sim') 
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Bloqueio')             
            Obs = ("Houve interferência com a área de bloqueio provisório da +X+X+X+X+X+ "
            "A análise deste processo deve ser suspensa até demais desdobramentos sobre o bloqueio. "
            "Recomenda-se comunicar a interferência ao titular bem como sobre o "
            "PARECER/PROGE Nº 500/2008-FMM-LBTL-MP-SDM-JA que é o dispositivo legal "
            "que disciplina o procedimento de bloqueio. "
            "O termo de renúncia anexo ao Parecer é o dispositivo que possibilita, "
            "à critério da ANM, prosseguir com a análise do requerimento.")

        elif 'sustentavel' in text_layer:          
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Uso Sustentavel')
        elif 'quilombola' in text_layer:          
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Quilombola')
        elif 'garimpeira' in text_layer:          
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Garimpeira')
        elif 'urbana'in text_layer:
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Urbana')
        elif 'assentamento' in text_layer:
            xset(form, 'Área restrição parcial Sim')    
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Assentamento')
        elif 'sitios' in text_layer:
            xset(form, 'Área restrição parcial Sim')
            xset(form, 'Área especial de restrição parcial - Não', '') # unmark
            xset(form, 'Área restrição parcial - especifique - Arqueologicos')    
        elif 'integral' in text_layer:
            xset(form, 'Área restrição total Sim')
            xset(form, 'Área especial de restrição total - Não', '') # unmark
            xset(form, 'Área especial de restrição total - especifique - unidade de conservação integral')    
        elif 'extrativista' in text_layer:
            xset(form, 'Área restrição total Sim')
            xset(form, 'Área especial de restrição total - Não', '') # unmark
            xset(form, 'Área restrição total - especifique - Reserva')
        elif 'indigena' in text_layer:
            xset(form, 'Área restrição total Sim')
            xset(form, 'Área especial de restrição total - Não', '') # unmark
            xset(form, 'Área restrição total - especifique - Indígena')                

    xset(form, 'observacoes', Obs)   
    doc_templates = pathlib.Path(config['sei']['doc_templates'])            
    template_path = next(doc_templates.glob(f"*form_analise*.html")) # get the template by name 
    template = templateEnv.get_template(template_path.name) 
    # turn it in a numbered index dictionary - easier to fill in jinja2 template
    form = {index+1: form[key] for index, key in enumerate(form.keys())} # 0 is 1
    return template.render(fm=form, xget=xget)  
    
