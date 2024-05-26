import re
from .pud import pud


# fonte de informação da data de origem do processo 
# 1. numero do processo 
# 2. data de associacao 
# data de associacao não existe para self 
# but data protocolo pode ou não existir
# se prioridade existe pode não ser útil para associação
# não há opção tem que ser por nome mesmo
## this is a key function for associados 
## it seams there is no other option 
def comparePnames(process, other, check=False):
    """simple check wether which process is older than other (e.g.) 
    custom sort function for list based on
    https://stackoverflow.com/questions/5213033/sort-a-list-of-lists-with-a-custom-compare-function

    if item1 < item2 ? -1   
    if item1 > item2 ? 1 
    else  0        
    e.g. 02/2005 < 03/2005
    don't cover comparison with process starting with 300.xxx/...    
    usage:
        lst = ['02/2005', '03/2005' ...]
        sorted(lst, key=cmp_to_key(careas.scm.comparePnames))
    """
    p = pud(process)
    o = pud(other)
    if p < o:
        return -1
    elif p > o:
        return 1
    else:
        return 0 