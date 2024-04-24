from enum import Enum, auto, Flag

import jinja2
from ...config import config
    
template_path = config['sei']['doc_templates']
templateLoader = jinja2.FileSystemLoader(searchpath=template_path)
templateEnv = jinja2.Environment(loader=templateLoader)

"""title for SEI external documents"""
docs_externos = [
    'Estudo de Retirada de Interferência',
    'Estudo de Mudança de Regime',
    'Estudo de Opção',
    'Minuta Pré de Alvará',
    'Minuta de Licenciamento',
    'Minuta de Registro de Extração',    
    'Minuta de Portaria de Lavra',
    'Minuta de Permissão de Lavra Garimpeira',
    'Formulário 1 Análise de Requerimento de Lavra'    
]

    
    
    
    


