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
# 0 - 4397674  Para analise de plano e notificar redução de área(Generico)
# 1 - 4398259  Para analise de plano sem redução de area
# 2 - 4398010  Para notificar e publicar interferencia total 
# 3 - 4481305  Para notificar e publicar interferência parcial opção
mcodigos = ['4397674', '4398259', '4398010', '4481305']

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
