"""
Flask app to analyse interferencia table 
and save it's 'prioridade' results direct from browser.add()
Run from ~/Projects 
python -m aidbag.anm.careas.estudos.app.main
or to run on background
nohup python -m aidbag.anm.careas.estudos.app.main 
"""
import sys, pathlib
import pandas as pd 
import argparse
import tempfile

from flask_cors import CORS
from flask_caching import Cache
from flask import (
        Flask, 
        request, 
        Response,
        send_from_directory
    )

from ...config import config
from ... import workflows as wf 
from ...scm.processo import (
        ProcessStorageUpdate,
        ProcessStorage
    )
from ...scm.util import fmtPname
from ...estudos.interferencia import (
        Interferencia, 
        prettyTabelaInterferenciaMaster
    )

curpath = pathlib.Path(__file__).absolute().parents[0]
   
app = Flask(__name__, static_folder=curpath/'build')

# to allow the anm domain (js,html injection) request this app on localhost
CORS(app) # This will enable CORS for all routes
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 30*60 # 30 mins in seconds
# Flask-Cache package
app.config['CACHE_THRESHOLD'] = 10000
app.config['CACHE_DIR'] = pathlib.Path(tempfile.gettempdir())/"workapp" #  temporary directory
app.config['CACHE_TYPE'] = 'FileSystemCache' 
cache = Cache(app)

def htmlTableList(table): 
    """create data to be send as JSON to frontend to create <table><tr><th><td> etc. """
    # additional columns created for stilying or UI/UX with css, jquery, jscript
    if table is None: 
        return None 
    table = table.copy()
    table['evindex'] = None 
    table['evn'] = None   
    for _, group in table.groupby(table.Processo):
        table.loc[group.index, 'evn'] = len(group) 
        table.loc[group.index, 'evindex'] = list(range(len(group)))        
    # for backward compatibility rearrange columns
    table = table[['Prior', 'Ativo', 'Processo', 'Evento', 'EvSeq', 'Descrição', 'Data', 
            'DataPrior', 'EvPrior', 'Inativ', 'Obs', 'DOU', 'Dads', 'Sons',
            'evindex', 'evn']] 
    # rename columns 
    if 'DataPrior' in table.columns:
        table.rename(columns={'DataPrior' : 'Protocolo'}, inplace=True)
    row_attrs = ['Ativo', 'evindex', 'evn'] # List of columns add as attributes in each row element.
    row_cols = table.columns.to_list() # List of columns to write as children in row element. By default, all columns
    row_cols = [ v for v in row_cols if v not in ['evindex', 'evn'] ] # dont use these as columns 
    table_pretty = prettyTabelaInterferenciaMaster(table, view=True)  # some prettify
    # States information using pretty table (checkboxes, eventview)
    query = table_pretty.query("Prior != ''")[['Processo', 'Prior']]
    checkboxes = { tp.Processo: True if (tp.Prior=='1') else False  for (i,tp) in query.iterrows()}
    eventview = { tp.Processo: True for (i,tp) in query.iterrows()} # create default view all
    indexes = query.index.values.astype(str)
    groups = list(zip(indexes[:-1],indexes[1:]))
    # process group rows indexes start/end  
    groupindexes = dict(zip(query.Processo, groups+[[indexes[-1],str(table_pretty.shape[0])]]))    
    states = {'checkboxes' : checkboxes, 'eventview' : eventview, 'groupindexes' : groupindexes}
    return table_pretty[row_cols].values.tolist(), row_cols, table[row_attrs].values.tolist(), row_attrs, states 


@app.route('/flask/analyze', methods=['POST'])
def startTableAnalysis():
    name = request.get_json()['name']
    processobj = ProcessStorage[name]
    data = processobj.dict_dados()
    table_pd = None # pandas table
    if 'iestudo' not in data: # status of finished priority check on table
        iestudo = {'iestudo' : {'done' : False } }        
        processobj._dados.update(iestudo)  
        processobj.changed() # db save
        data.update(iestudo)
    if 'iestudo' in data and 'table' in data['iestudo']: 
        table_pd = pd.DataFrame.from_dict(data['iestudo']['table'])
    else:
        try:
            print(f"{data['NUP']} Not using database json! Loading from legacy excel table.", file=sys.stderr)
            estudo = Interferencia.from_excel(wf.ProcessPathStorage[name])        
            table_pd = estudo.tabela_interf_master
            table_pd = prettyTabelaInterferenciaMaster(table_pd, view=False)
            processobj._dados.update({'iestudo' : { 'table' : table_pd.to_dict() }})  
            processobj.changed() # db save
        except RuntimeError:
            table_pd = None
    if table_pd is not None:      
        # those are payload data dont mistake it with the real dados dict saved on database
        # ONLY: 'states' and 'table' pandas dict are saved on database dados dict      
        table, headers, attrs, attrs_names, states = htmlTableList(table_pd)                    
        data['iestudo']['table'] = table                                    
        data['iestudo']['headers'] = headers            
        data['iestudo']['attrs'] = attrs
        data['iestudo']['attrs_names'] = attrs_names
        # states 'checkboxes''eventview'will be saved on DB when onClick or onChange
        if 'states' in data['iestudo']: 
            # ['groupindexes'] is not saved on DB but we need it to plot
            data['iestudo']['states'].update({'groupindexes' : states['groupindexes']})
            if not 'checkboxes' in data['iestudo']['states']:
                data['iestudo']['states'].update({'checkboxes' : states['checkboxes']})
            if not 'eventview' in data['iestudo']['states']:
                data['iestudo']['states'].update({'eventview' : states['eventview']})
        else:
            data['iestudo']['states'] = states
    return data 

def setCurrentProcessFolders():        
    processos = {} 
    for process in wf.currentProcessGet():
        processobj = ProcessStorage[process]
        dados = processobj.dict_dados() # must be able to cache no obj reference
        processos.update({process : dados})  
    cache.set('processos_dict', processos)


@app.route('/flask/list', methods=['GET'])
def getProcessos():                  
    fast_refresh = request.headers.get('fast-refresh', 'false')  # use request header information identify it
    if fast_refresh == 'true': # frequent refresh by setInterval javascript 15 seconds
        print("Making a fast-refresh", file=sys.stderr)
    else:         
        print("Making a slow-refresh re-reading the entire database", file=sys.stderr)
        dbloaded, timespent = ProcessStorageUpdate(False, background=False) # update processes from sqlite database    
        cache.set('dbloaded', dbloaded)
        cache.set('timespent', round(timespent,2))
        setCurrentProcessFolders()  # update processes folder from working folder
    return { 
            'processos' : cache.get('processos_dict'),
            'status'    : { 
                'workfolder' : config['processos_path'],             
                'dbloaded' : cache.get('dbloaded'), 
                'timespent' : cache.get('timespent') 
                }
            }

def updatedb(name, data, what='eventview', save=False):    
    """update cached estudo table and estudo file on database DADOS column"""    
    process = ProcessStorage[name]            
    iestudo = {}
    if 'iestudo' in process._dados:
        iestudo = process._dados['iestudo']    
        if 'states' not in iestudo:
            iestudo['states'] = {}
        if 'checkboxes' in what:            
            iestudo['states'].update({'checkboxes' : data })
        elif 'eventview' in what:
            iestudo['states'].update({'eventview' : data })            
        process._dados.update({'iestudo' : iestudo})  # add or update ['iestudo'] fields key   
        process.changed() # force database update for this process -> turns dict -> JSON 


@app.route('/flask/update_checkbox', methods=['POST'])
def update_checkbox():
    payload = request.get_json() 
    print('pkg checkboxes', payload['name'], payload['data'], file=sys.stderr);
    updatedb(payload['name'], payload['data'], 'checkboxes')    
    return Response(status=204)     

@app.route('/flask/update_eventview', methods=['POST'])
def update_collapse():
    payload = request.get_json()  
    print('pkg eventview', payload['name'], payload['data'], file=sys.stderr);  
    updatedb(payload['name'], payload['data'], 'eventview')     
    return Response(status=204)



#
# routines regarding the `css_js_inject` chrome extension helper injection tool
#

@app.route('/get_prioridade', methods=['GET'])  # like /get_prioridade?process=830.691/2023
def get_prioridade():
    """return list (without dot on name) of interferentes with process if checked-market or not
    for use on css_js_inject tool"""
    key = request.args.get('process')    
    processo = ProcessStorage[fmtPname(key)] # since html comes without dot
    if 'iestudo' in processo._dados and 'table' in processo._dados:        
        dict_ = pd.DataFrame.from_dict(processo._dados['iestudo']['table']).groupby("Processo", sort=False).first().to_dict()['Prior'] # json iestudo table 
        return { key.replace(".", "") : value for key, value in dict_.items() } # remove dot for javascript use

@app.route('/iestudo_finish', methods=['GET'])  
def iestudo_finish():
    """css_js_inject tool reports estudo finished"""
    key = request.args.get('process')    
    processo = ProcessStorage[fmtPname(key)] # since html comes without dot
    processo._dados.update( {'iestudo' : {'done' : True } })
    processo.changed() # force database update
    return Response(status=204)

cache.set('dbloaded', 0)
cache.set('timespent', 99999.99e6)
setCurrentProcessFolders()


# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and pathlib.Path(app.static_folder + '/' + path).exists():
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--debug', default=True, action='store_true')    
    args = parser.parse_args()    
    app.config['Debug'] = args.debug
    app.run(host='0.0.0.0', use_reloader=True, debug=args.debug, threaded=True, port=5000)   
    