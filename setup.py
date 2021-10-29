from setuptools import setup, find_packages

PACKAGES = find_packages()

# only the pretty basic to run careas apps on server
with open("requirements.txt") as f:
    INSTALL_REQUIRES = f.readlines()

# pip install aidbag[full] to install these additional dependencies
with open("requirements-extra.txt") as f:
    extra = f.readlines()

setup(
    name='aidbag',
    version='0.1.0',
    packages=PACKAGES,
    install_requires=INSTALL_REQUIRES,
    extras_require={
        'full': extra,
    }
)

