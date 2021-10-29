from setuptools import setup, find_packages

#PACKAGES = find_packages(where='poligonal')

# only the pretty basic to run careas apps on server
with open("requeriments.txt") as f:
    INSTALL_REQUIRES = f.readlines()

# pip install careas_poligonal[full] to install these additional dependencies
with open("requeriments-extra.txt") as f:
    extra = f.readlines()

setup(
    name='careas_poligons',
    version='0.1.0',
    packages=['poligonal'],
    package_dir = {'': "..\careas"}, # "all" packages are here : expects a poligonal\__init__.py
    install_requires=INSTALL_REQUIRES,
    extras_require={
        'full': extra,
    }
)

