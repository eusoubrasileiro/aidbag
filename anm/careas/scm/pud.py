import re 

class NotProcessNumber(Exception):
    """
    Raised when a string is not a valid process number
    """

class pud():
    """
    Class to handle process unique identification numbers like 847/1945, 
    02.537/1938, 832537-2016, 48403.832.537/2016-09, 832.537/2016-09 or 
    any other variation also including mixing unexpected separators

    Note inequality comparison is not fully support for processes 
    300 like 300.xxx/yyyy due its nature.
    """
    # reversed pattern - the only way that effectly works for anything
    # since year is the more striking characteristic to match first 
    # [1-2]\d{3} years from 1900-2999 - reversed pattern
    # separators are any non digit except \n -> [^\d\n] simple \D isn't enough
    # Negative lookbehind to ensure that no digit comes before year \d{3}[1-2] -> (?<!\d)
    rpattern = '(?<!\d)(\d{3}[1-2])[^\d\n](\d{1,3})[^\d\n]*(\d{0,3})'
    pattern = re.compile(rpattern)
    def __init__(self, str_: str = None, yng: list = None):                 
        if yng:
            y, n, g = yng
        elif str_: # use first found only             
            y, n, g = pud._getAllgroups(str_)[0]
        else:
            raise ValueError("str or yng must be provided")
        g = (3-len(g))*'0'+g # prepend with zeros
        n = (3-len(n))*'0'+n # prepend with zeros
        self._g = g
        self._n = n
        self._y = y
        self.std = f'{g}.{n}/{y}' # standard number-name anm
        self._unumber = int(f"{y}{g}{n}")
        self._number = f"{g}{n}"
        # processo descarte 300.xxx/year
        self._isdisp = True if g == '300' else False 

    @classmethod
    def _getAllgroups(cls, str_: str):
        """Get all process groups numbers in string """
        unreverse = lambda x: [g[::-1] for g in x]
        yngs = [] # reverse match then reverse the groups        
        groups = pud.pattern.findall(str_[::-1])[::-1]
        if groups:
            for group in groups:
                yngs.append(unreverse(group))
        else:
            raise NotProcessNumber(f"{str_} is not a valid process number")
        return yngs

    @classmethod
    def getAll(cls, str_: str):
        """
        Find all process numbers in a string
        """
        yngs = pud._getAllgroups(str_)
        return [ pud(yng=yng) for yng in yngs]         

    def __str__(self):
        return self.std

    def __repr__(self):
        return self.__str__()

    @property 
    def str(self):
        """standard name"""
        return self.__str__()

    @property
    def year(self):
        return self._y

    @property
    def number(self):
        return self._number

    @property
    def numberyear(self) -> tuple:
        """number and year as tuple"""
        return self._number, self._y

    @property
    def unumber(self):
        return self._unumber

    @property
    def isdisp(self):
        """is disponibilidade or starts with '300.xxx/yyyy'"""
        return self._isdisp

    def __eq__(self, other):
        return other.unumber == self.unumber 

    def __lt__(self, other): # less than 
        if not self.isdisp or not other.isdisp:
            return self.unumber < other.unumber 
        match (self.isdisp, other.isdisp):
            case (True, True):
                if self.year != other.year:
                    return self.year < other.year
                # same year
                return self.number < other.number
            case (False, True) | (True, False):
                if self.year != other.year:
                    return self.year < other.year
                # same year
                raise ValueError("can't compare 300 process number with" 
                    "the same year of other not 300")


def test_pnum_getAll():
    testtext = "847/1945,xx2.537/2016,832537-2016,48403.832.537/2016-09,832.537/2016-09"
    result = [p.unumber for p in pud.getAll(testtext)]
    expected = [1945000847, 2016002537, 2016832537, 2016832537, 2016832537]
    assert  result == expected

def test_pnum_numbers():
    a = pud('847/1945')
    b = pud('1325/1944')    
    assert a.number == '000847'
    assert a.year == '1945'
    assert a.unumber == 1945000847
    assert b.unumber == 1944001325

def test_pnum_cmp():    
    assert (pud('847/1945') < pud('1325/1944')) == False
    assert (pud('847/1945') > pud('1325/1944')) == True
    assert (pud('831.915/2023') < pud('831.012/2021')) == False

def test_newline_plus():
    testext = "48054.830817/2024-91\n48054.831400/2024-46\n27203.831741/2002-85\n"
    result = [p.str for p in pud.getAll(testext)]
    expected = ['830.817/2024', '831.400/2024', '831.741/2002']
    assert  result == expected

test_pnum_getAll()
test_pnum_numbers()
test_pnum_cmp()
test_newline_plus()


# fonte de informação da data de origem do processo 
# 1. numero do processo 
# 2. data de associacao 
# data de associacao não existe para self 
# but data protocolo pode ou não existir
# se prioridade existe pode não ser útil para associação
# não há opção tem que ser por nome mesmo
## this is a key function for associados 
## it seams there is no other option 
def cmpPud(process, other, check=False):
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
        sorted(lst, key=cmp_to_key(careas.scm.cmpPud))
    """
    p = pud(process)
    o = pud(other)
    if p < o:
        return -1
    elif p > o:
        return 1
    else:
        return 0 