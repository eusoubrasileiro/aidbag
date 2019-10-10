#html web-scraping

import time
from requests_ntlm import HttpNtlmAuth
import re

import os, sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import pandas as pd
from datetime import datetime

class wPage: # html  webpage scraping with soup and requests
    def __init__(self): # requests session
        self.session = requests.Session()

    def findAllnSave(self, pagefolder, tag2find='img', inner='src', verbose=False):
        if not os.path.exists(pagefolder): # create only once
            os.mkdir(pagefolder)
        for res in self.soup.findAll(tag2find):   # images, css, etc..
            try:
                filename = os.path.basename(res[inner])
                # dealing with weird resource names (RENAME it to save)
                if len(filename) > 30: # too big  weird names
                    extension = os.path.splitext(filename)[1]
                    if len(extension) > 5: # weird string with dots
                        extension = ''
                    filename = 'file_' + tag2find + '_' +str(hash(filename)) + extension # RENAMED file
                #fileurl = url.scheme + '://' + url.netloc + urljoin(url.path, res.get(inner))
                fileurl = urljoin(self.url, res.get(inner))
                # renamed and saved file path
                # res[inner] # may or may not exist basename makes
                # move html and folder of files anywhere
                res[inner] = os.path.join(os.path.basename(pagefolder), filename)
                # like a '<script' tag where the script is inplace
                filepath = os.path.join(pagefolder, filename)
                if not os.path.isfile(filepath): # was not already saved
                    with open(filepath, 'wb') as file:
                        filebin = self.session.get(fileurl)
                        file.write(filebin.content)
            except Exception as exc:
                if verbose:
                    print(exc, '\n', file=sys.stderr)

    def save(self, pagefilename='page'):
        """
        save html page and supported contents
        pagefilename  : specified folder
        """
        self.soup = BeautifulSoup(self.response.text, features="lxml")
        pagefolder = pagefilename+'_files' # page contents
        self.findAllnSave(pagefolder, 'img', inner='src')
        self.findAllnSave(pagefolder, 'link', inner='href')
        self.findAllnSave(pagefolder, 'script', inner='src')
        with open(pagefilename+'.html', 'w') as file:
            file.write(self.soup.prettify())

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
    def __init__(self, user, passwd):
        """ntlm auth user and pass"""
        self.session = requests.Session()
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

# Table parsing with bs4
def rowgetDataText(tr, coltag='td'): # td (data) or th (header)
    cols = []
    for td in tr.find_all(coltag):
        cols.append(td.get_text(strip=True))
    return cols

def tableDataText(table):
    """Parse a html segment started with tag <table>
    followed by multiple <tr> (table rows) and
    inner <td> (table data) tags
    returns: a list of rows with inner collumns
    Note: one <th> (table header/data) accepted in the first row"""
    rows = []
    trs = table.find_all('tr')
    headerow = rowgetDataText(trs[0], 'th')
    if headerow: # if there is a header row include first
        rows.append(headerow)
        trs = trs[1:]
    for tr in trs: # for every table row
        rows.append(rowgetDataText(tr, 'td')) # data row
    return rows
