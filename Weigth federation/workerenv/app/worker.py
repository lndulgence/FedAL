#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Javier Mora Argumánez"
__maintainer__ = "Javier Mora Argumánez"
__email__ = "jmargumanez99@gmail.com"
__status__ = "Development"
__credits__ = ["Javier Mora Argumánez"]

#################### Imports ##############################
import pika #RabbitMQ message broker interface
import math
import os
from sqlalchemy import create_engine, text, MetaData, update # Database dependencies
import json #Decode request headers
from types import SimpleNamespace #json dependency
from sqlalchemy.dialects.postgresql.dml import OnConflictDoNothing #db conflict handler
import dill #serialize python objects
from tensorflow import keras #keras model
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Activation, Flatten, Conv2D, MaxPooling2D, BatchNormalization
from tensorflow.keras.callbacks import TerminateOnNaN, TensorBoard
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle
import psycopg2 #db connection
import uuid #generate unique ids 
import numpy as np #matrix operations
import tensorflow as tf #machine learning
import requests
import cv2 #image processing
import threading #Concurrency
import socket
import time

################# Constants ################################
RABBIT_URL = 'rabbitmq' #hostname within docker network
ROUTING_KEY = 'task_queue' #arbitrary
QUEUE_NAME = 'task_queue' #arbitrary, must be the same as the one specified within the API code
THREADS = 5 #number of workers
IP='192.168.0.219'

############### Define classes #########################

class GenericObject:
    """
    Generic object data.
    """
    def __init__(self):
        self.id = uuid.uuid4()
        self.bb = (-1, -1, -1, -1)
        self.category= -1
        self.score = -1

class GenericImage:
    """
    Generic image data.
    """
    def __init__(self, filename):
        self.filename = filename
        self.tile = np.array([-1, -1, -1, -1])  # (pt_x, pt_y, pt_x+width, pt_y+height)
        self.objects = list([])

    def add_object(self, obj: GenericObject):
        self.objects.append(obj)

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

class Consumer():
    def __init__(self):
        self.IPAddr=IP
        maindir= '/data/'
        os.chdir(maindir)
        l=[]
        for i in os.listdir():
            try:
                os.chdir(i)
                name=os.getcwd().split("/")
                num=int(name[len(name)-1])
                print(num)
                for j in os.listdir():
                    img=cv2.imread(j)
                    img=cv2.resize(img,(224,224))
                    l.append([img, num])
                os.chdir(maindir)
            except:
                continue
        l=shuffle(l)
        self.train=l
        self.val=[]
        print ("WORKER INTIALIZED")
        dbconnection = Db_connection_manager('/code/app/db_parameters.json') #Db channel
        engine = dbconnection.get_engine() #Db broker
        #start each instance as a thread with a rabbitmq connection
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials = pika.PlainCredentials('worker', 'RccqtmuQE8Dt3zi')))
        self.channel = connection.channel()
        self.channel.basic_qos(prefetch_count=THREADS*10)
        self.channel.basic_consume(QUEUE_NAME, on_message_callback=self.on_message, auto_ack=True) #define message consumption as a call to on_message()
    def run(self):
        self.channel.start_consuming()
    def on_message(self, channel, method_frame, header_frame, body):
        body=json.loads(body, object_hook=lambda d: SimpleNamespace(**d)) #deserialize the json string to a python object
        body=body.__dict__ #convert the object to a dictionary

        model=body['model']
        roundnumber=body['roundnumber']
        epochs=body['epochs']
        bsize=body['bsize']
        db=body['db']
        lr=body['lr']
        r_limit=body['r_limit']
    
        round(model, roundnumber,  epochs, bsize, db, lr, self.IPAddr, self.train, self.val, r_limit)

################### Instantiate objects ####################################
dbconnection = Db_connection_manager('db_parameters.json') #db channel
engine = dbconnection.get_engine() #db engine


################## callback function that trains the actual model #######################################
def round(model, roundnumber,  epochs, bsize, db, lr, IPAddr, train, val, r_limit):
    query= "SELECT weights from models.global_weights WHERE id = %s AND roundnumber= %s"
    print("Message received. Trainiung model with id: "+str(model)+" and round: "+str(roundnumber))
    result=dbconnection.execute_query(query, (model, roundnumber))
    id=model
    for row in result:
        getweights=bytes(row[0])
        model=dill.loads(getweights)

    # Callbacks

    terminate = TerminateOnNaN()
    tensorboard_callback =TensorBoard(log_dir=model, histogram_freq=1)
    callbacks= [tensorboard_callback, terminate]
    x_train=[]
    y_train=[]
    x_val=[]
    y_val=[]

    #TODO setup dataset metadata and load data into datasets

    if r_limit==1:
        for i in train:
            x_train.append(i[0])
            y_train.append([float(i[1])])
        for i in val:
            x_val.append(i[0])
            y_val.append([float(i[1])])
        x_train= np.array(x_train)
        y_train= np.array(y_train)  
        print(y_train.shape)
        x_val= np.array(x_val)
        y_val= np.array(y_val)
        train = tf.data.Dataset.from_tensor_slices((x_train, y_train)).batch(1)
        val = tf.data.Dataset.from_tensor_slices((x_val, y_val)).batch(1)
        model.fit(train,  epochs=epochs,callbacks=callbacks, verbose=1)
    else:
        train=train[:int(len(train)*float(r_limit))]
        for i in train:
            x_train.append(i[0])
            y_train.append([float(i[1])])
        for i in val:
            x_val.append(i[0])
            y_val.append([float(i[1])])
        x_train= np.array(x_train)
        y_train= np.array(y_train)  
        print(x_train.shape)
        print(y_train.shape)
        x_val= np.array(x_val)
        y_val= np.array(y_val)
        train = tf.data.Dataset.from_tensor_slices((x_train, y_train)).batch(1)
        val = tf.data.Dataset.from_tensor_slices((x_val, y_val)).batch(1)
        model.fit(train, validation_data=val, epochs=epochs, batch_size=bsize,  callbacks=[], verbose=1)
    weights=dill.dumps(model.get_weights())
    query = "INSERT into models.local_weights VALUES (%s, %s, %s, %s, %s)"
    dbconnection.execute_query(query, (str(id), str(IPAddr),roundnumber, psycopg2.Binary(weights), ''))


################## main ######################################

        
if __name__=="__main__":
    print(" [*] Waiting for messages. To exit press Ctrl+C")
    w=Consumer()
    w.run()