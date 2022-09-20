

def try_read_html(path):
    """
    try read html from path using 'utf-8' or 'latin-1' encodings
    Args:
        path pathlib.Path
    """
    html = None
    try:
        with path.open('r', encoding='utf-8') as f: 
            html = f.read()
    except UnicodeDecodeError:
        with path.open('r', encoding='latin-1') as f: 
            html = f.read()
    return html 