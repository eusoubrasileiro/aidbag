from glob import glob
from pathlib import Path 
import os

config = {}
config['secor_timeout'] = 4*60 # sometimes sigareas server/r. interferncia takes a long long time to answer 

# sei module configurations
config['sei'] = {}
config['sei']['atribuir_default'] = 'set-this-at-run-time'
config['sei']['marcador_default'] = 'set-the-default-marcador-at-run-time'
config['sei']['doc_templates'] = ''

def SetHomeCareasPath(home=str(Path.home())): # default get userhome folder
    """for mounted disk on linux, set windows home user path"""
    config['secor_path'] = os.path.join(home, 'Documents', 'Controle_Areas')  # os independent     
    config['eventos_scm'] = os.path.join(config['secor_path'], 'Secorpy', 'eventos_scm_12032020.xls')    
    config['sei']['doc_templates'] = os.path.join(config['secor_path'], 'Secorpy', 'docs_models')  # os independent 
    config['processos_path'] = os.path.join(config['secor_path'], 'Processos')  # os independent     

SetHomeCareasPath() # set config path defaults