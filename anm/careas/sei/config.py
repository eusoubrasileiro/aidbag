from enum import Enum

# Workflows 
# Deve ser atualizado o código se o modelo favorito for modificado
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
