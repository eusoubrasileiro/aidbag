### Flask app to analyse interferencia table 

Saves 'prioridade' results direct from browser to sqlite database. Uses `css_js_inject` scripts to save information from sigareas estudo real-time on database. 

Run from `~/Projects` 

```python -m aidbag.anm.careas.estudos.app.main```

or to run on background

```nohup python -m aidbag.anm.careas.estudos.app.main```

### Frontend

To build the react bundle on the `workapp` git repository folder run

`npm run build`

That'll create the `build` folder (here) used by main.py 



