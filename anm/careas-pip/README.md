## Poligonal or "memorial descritivo" manipulation tools package.


Install from this folder with:

```
python setup.py install 
```

remove with `pip uninstall careas-poligons`

### Network install

Clone with `--depth 1` only last commit on history.
And install on your virtual env.

```
git clone --depth 1 https://github.com/eusoubrasileiro/aidbag.git
cd aidbag/anm/careas-pip 
python3 setup.py install
```

Pip subdirectory install won't work. 

```
pip3 install -e git+https://github.com/eusoubrasileiro/aidbag.git#egg=version_subpkg\&#subdirectory=anm/careas-pip
```

Since `setup.py` uses a backward relative reference `'..\'`
