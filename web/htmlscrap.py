#html web-scraping
from requests_ntlm import HttpNtlmAuth
import re
import os, sys
import requests
from urllib3.util.retry import Retry
from urllib.parse import urljoin
from requests import adapters
from bs4 import BeautifulSoup

# to disable warnings when ssl is False
from urllib3.exceptions import InsecureRequestWarning


# A backoff factor to apply between attempts after the second try
# (most errors are resolved immediately by a second try without a
# delay). urllib3 will sleep for::

#     {backoff factor} * (2 ** ({number of total retries} - 1))
# 10 retries and  backoff factor = 0.1
# = 0.1 * 2 **(2-1)
# = 0.1 * 2 = 0.2
# = 0.1 * 2 * 2 = 0.4 
# = 0.1 * 2 * 3 = 0.6
# = 0.1 * 2 * 9 = 1.8 seconds

class wPage: # html  webpage scraping with soup and requests
    def __init__(self, nretries=10, ssl=True): # requests session
        self.session = requests.Session()
        if not ssl: # disable ssl verification certificates
            self.session.verify = False 
            self.session.trust_env = False
            os.environ['CURL_CA_BUNDLE']="" # or whaever other is interfering with requests
            # not allowing it to verify=False
            # Suppress only the single warning from urllib3 needed.
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)        
        retries = Retry(total=nretries,
                        backoff_factor=0.1, # will sleep for [0.1s, 0.2s, 0.4s, ...] between retries
                        status_forcelist=[ 500, 502, 503, 504 ])
        # https://stackoverflow.com/a/35504626/1207193
        self.session.mount('http://', adapters.HTTPAdapter(max_retries=retries))
        self.session.mount('https://', adapters.HTTPAdapter(max_retries=retries))        

    # testing with 
    # wp = wPage()
    # wp.get("https://br.yahoo.com/")
    # wp.save("yahoo", verbose=True)
    def save(self, pagepath='page', verbose=False):
        """
        using last html page accessed save its html and supported contents        
        * pagepath : path-to-page   
        It will create a file  `'path-to-page'.html` and a folder `'path-to-page'_files`
        https://stackoverflow.com/a/62207356/1207193
        """        
        def savenRename(soup, pagefolder, session, url, tag, inner):
            if not os.path.exists(pagefolder): # create only once
                os.mkdir(pagefolder)
            for res in soup.findAll(tag):   # images, css, etc..
                if res.has_attr(inner): # check inner tag (file object) MUST exists     
                    try:                  
                        filename, ext = os.path.splitext(os.path.basename(res[inner])) # get name and extension
                        filename = re.sub('\W+', '', filename) + ext # clean special chars from name
                        fileurl = urljoin(url, res.get(inner))
                        filepath = os.path.join(pagefolder, filename)
                        # rename html ref so can move html and folder of files anywhere
                        res[inner] = os.path.join(os.path.basename(pagefolder), filename)
                        if not os.path.isfile(filepath): # was not downloaded
                            with open(filepath, 'wb') as file:
                                filebin = session.get(fileurl)
                                file.write(filebin.content)
                    except Exception as exc:
                        if verbose:
                            print(exc, '\n', file=sys.stderr)
        session = self.session
        #... whatever other requests config you need here        
        soup = BeautifulSoup(self.response.text, "html.parser")
        path, _ = os.path.splitext(pagepath)
        pagefolder = path+'_files' # page contents folder
        tags_inner = {'img': 'src', 'link': 'href', 'script': 'src'} # tag&inner tags to grab
        for tag, inner in tags_inner.items():
            savenRename(soup, pagefolder, session, self.response.url, tag, inner)
        with open(path+'.html', 'wb') as file:
            file.write(soup.prettify('utf-8'))

    def post(self, arg, save=True, **kwargs):
        """save : save response overwriting the last"""
        resp = self.session.post(arg, **kwargs)
        if save:
            self.response = resp
        return resp

    def get(self, arg, save=True, **kwargs):
        """save : save response overwrites the last"""
        resp = self.session.get(arg, **kwargs)
        if save:
            self.response = resp
        return resp

class wPageNtlm(wPage): # overwrites original class for ntlm authentication
    def __init__(self, user, passwd, nretries=10, ssl=True):
        """
        ntlm auth user and pass
        * nretries : 
            number of retries to try default 10 - 
            0.1 + 0.2
        """
        super().__init__(nretries, ssl)
        self.user = user
        self.passwd = passwd
        self.session.auth = HttpNtlmAuth(user, passwd)         


def formdataPostAspNet(response, formcontrols):
    """
    Creates a formdata dict based on dict of formcontrols to make a post request
    to an AspNet html page. Use the previous html get `response` to extract the AspNet
    states of the page.

    response : from page GET request
    formcontrols : dict from webpage with values assigned
    """
    # get the aspnet form data neeed with bsoup
    soup = BeautifulSoup(response.content, features="lxml")
    aspnetstates = ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION', '__EVENTTARGET',
                    '__EVENTARGUMENT', '__VIEWSTATEENCRYPTED' ];
    formdata = {}
    for aspnetstate in aspnetstates: # search for existing aspnet states and get its values when existent
        result = soup.find('input', {'name': aspnetstate})
        if not (result is None):
            formdata.update({aspnetstate : result['value']})

    # include aditional form controls params
    formdata.update(formcontrols)
    #return formdata
    return formdata


#### HTML PARSING DATA
# BeautifulSoup Power

# Table parsing with bs4
def tableDataText(table):
    """Parse a html segment started with tag <table>
    followed by multiple <tr> (table rows) and
    inner <td> (table data) tags
    returns: a list of rows with inner collumns
    Note: one <th> (table header/data) accepted in the first row"""
    rows = []
    trs = table.find_all('tr')
    headerow = [td.get_text(strip=True) for td in trs[0].find_all('th')] # header row
    if headerow: # if there is a header row include first
        rows.append(headerow)
        trs = trs[1:]
    for tr in trs: # for every table row
        rows.append([td.get_text(strip=True) for td in tr.find_all('td')]) # data row
    return rows


def dictDataText(soup, data_tags, strip=True):
    """
    Parse Html tags from dict `data_tags` like bellow:

    data_tags = {
        'tipo'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoRequerimento'} ],
        'eventos'               : ['table', { 'id' : 'ctl00_conteudo_gridEventos'} ]
    }

    format
       "data name"  :    ["tagname" , { "attribute name" : "attribute value" }]

    Will be used by BeautifulSoup like
         `soup.find(data_tags['tipo'][0], data_tags['tipo'][1])`

    Return:
        dictionary of data_names with parsed data including tables using `tableDataText`
    """
    dados = {}
    for data in data_tags:
        result = soup.find(data_tags[data][0],
                                data_tags[data][1])
        if not (result is None):
            if data_tags[data][0] == 'table': # parse table if table
                result = tableDataText(result)
            else:
                result = result.text
                if strip: # strip text
                    result = result.strip()
            dados.update({data : result})
    return dados
