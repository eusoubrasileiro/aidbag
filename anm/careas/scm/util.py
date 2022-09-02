import re

# Processes Regex 
# groups 
regex_processg = re.compile('(\d{0,3})\D*(\d{1,3})\D([1-2]\d{3})') # use regex_processg return tupple groups
# without groups
regex_process = re.compile('\d{0,3}\D*\d{1,3}\D[1-2]\d{3}') # use regex_process.search(...) if None didn't find 
# explanation: [1-2]\d{3} years from 1900-2999

def test_regex_process():
    testtext = "847/1945,xx2.537/2016,832537-2016,48403.832.537/2016-09,832.537/2016-09"
    result = re.findall(regex_processg, testtext)
    expected = [('84', '7', '1945'),
    ('2', '537', '2016'),
    ('832', '537', '2016'),
    ('832', '537', '2016'),
    ('832', '537', '2016')]
    assert  result == expected

# test regex when imported 
test_regex_process()

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
    pross_str = ''.join(re.findall('\d', fmtPname(pross_str)))
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

def processUniqueNumber(pross_str):
    """
    Unique number from process name
    That can be easily sorted.
    eg. 2537/1942 -> 1942002537
    """
    number, year = numberyearPname(pross_str)
    return year+'{:06d}'.format(int(number))



# fonte de informação da data de origem do processo 
# 1. numero do processo 
# 2. data de associacao 
# data de associacao não existe para self 
# but data protocolo pode ou não existir
# se prioridade existe pode não ser útil para associação
# não há opção tem que ser por nome mesmo

    # def isOlderAssociado(self, other):
    #     """simple check for associados 
    #     wether self 02/2005 is older than 03/2005"""
    #     # if starts with 3xx
    #     # if self.disp: # if disponibilidade get data associação mais antiga -> origen
    #     #     datas = [ d['data'] for d in self.AssociadosData.values() ]
    #     #     datas.sort(reverse=False)
    #     #     syear = datas[0].year
    #     # else:
    #     #     syear = self.year 
    #     # if other.disp: # if disponibilidade get data associação mais antiga -> origen
    #     #     datas = [ d['data'] for d in other.AssociadosData.values() ]
    #     #     datas.sort(reverse=False)
    #     #     oyear = datas[0].year 
    #     # else:
    #     #     oyear = other.year 
    #     if self.year < other.year:
    #         return True 
    #     if self.year > other.year:
    #         return False 
    #     # same year now       
    #     if self.number < other.number:
    #         return True 
    #     if self.number > other.number:
    #         return False 
    #     raise Exception("Error `IsOlder` process are equal")

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
    if check: 
        process = fmtPname(process)
        other = fmtPname(other)
    pnumber, pyear = map(int, numberyearPname(process))
    onumber, oyear = map(int, numberyearPname(other))
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