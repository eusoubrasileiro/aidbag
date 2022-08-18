from enum import Enum

# Workflows 
# Deve ser atualizado o código se o modelo favorito for modificado
# 0 - 4397674  Para analise de plano e notificar redução de área(Generico)
# 1 - 4398259  Para analise de plano sem redução de area
# 2 - 4398010  Para notificar e publicar interferencia total 
# 3 - 4481305  Para notificar e publicar interferência parcial opção
mcodigos = ['4397674', '4398259', '4398010', '4481305']


class SEI_DOCS(Enum):
    REQUERIMENTO_OPCAO_ALVARA = 0  # opção de área na fase de requerimento  
