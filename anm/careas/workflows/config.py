from enum import Flag, auto

__workflow_debugging__ = False

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
    REQUERIMENTO_MUDANCA_REGIME = auto()
    

class ESTUDO_TYPE(Flag):
    INTERFERENCIA = auto()
    OPCAO = auto()