from setuptools import setup
import os 

#PACKAGES = find_packages(where='poligonal')

# only the pretty basic to run careas apps on server
with open("requeriments.txt") as f:
    INSTALL_REQUIRES = f.readlines()

# pip install careas_poligonal[full] to install these additional dependencies
with open("requeriments-extra.txt") as f:
    extra = f.readlines()

PACKAGE_DIR = os.path.join('..', 'careas', 'poligonal') # to deal with Linux/Windows different convention

setup(
    name='careas-poligonal',
    version='0.1.1',
    # use packages=[''] for simple python files no folder\__init__.py needed 
    packages=['poligonal', 'poligonal.tests'],  # expects a poligonal\__init__.py at package_dir specified
    package_dir = {'poligonal': PACKAGE_DIR}, # ('' == "all") packages are in specified folder  
    install_requires=INSTALL_REQUIRES,
    extras_require={
        'full': extra,
    },
    tests_require=['pytest'],
    package_data={'': ['*.xml']}
)