from glob import glob
from pathlib import Path 
import os
import datetime 

config = {}
config['secor_timeout'] = 4*60 # sometimes sigareas server/r. interferncia takes a long long time to answer 

#configs are per module

config['scm'] = {} 
# when to replace the process stored on the ProcessManager after this amount of time 
config['scm']['process_expire'] = datetime.timedelta(weeks=1)
config['scm'] = {'html_prefix' : {'basic': 'scm_basicos_', 'poligon': 'scm_poligonal_'} }

# sei module configurations
config['sei'] = {}
config['sei']['atribuir_default'] = 'set-this-at-run-time'
config['sei']['marcador_default'] = 'set-the-default-marcador-at-run-time'
config['sei']['doc_templates'] = ''
# intereferencia module configuration
config['interferencia'] = {}
config['interferencia']['html_prefix'] = {'this' : 'interferencia', 'legacy': 'sigareas_rinterferencia'}
config['interferencia']['file_prefix'] = 'eventos_prioridade'

def SetHome(home=str(Path.home())): # default get userhome folder
    """
    For mounted disk on linux, set windows home user path to find `Controle_Areas` path.  
    Default is '~' that will become '~\Documents\Controle_Areas'
    """
    config['secor_path'] = os.path.join(home, 'Documents', 'Controle_Areas')  # os independent     
    config['eventos_scm'] = os.path.join(config['secor_path'], 'secorpy', 'eventos_scm_12032020.xls')    
    config['sei']['doc_templates'] = os.path.join(config['secor_path'], 'secorpy', 'docs_models')  # os independent 
    config['processos_path'] = os.path.join(config['secor_path'], 'Processos')  # os independent   
    config['wf_processpath_json'] = os.path.join(config['processos_path'], 'wf_processpath_json.jsons')
    config['scm']['process_storage_file'] = os.path.join(config['processos_path'], 'ProcessesStored')
SetHome() # set config path defaults