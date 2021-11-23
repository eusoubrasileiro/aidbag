## Poligonal or "memorial descritivo" manipulation tools package.


Install from this folder with:

```
pip install .
```

remove with `pip uninstall careas-poligonal`

### Network install

Pip subdirectory install.

```
pip3 install git+https://github.com/eusoubrasileiro/aidbag.git#subdirectory=anm/careas-pip
```

Clone with `--depth 1` only last commit on history.
And install on your virtual env.

```
git clone --depth 1 https://github.com/eusoubrasileiro/aidbag.git
cd aidbag/anm/careas-pip 
```
Then use 

```pip install .```

or 

```python3 -m pip install .```

or 

```python3 setup.py install```


### Pip editable mode

Pip install -e . (doesn't work yet)

> -e,--editable <path/url>
> Install a project in editable mode (i.e.  setuptools "develop mode") from a local project path or a VCS url.
> normally just a link to the folder


### Tests

For development run from careas folder

```
python -m pytest -vv
```