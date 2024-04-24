import sys 
from .. import scm

def editalTipo(obj):
    tipo = obj['tipo'].lower()  
    if 'leilão' in tipo:
        return 'Leilão'
    elif 'oferta' in tipo:                
        return 'Oferta Pública' 
    return '' # to avoid none on nota tecnica

def dispDadSon(name, infer=True, areatol=0.1):
    """
    return 'dad' and 'son' from name
    * infer: bool (defaul True)
        infer from area-fase
    * areatol: float (default 0.1)
        tolerance area in heactare to found process 
        if infer=True
    """
    def dispSearch(name):
        """
        Try to infer based on search on 
            * Same área 
            * Fase name: disponibilidade/leilão/oferta
        Search for son-dad (or vice-versa) relation leilão or oferta pública.
            Get first son with tipo leilão or oferta publica, when multiple                        
            get 1'st 'son' by poligon matching area on the list and edital/oferta tipo
        return standard name or None
        """   
        root = scm.ProcessManager[name]
        found = False
        for ass_name, attrs in scm.ProcessManager[name]['associados'].items():            
            # print('associdado: ', ass_name, attrs, file=sys.stdout)
            Obj = attrs['obj']
            if not 'polygon' in Obj: #ignore 
                if len(Obj['polygon']) > 1: # also in case of multiple poligons
                    print(f"Ignored {ass_name} multiple poligons", file=sys.stderr)
                continue 
            areadiff = abs(root['polygon'][0]['area']-Obj['polygon'][0]['area'])                        
            edital_tipo = editalTipo(Obj)
            if areadiff <= areatol and edital_tipo is not None:
                found = ass_name
                break # found    
        if not found:
            print('associdados: ', scm.ProcessManager[name]['associados'], file=sys.stdout)
            raise Exception(f'`dispSearch` did not found son-dad from {name}')                
        return found
    p = scm.ProcessManager[scm.fmtPname(name)]
    nparents = len(p['parents'])
    nsons = len(p['sons'])
    if nparents > 1 or nsons > 1:        
        if infer:
            print(f"`dispDadSon` Infering from area-fase {name}", file=sys.stderr)
        # Mais de um associado! Àrea Menor no Leilão? Advindo de Disponibilidade?
        if nsons == 1:
            son = p['sons'][0]
            # search for parent 
            dad = dispSearch(son)
        elif nparents == 1:
            # search for son
            dad = p['dad'][0]
            son = dispSearch(dad)
        else: 
            raise Exception(f'Mais de 1 pai e 1 filho at once {name}')                
    if nparents:
        son, dad = name, p['parents'][0]           
    elif nsons:
        son, dad = p['sons'][0], name 
    return dad, son 

