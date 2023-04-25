"""
Flask app to analyse interferencia table 
and save it's 'prioridade' results direct from browser.add()
Run from ~/Projects 
python -m aidbag.anm.careas.estudos.app.main
or to run on background
nohup python -m aidbag.anm.careas.estudos.app.main 
"""
from inspect import trace
import os, sys 
import pandas as pd 
import argparse
import pathlib
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

from flask_cors import CORS

from ...config import config
from ... import workflows as wf 
from .....web.pandas_html import dataframe_to_html 
from ...scm.processo import (
        ProcessStorageUpdate,
        ProcessStorage
    )
from ...scm.util import fmtPname, numberyearPname
from ...estudos.interferencia import (
        Interferencia, 
        prettyTabelaInterferenciaMaster
    )

curpath = os.path.dirname(os.path.abspath(__file__))
   
app = Flask(__name__, template_folder=curpath)
# to allow the anm domain (js,html injection) request this app on localhost
CORS(app) # This will enable CORS for all routes
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 30*60 # 30 mins in seconds
app.config['CACHE_TYPE'] = 'SimpleCache'  # only 1 connection (1 thread/session/client)
cache = Cache(app)

def setCurrentProcessFolders():        
    processos = [] 
    for process in wf.currentProcessGet():
        processos.append((process, ProcessStorage[process].dict_dados()))    
    cache.set('processos_list', processos)

cache.set('selected', None)
cache.set('table', None)
cache.set('done', False)
setCurrentProcessFolders()


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
    # rename columns 
    table.rename(columns={'DataPrior' : 'Protocolo'}, inplace=True)
    row_attrs = ['Ativo', 'group', 'evindex', 'evn', 'style'] # List of columns add as attributes in each row element.
    row_cols = table.columns.to_list() # List of columns to write as children in row element. By default, all columns
    row_cols = [ v for v in row_cols if v not in ['group', 'evindex', 'evn', 'style'] ] # dont use these as columns 
    html_table = dataframe_to_html(table, row_attrs, row_cols)
    # insert checkboxes on first row of each process 'Prior' column for click-check prioridade
    for main_row in html_table.findall(".//tbody/tr[@evindex='0']"):                    
        if '1' in main_row[0].text:            
            etree.SubElement(main_row[0], "input", { 'type': 'checkbox', 'checked': ''}) 
        else:
            etree.SubElement(main_row[0], "input", { 'type': 'checkbox'})  
        main_row[0].text = ''   
    html_table = etree.tostring(html_table, encoding='unicode', method='xml')         
    return html_table   

@app.route('/', methods=['GET'])
def chooseProcess():        
    dbloaded, time_spent = ProcessStorageUpdate(False, background=False) # update processes from sqlite database
    wf.ProcessPathStorage.clear() # update processes folder from working folder
    setCurrentProcessFolders()
    return render_template('index.html', 
                processos_list=cache.get('processos_list'), 
                work_folder=config['processos_path'],
                dados=None,
                dbloaded=dbloaded, time_spent=round(time_spent,2))

@app.route('/select', methods=['GET'])
def select():    
    cache.set('selected', fmtPname(request.args.get('selected')))
    key = cache.get('selected')    
    processo = ProcessStorage[key]
    if 'iestudo' not in processo: # status of finished priority check on table
        processo._dados.update( {'iestudo' : {'done' : False } })    
        processo.changed() # force database update
    if 'iestudo_table' in processo._dados: 
        table = pd.DataFrame.from_dict(processo._dados['iestudo_table'])
    else:
        try:
            print("Not using database json! Loading from legacy excel table.", file=sys.stderr)
            estudo = Interferencia.from_excel(wf.ProcessPathStorage[key])        
            table = estudo.tabela_interf_master
        except RuntimeError:
            table = None
    cache.set('table', table)    
    html_table = htmlTable(table) if table is not None else '<h3>No interf. table!</h3>'
    response = make_response(render_template('index.html', processo=key, dados=ProcessStorage[key]._dados,
                pandas_table=html_table) )
    # disable cache so checkbox and display hidden dont get cached
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

@app.route('/process', methods=['GET']) # like /process?process=830.691/2023
def details():
    key = request.args.get('process')
    print(f'process is {key}', file=sys.stderr)
    return ProcessStorage[key]._pages['basic']['html']   

@app.route('/update_checkbox', methods=['POST'])
def update_checkbox():
    datapkg = request.get_json()  
    for process, state in datapkg:          
        update(process, state, 'state')
    update('', '', '', save=True) # only save now on disk
    return Response(status=204)

@app.route('/update_events_view', methods=['POST'])
def update_collapse():
    data = request.get_json()        
    update(data['process'], data['style'], 'style', save=True)
    return Response(status=204)

def update(processo, data, what='state', save=False):    
    """update cached estudo table and estudo file on database DADOS column 
    if `save=True`"""    
    table = cache.get('table')       
    if table is not None:          
        if 'state' in what:
            table.loc[table.Processo == processo, 'Prior'] = '1' if data else '0'                
        if 'style' in what:                        
            table.loc[table.loc[table.Processo == processo].index[1:], 'style'] = f'display: {data}' 
        cache.set('table', table)        
        if save:        
            processo = ProcessStorage[cache.get('selected')]
            table = prettyTabelaInterferenciaMaster(table, view=False)                 
            processo._dados.update( {'iestudo_table' : table.to_dict() }) # add or update 'iestudo_table' key   
            processo.changed() # force database update for this process    

@app.route('/get_prioridade', methods=['GET'])  # like /get_prioridade?process=830.691/2023
def get_prioridade():
    """return list (without dot on name) of interferentes with process if checked-market or not
    for use on css_js_inject tool"""
    key = request.args.get('process')    
    processo = ProcessStorage[fmtPname(key)] # since html comes without dot
    if 'iestudo_table' in processo._dados:        
        dict_ = pd.DataFrame.from_dict(processo._dados['iestudo_table']).groupby("Processo", sort=False).first().to_dict()['Prior'] # json iestudo table 
        return { key.replace(".", "") : value for key, value in dict_.items() } # remove dot for javascript use


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--debug', default=True, action='store_true')    
    args = parser.parse_args()    
    app.config['Debug'] = args.debug
    app.run(host='0.0.0.0', debug=args.debug)
    