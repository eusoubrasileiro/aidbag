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
import xml.etree.ElementTree as etree

from flask_caching import Cache
from flask import Flask, render_template, request, redirect
from .....web.pandas_html import dataframe_to_html 
from ... import workflows as wf 
from ...scm.util import fmtPname

curpath = os.path.dirname(os.path.abspath(__file__))

def readExcelLegacy(path):
    excel_path = pathlib.Path(path).glob('eventos_prioridade_*.xlsx')
    if not excel_path: 
        raise RuntimeError("Legacy Excel prioridade not found, something like eventos_prioridade_*.xlsx")
    table = pd.read_excel(list(excel_path)[0])
    cols = ['Ativo', 'Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 'Obs', 'DOU', 'Dads', 'Sons']
    table = table[cols]
    table.fillna('-', inplace=True) # fill nan to -
    # additional columns created for stilying or UI/UX with css, jquery, jscript
    table['group'] = table.groupby(table.Processo).ngroup() # set index as id of process 
    table['evindex'] = table.groupby(table.Processo).cumcount() # number of each item inside each group
    # evn is givin unordered number of events to be added as attribute
    table['evn'] = [ p for v in table.groupby(table.Processo).size() for p in [v]*v ] # number of events
    print(table, file=sys.stderr)
    print(table['evn'], file=sys.stderr)
    row_attrs = ['Ativo', 'group', 'evindex', 'evn'] # List of columns to write as attributes in row element.
    row_cols = table.columns.to_list() # List of columns to write as children in row element. By default, all columns
    row_cols = [ v for v in row_cols if v not in ['group', 'evindex', 'evn'] ]
    html_table = dataframe_to_html(table, row_attrs, row_cols)
    # insert checkboxes on first row of each process for prioridade
    for e in html_table.iterfind(".//tbody/tr[@evindex='0']/td[1]"):
        if 'Sim' in e.text:
            e.text = etree.SubElement(e, "input", { 'type': 'checkbox', 'checked': 'true'}) 
        else:
            e.text = etree.SubElement(e, "input", { 'type': 'checkbox'}) 
    #[ e.set('text', '') for e in html_table.iterfind(".//tbody/tr[not(@evindex='0')]/td[1]")]
    html_table = etree.tostring(html_table, encoding='unicode', method='xml')   
    return html_table

def chooseProcess():
    wf.currentProcessGet()
    return wf.ProcessPathStorage
    
app = Flask(__name__, template_folder=curpath)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 30*60 # 30 mins in seconds
app.config['CACHE_TYPE'] = 'SimpleCache' 
cache = Cache(app)
cache.set('processos_list', chooseProcess())
cache.set('selected', None)

@app.route('/')
def chooseProcess():    
    return render_template('index.html', 
                processos_list=cache.get('processos_list'))

@app.route('/table')
def table():
    if cache.get('selected'):
        key = cache.get('selected')        
        return render_template('index.html', 
                               pandas_table=readExcelLegacy(wf.ProcessPathStorage[key]))
    return redirect("/", code=302)        
        
@app.route('/select', methods=['GET'])
def select():    
    cache.set('selected', fmtPname(request.args.get('selected')))
    return redirect("/table", code=302)        
    
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--debug', default=True, action='store_true')    
    args = parser.parse_args()    
    app.config['Debug'] = args.debug
    app.run(host='0.0.0.0', debug=args.debug)       