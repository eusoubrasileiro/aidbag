import json
import copy 
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy_json import mutable_json_type
from sqlalchemy.orm import (
    mapped_column, 
    declarative_base,
    object_session
    )

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, 
    JSON     
    )

from ....web.json import (
    datetime_to_json,
    json_to_datetime,
    datetime
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

# uses sqlalchemy-json package to track changes on nested dict (dict, list) mutated types
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
    modified = mapped_column('MODIFIED', DateTime, 
        default=datetime.utcnow(), onupdate=datetime.utcnow())    
    version = mapped_column('VERSION', Integer, default=1, nullable=False, 
        onupdate=lambda ctx: 
        ctx.current_parameters['VERSION'] + 1 if ctx.current_parameters['VERSION'] is not None else 1)

    def __init__(self, name):
        # real data to store in the database - instance variables 
        self.name = name
        self.dados = {}        
        self.basic_html = ''
        self.polygon_html = ''        

    def __repr__(self):
        dados = copy.deepcopy(self.dados)
        # if 'estudo' in dados and 'table' in dados['estudo']:        
        #     dados['estudo']['table'] = f"...omitted..."
        #     if 'states' in dados['estudo']:
        #         dados['estudo']['states'] = ['...omitted...']
        # if 'polygon' in dados:
        #     for p in dados['polygon']:
        #         if 'memo' in p:
        #             p['memo'] = f"...omitted..."
        # if 'eventos' in dados:
        #     dados['eventos'] = [ dados['eventos'][0], dados['eventos'][1], '...omitted...']            
        # return f"{self.name} - modified {self.modified} \n{ json.dumps(dados, indent=4, default=datetime_to_json) }"
        keys = "non empty keys: "
        for key, value in dados.items():
            if value is not None and value != '' and (not isinstance(value, dict) or value):
                keys += f"{key}, "
        return f"{self.name} - modified {self.modified} \n{ keys }"

    