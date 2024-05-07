"""
run with 
pytest -v test_sqlalchemy.py (current folder)
or 
pytest -v aidbag/anm/careas/scm/test_sqlalchemy.py (Projects folder)

you can also inspect the pytestdb.db file in the current folder using
db browser for sqlie (https://sqlitebrowser.org/)
"""
import random
import string
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    scoped_session,
    sessionmaker    
    )

from aidbag.anm.careas.scm import sqlalchemy as sql

@pytest.fixture
def engine():
    engine = create_engine(f"sqlite:///pytestdb.db", echo=True) # create pytestdb.db file 
    yield engine
    engine.dispose()

@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    sql.Base.metadata.create_all(session.get_bind()) # create tables 
    yield session
    session.close()

def generate_random_name(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def test_basic_html(session):
    pname = generate_random_name(7)
    p = sql.Processodb(pname)
    session.add(p)
    session.commit()
    p.basic_html = 'something on basic html'
    session.commit()
    p = session.query(sql.Processodb).filter_by(name=pname).first()
    assert p.basic_html == 'something on basic html'

def test_dados(session):
    pname = generate_random_name(7)
    p = sql.Processodb(pname)
    session.add(p)
    session.commit()
    p.dados['xxx'] = {'x': 'y'}
    session.commit()
    p = session.query(sql.Processodb).filter_by(name=pname).first()
    assert p.dados['xxx'] == {'x': 'y'}
    p.dados['xxx']['x'] = 'z'
    session.commit()
    p = session.query(sql.Processodb).filter_by(name=pname).first()
    assert p.dados['xxx']['x'] == 'z'
    # p = session.query(sql.Processodb).filter_by(name=pname).first()
    # session.delete(p)
    # session.commit()