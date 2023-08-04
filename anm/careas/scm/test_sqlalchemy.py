from sqlalchemy import create_engine, Column, Integer, String, JSON, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from aidbag.anm.careas.scm import sqlalchemy as sql

# engine = create_engine('sqlite:////home/andre/ProcessesStored.db')
# sql.Base.metadata.create_all(engine)

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    scoped_session,
    sessionmaker
    )
engine = create_engine(f"sqlite:///mydb.db", echo=True)                    
# session = sessionmaker(bind=engine)()
sql.Base.metadata.create_all(engine)

with Session(engine) as session:
    p = sql.Processodb('test')
    session.add(p)    
    session.commit()
with Session(engine) as session:
    p = session.query(sql.Processodb).filter_by(name='test').first()
    p.polygon_html = p.polygon_html+'something on html text'
    session.commit()
    p = sql.Processodb('test2')
    session.add(p)
    session.commit()
    p.basic_html = 'something on basic html'
    session.commit()
    p.dados['xxx'] = { 'x' : 'y'}
    session.commit()
with Session(engine) as session:
    p = session.query(sql.Processodb).filter_by(name='test2').first()
    assert p.dados['xxx'] == { 'x' : 'y' }
with Session(engine) as session:
    p = session.query(sql.Processodb).filter_by(name='test2').first()
    p.dados['xxx']['x'] = 'z'
    session.commit()
with Session(engine) as session:
    p = session.query(sql.Processodb).filter_by(name='test2').first()
    assert p.dados['xxx']['x'] == 'z'
# delete everything
with Session(engine) as session:
    p = session.query(sql.Processodb).filter_by(name='test').first()
    session.delete(p)
    session.commit()
with Session(engine) as session:
    p = session.query(sql.Processodb).filter_by(name='test2').first()
    session.delete(p)
    session.commit()