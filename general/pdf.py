from pypdf import PdfReader

def readPdfText(filename):
    reader = PdfReader(filename)   
    text = [ page.extract_text() for page in reader.pages ]
    return '\n\n'.join(text)