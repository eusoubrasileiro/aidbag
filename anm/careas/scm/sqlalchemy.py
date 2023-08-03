import json
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy_json import mutable_json_type
from sqlalchemy.orm import mapped_column

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, 
    func, JSON    
    )

from ....web.json import (
    datetime_to_json,
    json_to_datetime
)    

class JSONdt(TypeDecorator):
    impl = TEXT
    """ custom JSON column in SQLAlchemy to serialize/deserialize datetime.datetime objects"""
    def __init__(self, *args, **kwargs):
        super(JSONdt, self).__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value, default=datetime_to_json)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value, object_hook=json_to_datetime)
        return value

# uses sqlalchemy-json package for nested dict, list mutated types
JSONDT = mutable_json_type(dbtype=JSONdt, nested=True)

Base = declarative_base()

class Processodb(Base):
    # structure of the database - class variables
    __tablename__ = 'STORAGE'
    id = Column('id', Integer, primary_key=True, autoincrement=True)
    name = mapped_column('NAME', String(12), unique=True)  # Unique constraint on the 'name' column    
    dados = mapped_column('DADOS', JSONDT)  # Use JSON type to store the nested dictionary as a JSON string
    # Alchemy will serialize the dict to JSON and the way back I don't need to care about it        
    basic_html = mapped_column('PAGE_BASIC', Text)  
    polygon_html = mapped_column('PAGE_POLYGON', Text)  
    # New column for last modification timestamp (auto updated)
    modified = mapped_column('MODIFIED', DateTime, default=func.now(), onupdate=func.now())    
    def __init__(self, name):
        # real data to store in the database - instance variables 
        self.name = name
        self.dados = {}        
        self.basic_html = ''
        self.polygon_html = ''        