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

class WORK_ACTIVITY(Flag):        
    REQUERIMENTO_PESQUISA = auto()
    REQUERIMENTO_LICENCIAMENTO = auto()
    REQUERIMENTO_PLG = auto()    
    REQUERIMENTO_REGISTRO_EXTRAÇÃO = auto()    
    REQUERIMENTO_EDITAL = auto()
    REQUERIMENTO_EDITAL_DAD = auto() # old process to archive 
    REQUERIMENTO_OPCAO_ALVARA = auto()  # opção de área na fase de requerimento  
    DIREITO_RLAVRA_FORMULARIO_1 = auto()    
    REQUERIMENTO_CUSTOM = auto() # custom nota técnica requerimento
    NOTA_TECNICA_GENERICA = auto()
    REQUERIMENTO_GENERICO_NOT_EDITAL = REQUERIMENTO_REGISTRO_EXTRAÇÃO | REQUERIMENTO_PLG | REQUERIMENTO_LICENCIAMENTO | REQUERIMENTO_PESQUISA  
    REQUERIMENTO_GENERICO = REQUERIMENTO_GENERICO_NOT_EDITAL | REQUERIMENTO_EDITAL
    
    
    
    
    

