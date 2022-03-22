import re

from .constants import (
    regex_processg, 
    regex_process, 
)

# scm consulta dados (post) nao aceita formato diferente de 'xxx.xxx/xxxx'
def fmtPname(pross_str):
    """format process name to xxx.xxx/yyyy
    - input process might be also like this 735/1935
    prepend zeros in this case to form 000.735/1935"""
    pross_str = ''.join(regex_processg.findall(pross_str)[0]) # use the first ocurrence    
    ncharsmissing = 10-len(pross_str) # size must be 10 chars
    pross_str = '0'*ncharsmissing+pross_str # prepend with zeros
    return pross_str[:3]+'.'+pross_str[3:6]+r'/'+pross_str[6:]

def numberyearPname(pross_str):
    "return process (number, year)"
    # pross_str = fmtPname(pross_str) # to make sure
    pross_str = ''.join(re.findall('\d', pross_str))
    return pross_str[:6], pross_str[6:]

def findfmtPnames(text):
    """
    Find all process names on `text` return list with strings format xxx.xxx/yyyy like `fmtPname`
    """
    ps = regex_process.findall(text)    
    return [ p[0]+'.'+p[1]+'/'+p[2] for p in ps ]

def findPnames(pross_str):    
    """
    Find all process names on `text` return list with strings as found
    """
    return regex_process.findall(pross_str)

def comparePnames(process, other, check=False):
    """simple check wether which process is older than other (e.g.) 
    based on custom sort function for list 
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
    if check: 
        process = fmtPname(process)
        other = fmtPname(other)
    pnumber, pyear = numberyearPname(process)
    onumber, oyear = numberyearPname(other)
    if pyear < oyear:
        return -1 
    if pyear > oyear:
        return 1 
    # same year now 
    if pnumber < onumber:
        return -1 
    if pnumber > onumber:
        return 1
    return 0 