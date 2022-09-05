"""
Flask app to analyse interferencia table 
and save it's 'prioridade' results direct from browser.add()
Run from ~/Projects 
python -m aidbag.anm.careas.estudos.app.main
"""
from inspect import trace
import os, sys 
import pandas as pd 
import argparse
import pathlib
import traceback
from threading import Thread
import xml.etree.ElementTree as etree

from flask_caching import Cache
from flask import (
        make_response,
        Flask, 
        render_template, 
        request, 
        Response
    )

from ...config import config
from ... import workflows as wf 
from .....web.pandas_html import dataframe_to_html 
from ...scm.util import fmtPname, numberyearPname
from ...estudos.interferencia import (
        Interferencia, 
        prettyTabelaInterferenciaMaster
    )

curpath = os.path.dirname(os.path.abspath(__file__))


def htmlTable(table): 
    """crate a html code for a pretty view of dataframe `table` """
    # additional columns created for stilying or UI/UX with css, jquery, jscript
    table = table.copy()
    table['group'] = table.Processo # which process group it belongs
    table['evindex'] = None 
    table['evn'] = None 
    if 'style' not in table.columns: # legay table or jsons
        table['style'] = '' # missing column for display porpouses     
    for _, group in table.groupby(table.Processo):
        table.loc[group.index, 'evn'] = len(group) 
        table.loc[group.index, 'evindex'] = list(range(len(group)))
    table = prettyTabelaInterferenciaMaster(table, view=True)  # some prettify 
    # for backward compatibility rearrange columns
    table = table[['Prior', 'Ativo', 'Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 
            'DataPrior', 'EvPrior', 'Inativ', 'Obs', 'DOU', 'Dads', 'Sons',
            'group', 'evindex', 'evn', 'style']] 
    row_attrs = ['Ativo', 'group', 'evindex', 'evn', 'style'] # List of columns to write as attributes in row element.
    row_cols = table.columns.to_list() # List of columns to write as children in row element. By default, all columns
    row_cols = [ v for v in row_cols if v not in ['group', 'evindex', 'evn', 'style'] ]        
    html_table = dataframe_to_html(table, row_attrs, row_cols)
    # insert checkboxes on first row of each process 'Prior' column for click-check prioridade
    for main_row in html_table.findall(".//tbody/tr[@evindex='0']"):                    
        if '1' in main_row[0].text:            
            etree.SubElement(main_row[0], "input", { 'type': 'checkbox', 'checked': 'true'}) 
        else:
            etree.SubElement(main_row[0], "input", { 'type': 'checkbox'})  
        main_row[0].text = ''   
    html_table = etree.tostring(html_table, encoding='unicode', method='xml')         
    return html_table   

   
app = Flask(__name__, template_folder=curpath)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 30*60 # 30 mins in seconds
app.config['CACHE_TYPE'] = 'SimpleCache'  # only 1 thread connection
cache = Cache(app)
cache.set('processos_list', wf.currentProcessGet())
cache.set('selected', None)
cache.set('table', None)
cache.set('json_path', None)


@app.route('/')
def chooseProcess():    
    return render_template('index.html', 
                processos_list=cache.get('processos_list'))

@app.route('/select', methods=['GET'])
def select():    
    cache.set('selected', fmtPname(request.args.get('selected')))
    key = cache.get('selected')
    number, year = numberyearPname(key)
    json_path = (pathlib.Path(wf.ProcessPathStorage[key]) / (config['interferencia']['file_prefix'] 
                 + '_' + '_'.join([number, year])+'.json'))          
    cache.set('json_path', json_path)
    try: # json first         
        table = pd.read_json(json_path)
    except Exception as e: # legacy then        
        print("Not using local json! Loading from legacy excel table.", file=sys.stderr)
        estudo = Interferencia.from_excel(wf.ProcessPathStorage[key])
        table = estudo.tabela_interf_master
    cache.set('table', table)
    response = make_response(render_template('index.html', processo=key,
                pandas_table=htmlTable(table)) )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response
    
@app.route('/update', methods=['POST'])
def update():
    data = request.get_json()        
    if 'state' in data: # checkbox state        
        save(data['process'], data['state'], 'state ')
    elif 'style' in data: # toggle style state
        save(data['process'], data['style'], 'style')
    return Response(status=204)

def save(processo, data, what='state'):    
    """update cached estudo table and estudo file on disk"""    
    table = cache.get('table')          
    if table is not None:          
        if 'state' in what:
            table.loc[table.Processo == processo, 'Prior'] = '1' if data else '0'                
        if 'style' in what:                        
            table.loc[table.loc[table.Processo == processo].index[1:], 'style'] = f'display: {data}' 
        cache.set('table', table)
        table = prettyTabelaInterferenciaMaster(table, view=False)
        with open(cache.get('json_path'), 'w') as f:
            table.to_json(f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--debug', default=True, action='store_true')    
    args = parser.parse_args()    
    app.config['Debug'] = args.debug
    app.run(host='0.0.0.0', debug=args.debug)       