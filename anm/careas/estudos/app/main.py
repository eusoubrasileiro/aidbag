"""
Flask app to analyse interferencia table 
and save it's 'prioridade' results direct from browser.add()
Run from ~/Projects 
python -m aidbag.anm.careas.estudos.app.main
"""
import os, sys
import pathlib  
import argparse
import pandas as pd
from threading import Thread
import xml.etree.ElementTree as etree

from flask_caching import Cache
from flask import (
    Flask, render_template, request, redirect, Response
    )
from .....web.pandas_html import dataframe_to_html 
from ... import workflows as wf 
from ...scm.util import fmtPname

curpath = os.path.dirname(os.path.abspath(__file__))


def readExcelLegacy(path):
    excel_path = pathlib.Path(path).glob('eventos_prioridade_*.xlsx')
    if not excel_path: 
        raise RuntimeError("Legacy Excel prioridade not found, something like eventos_prioridade_*.xlsx")
    table = pd.read_excel(list(excel_path)[0])    
    table.fillna('', inplace=True) # fill nan to -
    # additional columns created for stilying or UI/UX with css, jquery, jscript
    table['group'] = table.Processo # which process group it belongs
    table['evindex'] = None 
    table['evn'] = None 
    for name, group in table.groupby(table.Processo):
        table.loc[group.index, 'evn'] = len(group) 
        table.loc[group.index, 'evindex'] = list(range(len(group)))
        # unecessary information - making visual analysis too poluted
        table.loc[group.index[1:], 'Ativo'] = '' 
        table.loc[group.index[1:], 'Prior'] = ''  # 1'st will be replaced by a checkbox
        table.loc[group.index[1:], 'Processo'] = ''
        table.loc[group.index[1:], 'Dads'] = ''
        table.loc[group.index[1:], 'Sons'] = ''
    cols = ['Prior', 'Ativo', 'Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 
            'DataPrior', 'EvPrior', 'Inativ', 'Obs', 'DOU', 'Dads', 'Sons',
            'group', 'evindex', 'evn']
    table = table[cols]
    row_attrs = ['Ativo', 'group', 'evindex', 'evn'] # List of columns to write as attributes in row element.
    row_cols = table.columns.to_list() # List of columns to write as children in row element. By default, all columns
    row_cols = [ v for v in row_cols if v not in ['group', 'evindex', 'evn'] ]        
    html_table = dataframe_to_html(table, row_attrs, row_cols)
    # insert checkboxes on first row of each process for prioridade
    # add span around everything except this checkbox for clicking porpouses
    for main_row in html_table.findall(".//tbody/tr[@evindex='0']"):    
        children = list(main_row)                     
        if '1' in children[0].text:            
            etree.SubElement(children[0], "input", { 'type': 'checkbox', 'checked': 'true'}) 
        else:
            etree.SubElement(children[0], "input", { 'type': 'checkbox'})  
        children[0].text = ''
    html_table = etree.tostring(html_table, encoding='unicode', method='xml')       
    return html_table

def getProcessesAvailable():
    wf.currentProcessGet()
    return wf.ProcessPathStorage
    
app = Flask(__name__, template_folder=curpath)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 30*60 # 30 mins in seconds
app.config['CACHE_TYPE'] = 'SimpleCache' 
cache = Cache(app)
cache.set('processos_list', getProcessesAvailable())
cache.set('selected', None)

@app.route('/')
def chooseProcess():    
    return render_template('index.html', 
                processos_list=cache.get('processos_list'))

@app.route('/select', methods=['GET'])
def select():    
    cache.set('selected', fmtPname(request.args.get('selected')))
    key = cache.get('selected')        
    return render_template('index.html', processo=key,
                    pandas_table=readExcelLegacy(wf.ProcessPathStorage[key]))    
    
@app.route('/save', methods=['POST'])
def save():
    data = request.get_json()    
    Thread(target=updateFile, args=(data['process'], data['state'])).start()
    return Response(status=204)

def updateFile(processo, state):
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--debug', default=True, action='store_true')    
    args = parser.parse_args()    
    app.config['Debug'] = args.debug
    app.run(host='0.0.0.0', debug=args.debug)       