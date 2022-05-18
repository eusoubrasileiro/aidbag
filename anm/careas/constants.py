from enum import Enum
from glob import glob
from pathlib import Path 
import os

from aidbag.anm import careas 

# for interferencia
careas_path = str(Path.home()) # get userhome folder
# eventos que inativam or ativam processo

config = {}
config['secor_path'] = os.path.join(careas_path, 'Documents', 'Controle_Areas')  # os independent 
config['eventos_scm'] = os.path.join(config['secor_path'], 'Secorpy', 'eventos_scm_12032020.xls')
config['secor_timeout'] = 4*60 # sometimes sigareas server/r. interferncia takes a long long time to answer 

def SetHomeCareasPath(Home):
    """for mounted disk on linux, set windows home user path"""
    config['secor_path'] = os.path.join(Home, 'Documents', 'Controle_Areas')
    config['eventos_scm'] = os.path.join(config['secor_path'], 'Secorpy','eventos_scm_12032020.xls')


# Workflows 
# Deve ser atualizado o código se o modelo favarito for modificado
# 0 -  1537881	Retificação Resumida Alvará e Aprovo do RFP
# 1 - 1947449	Parecer Técnico - Correção áreas e deslocamentos
# 2 - 1618347	Formulário 1 - Lavra - Pré-Prenchido
# 3 - 2725631	Chefe SECOR Requerimento: Recomendo Analise de Plano
# 4 - 1133380	Chefe SECOR Requerimento: Recomenda publicar exigência opção
# 5 - 2725639	Chefe SECOR Requerimento: Recomenda publicar indeferimento por Interferência Total
# 6 - 1206693	Chefe SECOR Requerimento: Recomendo Analise de Cessão Parcial
# 7 - 1243175	Chefe SECOR Requerimento: Recomendo Analise de Plano (híbrido)
# 8 - 1453503	Chefe SECOR Requerimento de Lavra: Recomendo aguardar cumprimento de exigências
# 9 - 1995116	Chefe SECOR Requerimento de Lavra: com Retificação de Alvará
# 10 - 1995741	Chefe SECOR Requerimento de Lavra: Recomendo encaminhar para preenchimento de check-list
# 11 - 2052065	Chefe SECOR Requerimento de Lavra: Encaminhar avaliar necessidade de reavaliar reservas - redução de área
# 12 - 3044089  Chefe SECOR Requerimento: Recomendo Só Análise de Plano 100%
# 13 - 3369278  Chefe SECOR Requerimento: Opção Executada Recomendo Analise de Plano	
# 14 - 3680185  Informe: Requerimento de Lavra Formulario 1 realizado
# 15 - 3645367  Para DFMNM: Requerimento de Lavra para análise de cumprimento de exigências
# 16 - 3656770  Para SECOR-MG Expedição: Requerimento de Lavra para análise
mcodigos = ['1537881', '1947449', '1618347', '2725631', '1133380', '2725639', 
'1206693', '1243175', '1453503', '1995116', '1995741', '2052065', '3044089', 
'3369278', '3680185', '3645367', '3656770']

docs_externos = {
    0: {'tipo': 'Estudo', 'desc': 'de Retirada de Interferência'},
    1: {'tipo': 'Minuta', 'desc': 'Pré de Alvará'},
    2: {'tipo': 'Minuta', 'desc': 'de Licenciamento'},
    3: {'tipo': 'Estudo', 'desc': 'de Opção'},
    4: {'tipo': 'Minuta', 'desc': 'de Portaria de Lavra'},
    5: {'tipo': 'Minuta', 'desc': 'de Permissão de Lavra Garimpeira'},
    6: {'tipo': 'Formulário', 'desc': '1 Análise de Requerimento de Lavra SECOR-MG'}
}

class SEI_DOCS(Enum):
    REQUERIMENTO_OPCAO_ALVARA = 0  # opção de área na fase de requerimento  
    

def processPathSecor(processo, create=True):
    """pasta padrao salvar todos processos 
    * processo : `Processo` class
    * create: create the path/folder if true (default)
    """
    secorpath = os.path.join(config['secor_path'], 'Processos')
    processo_path = os.path.join(secorpath,
                processo.number+'-'+processo.year)    
    
    if create and not os.path.exists(processo_path): # cria a pasta se nao existir
        os.mkdir(processo_path)                
    return processo_path
