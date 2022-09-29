import os
import sys
import re
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pathlib


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


def saveHtmlPage(path, html):
    html = html if type(html) is bytes else html.encode('utf-8')
    with pathlib.Path(path).with_suffix('.html').open('wb') as f:
        f.write(html)


def saveFullHtmlPage(url, pagepath='page', session=requests.Session(), html=None, verbose=True):
    """Save web page html and supported contents        
        * pagepath : path-to-page   
        It will create a file  `'path-to-page'.html` and a folder `'path-to-page'_files`
        https://stackoverflow.com/a/62207356/1207193
    """
    def savenRename(soup, pagefolder, session, url, tag, inner):
        if not os.path.exists(pagefolder):  # create only once
            os.mkdir(pagefolder)
        for res in soup.findAll(tag):   # images, css, etc..
            if res.has_attr(inner):  # check attrs tag (file object) MUST exists
                try:
                    filename, ext = os.path.splitext(
                        os.path.basename(res[inner]))  # get name and extension
                    filename, ext = (filename+'.'+ext,
                                     '') if len(ext) > 5 else (filename, ext)
                    # clean special chars from name
                    filename = 'hash_'+str(abs(hash(filename))) + ext
                    fileurl = urljoin(url, res.get(inner))
                    filepath = os.path.join(pagefolder, filename)
                    # rename html ref so can move html and folder of files anywhere
                    res[inner] = os.path.join(
                        os.path.basename(pagefolder), filename)
                    if not os.path.isfile(filepath):  # was not downloaded
                        with open(filepath, 'wb') as file:
                            filebin = session.get(fileurl)
                            file.write(filebin.content)
                except Exception as exc:
                    if verbose:
                        print(exc, file=sys.stderr)
    if not html:
        html = session.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    path, _ = os.path.splitext(pagepath)
    pagefolder = path+'_files'  # page contents folder
    tags_attrs = {'img': 'src', 'link': 'href',
                  'script': 'src'}  # tag&attrs tags to grab
    for tag, inner in tags_attrs.items():  # saves resource files and rename refs
        savenRename(soup, pagefolder, session, url, tag, inner)
    saveHtmlPage(pagepath, soup.prettify('utf-8'))
