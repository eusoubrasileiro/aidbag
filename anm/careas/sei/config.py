from enum import Enum, auto, Flag

import jinja2
from ..config import config
    
template_path = config['sei']['doc_templates']
templateLoader = jinja2.FileSystemLoader(searchpath=template_path)
templateEnv = jinja2.Environment(loader=templateLoader)

docs_externos = {
    0: {'tipo': 'Estudo', 'desc': 'de Retirada de Interferência'},
    1: {'tipo': 'Minuta', 'desc': 'Pré de Alvará'},
    2: {'tipo': 'Minuta', 'desc': 'de Licenciamento'},
    3: {'tipo': 'Estudo', 'desc': 'de Opção'},
    4: {'tipo': 'Minuta', 'desc': 'de Portaria de Lavra'},
    5: {'tipo': 'Minuta', 'desc': 'de Permissão de Lavra Garimpeira'},
    6: {'tipo': 'Formulário', 'desc': '1 Análise de Requerimento de Lavra SECOR-MG'},
    7: {'tipo': 'Minuta', 'desc': 'de Registro de Extração'}
}

    
    
    
    

