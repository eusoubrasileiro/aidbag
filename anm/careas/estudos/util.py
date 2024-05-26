from ..scm.pud import pud 
from enum import Enum
from ....general import closest_enum

class MINUTA(Enum): 
    """Enums for Minutas for download"""
    MINUTA_ALVARA = 1
    MINUTA_PORTARIA_LAVRA = 2
    MINUTA_PORTARIA_LAVRA_AGUA_MINERAL = 3
    MINUTA_PERMISSAO_LAVRA_GARIMPEIRA = 4
    MINUTA_LICENCIAMENTO = 5
    MINUTA_REGISTRO_EXTRACAO = 6
    @classmethod
    def fromName(cls, title):        
        """get the closest enum from a string"""
        return closest_enum(title, cls)

def downloadMinuta(wpage, processtr, pdfpath="minuta.pdf", tipo=MINUTA.MINUTA_ALVARA):
    """Download Minuta Alvará/Licenciamento etc. se possível e salva
        
        * wpage : wPage html 
            webpage scraping class com login e passwd preenchidos        
        * processostr : str
            numero processo format xxx.xxx/ano            
        * pdfpath: str 
            path and name to save the pdf             
        * tipo: MINUTA
    """
    number, year = pud(processtr).numberyear 
    minuta_get = f"""http://sigareas.dnpm.gov.br/Paginas/Usuario/Imprimir.aspx?tipo={tipo.value}&numero={number}&ano={year}"""
    wpage.get(minuta_get)
    if wpage.response.status_code != 200:
        raise RuntimeError("Nao é possivel fazer download da Minuta")
    with open(pdfpath, 'wb') as f:
        f.write(wpage.response.content)