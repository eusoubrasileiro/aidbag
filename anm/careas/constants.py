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
