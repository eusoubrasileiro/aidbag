from ..scm.util import numberyearPname


def downloadMinuta(wpage, processtr, pdfpath="minuta.pdf", tipo=1):
    """Download Minuta Alvará/Licenciamento etc. se possível e salva
        
        * wpage : wPage html 
            webpage scraping class com login e passwd preenchidos
        
        * processostr : str
            numero processo format xxx.xxx/ano
            
        * pdfpath: str 
            path and name to save the pdf 
            
        * tipo: int 
           1. minuta pré de alvará  
           2. minuta de portaria de lavra    
           3. minuta de portaria de lavra agua mineral  
           4. minuta de permissão de lavra garimpeira  
           5. minuta pré de licenciamento - precisa numero de licença, data e município
           6. minuta de registro de extração    
        
    """
    number, year = numberyearPname(processtr) # `fmtPname` unique 
    minuta_get = f"""http://sigareas.dnpm.gov.br/Paginas/Usuario/Imprimir.aspx?tipo={tipo}&numero={number}&ano={year}"""
    wpage.get(minuta_get)
    if wpage.response.status_code != 200:
        raise RuntimeError("Nao é possivel fazer download da Minuta")
    with open(pdfpath, 'wb') as f:
        f.write(wpage.response.content)