from ..scm.util import numberyearPname


def downloadMinuta(wpage, processtr, pdfpath="minuta.pdf"):
    """Download Minuta Alvará/Licenciamento etc. se possível e salva
        
        * wpage : wPage html 
            webpage scraping class com login e passwd preenchidos
        
        * processostr : str
            numero processo format xxx.xxx/ano
            
        * pdfpath: str 
            path and name to save the pdf 
        
    """
    number, year = numberyearPname(processtr) # `fmtPname` unique 
    minuta_get = f"""http://sigareas.dnpm.gov.br/Paginas/Usuario/Imprimir.aspx?tipo=1&numero={number}&ano={year}"""
    wpage.get(minuta_get)
    if wpage.response.status_code != 200:
        raise RuntimeError("Nao é possivel fazer download da Minuta")
    with open(pdfpath, 'wb') as f:
        f.write(wpage.response.content)