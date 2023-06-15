#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Javier Mora Argumánez"
__maintainer__ = "Javier Mora Argumánez"
__email__ = "jmargumanez99@gmail.com"
__status__ = "Development"
__credits__ = ["Javier Mora Argumánez"]

###################### Imports ############################################
from fastapi import Request, FastAPI, HTTPException, Query #ASGI engine
from typing import List, Union
from fastapi.middleware.cors import CORSMiddleware #CORS
import pika #RabbitMQ interface
import json #read and dump json
import unicodedata #character support for autocomplete 
from sqlalchemy import create_engine, text, MetaData #DB channel
from sqlalchemy.dialects.postgresql.dml import OnConflictDoNothing #Db conflict handler 
from pydantic import BaseModel #HTTP error codes
from collections import deque

class Db_connection_manager:
    def __init__(self, connection_params):
        """
        Create the engine to establish the connections with the database.
        @param connection_params: json with the parameters of the connection
        """
        # Extract the conexion parameters
        with open(connection_params) as json_file:
            db_parameters = json.load(json_file)
        
        user = db_parameters['user']
        password = db_parameters['password']
        host = db_parameters['host']
        port = db_parameters['port']
        database = db_parameters['database']

        # Create the engine
        url = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
        self.engine= create_engine(url)

        self.metadata = MetaData()


    def get_engine(self):
        return self.engine
    

    def reflect(self, tables):
        self.metadata.reflect(self.engine, only=tables)


    def execute_query(self, query, params=None):
        """
        Execute a SQL file

        :param engine: engine to establish the connection with the database.
        :param query: query to execute.
        :param params: aditional params to add to the query.
        """
        with self.engine.connect() as conn:
            if params is None:
                return conn.execute(query)
            else:
                return conn.execute(query, params)

    def execute_sql_file(self, file_name):
        """
        Execute a SQL file

        :param engine: engine to establish the connection with the database.
        :param file_name: name of the sql file to execute.
        """
        with open(file_name) as file:
            query = text(file.read())
            
        self.execute_query(query)



class Item(BaseModel):
    id: str
    value: str

class Message(BaseModel):
    message: str

################# Instantiate app and other utilities ########################################

#App metadata for Swagger specification
app = FastAPI(
    docs_url="/documentation",
    title="FedAML client API",
    description="""
    This is the API for the FedAML client. It allows the workers to interact with the master,
    
    
    """,
    version="0.1.0",
    contact={
        "name": "Javier Mora Argumánez",
        "email": "jmargumanez99@gmail.com",
    }
)

def getconfig(json_path):
    with open(json_path) as json_file:
        config = json.load(json_file)
        return config



#allowed origins for incoming requests. In this case, all requests come from the nginx reverse proxy
origins = [
    "http://localhost", "nginx", "http://nginx" #define all other origins here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
dbconnection = Db_connection_manager('/code/app/db_parameters.json') #Db channel
config=getconfig('/code/app/config.json')
engine = dbconnection.get_engine() #Db broker

################ Define auxiliary functions #########################################

def json_to_table(json):
    json.load(json)

    for i in json:
        if "campos" in i.keys() and "tabla" in i. keys():
            fields=i["campos"]
            table = i["tabla"]
        else:
            continue
        #añadimos acá la query
            
        
def read_from_db(key):
    #get remaining monthly rate
    query = "select apirate_dynamic.rate from apirate_dynamic where key = '%s'"%(key)
    result=dbconnection.execute_query(query)
    for row in result:
        return row[0]

def checknolim(headers):
    #returns whether the request comes from the search engine, as autocomplete may only be used by it.
    return headers['r_limit']=='nolim'

def ratelimit(headers):
    #Monthly rate limiting, keeps control of API keys via the postgres db. New keys can be added dynamically to postgres w/o restarting the api.
    #NGINX reverse proxy, however, will need to restart in order to add new keys. Adding a buffer of unassigned keys to nginx is recommended, 
    #adding them to the db on demand.
    if (headers['r_limit']=='nolim'):
        return (True, None) #Search engine key, unlimited requests
    rate=read_from_db(headers["apikey"]) #if limited, read remaining monthly rates
    if(int(rate)>=1):
        return (True, rate-1)#accept request, decrease count by one
    else:
        return (False, 0)#decline request

def enqueue(body):
    #Interact with the RabbitMQ message broker, enqueuing task parameters for the workers.
    connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq', credentials = pika.PlainCredentials('worker', 'RccqtmuQE8Dt3zi')))
    channel = connection.channel()
    channel.queue_declare(queue='task_queue', durable=True)
    message=body
    channel.basic_publish(
    exchange='',
    routing_key='task_queue',
    body=message,
    properties=pika.BasicProperties(
        delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
    ))
    connection.close()


########################## Define API route functions ###############################################
#@app.on_event("startup")
#def startup():
    #On API startup, build autocomplete tree
    #Since a tree is built for each worker, it takes up slightly more memory, but it doesnt instantiate 12 trees, sharing memory instead.
    #This has been tested experimentally by checking process and total memory consumption under different numbers of gunicorn workers.
   

@app.get("/metadata")
def metadata():
    md=getconfig('/data/metadata.json')
    return md

@app.get("/train")
def train(request: Request,model: Union[str, None] = Query(default=None), roundnumber: Union[int, None]= Query(default=None),  epochs: Union[int, None] = Query(default=1), bsize: Union[int, None] = Query(default=1), db: Union[str, None] = Query(default=None),lr: Union[float, None] = Query(default=0.01)):
    if not model == None and not db == None and not roundnumber == None:
        headers=request.headers
        if headers['r_limit']>0:
            body = {
                "model": model,
                "roundnumber": roundnumber,
                "epochs": epochs,
                "bsize": bsize,
                "db": db,
                "lr": lr,
                "r_limit": headers['r_limit']
            }
            enqueue(json.dumps(body))
            return Message(message="Training task enqueued")
        else:
            return Message(message="Rate limit exceeded")
    else:
        return Message(message="Missing parameters")
    
#TODO app.get checkauth
@app.get("/checkauth")
def checkauth(request: Request):
    headers=request.headers
    if headers['r_limit']>0:
        return Message(message="API key valid")
    else:
        return Message(message="API key invalid")

