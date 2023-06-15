from sklearn.metrics import accuracy_score
import tensorflow as tf
from tensorflow.keras.callbacks import TensorBoard
import gc
from tensorflow import keras
import numpy as np
import os, contextlib
from utils.dbconnection import Db_connection_manager
import uuid
import requests
import psycopg2
import math
import dill
from keras import backend as K




devnull= open(os.devnull, 'w')
#os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
print(tf.config.list_physical_devices('GPU'))
class federatedModel():
    def __init__(self, model, batch_size, clients, dbparams, epochs, test_set=None):
        for client in clients:
            if not client.check_auth():
                raise Exception("Failed to authenticate on client {} API key may be missing or outdated".format(client.ip))
        self.id = uuid.uuid4()
        self.batch_size = batch_size
        self.model = model
        self.best=0
        self.bestmodel=None
        self.roundnumber=0
        self.epochs = epochs
        self.clients = clients
        self.db = Db_connection_manager(dbparams)
        self.global_count = self.compute_global_count(clients)
        self.local_count = self.compute_local_count(clients)
        self.callbacks=[]
        self.test_set=test_set
        tensorboard_callback =TensorBoard(log_dir="./"+str(self.id), histogram_freq=1)
        self.callbacks.append(tensorboard_callback)
        self.losshistory=[]
        self.acchistory=[]
        self.recallhistory=[]

    
    def set_lr(self, lr):
        K.set_value(self.model.optimizer.learning_rate, lr)
    
    def set_test_set(self, test_set):
        self.test_set = test_set

    def compute_global_count(self, clients):
        global_data = 0
        for client in clients:
            #print(client.get_metadata().content)
            global_data+=client.get_metadata().json()['acessible_instances']
        return global_data
    
    def compute_local_count(self, clients):
        data={}
        for client in clients:
            #print(client.get_metadata().content)
            data[client.getip()]=client.get_metadata().json()['acessible_instances']
        return data

    def weight_scaling_factor(self, client):
        return (self.local_count[client]/self.global_count)


    def scale_model_weights(self, weight, scalar):
        '''function for scaling a models weights'''
        weight_final = []
        steps = len(weight)
        for i in range(steps):
            weight_final.append(scalar * weight[i])
        return weight_final

    def sum_scaled_weights(self, scaled_weight_list):
        '''Return the sum of the listed scaled weights. The is equivalent to scaled avg of the weights'''
        avg_grad = list()
        #get the average grad accross all client gradients
        for grad_list_tuple in zip(*scaled_weight_list):
            layer_mean = tf.math.reduce_sum(grad_list_tuple, axis=0)
            avg_grad.append(layer_mean)
            
        return avg_grad
    
    def round(self, each, model): #TODO: fix this function
        #post global weights to db underf self.id and self.roundnumber
        with contextlib.redirect_stdout(devnull):
            modelbytes=dill.dumps(model)
        self.db.execute_query("INSERT INTO models.global_weights (id, roundnumber, weights) VALUES (%s, %s, %s) ON CONFLICT(id) DO update SET roundnumber=%s, weights=%s WHERE models.global_weights.id=%s",(str(self.id), self.roundnumber,  (psycopg2.Binary(modelbytes)), self.roundnumber, (psycopg2.Binary(modelbytes)), str(self.id)))
        #If we use model as PK, we need onconflit replace here. Same in clients
        for client in self.clients:
            client.train(self.model, self.batch_size, self.id, each, self.roundnumber).content
        queryresults=[]
        while(len(queryresults)<len(self.clients)):
            queryresults = self.db.execute_query("SELECT * FROM models.local_weights WHERE roundnumber = %s and id=%s", (self.roundnumber, str(self.id))).fetchall()
        #get local weights from db underf self.id+client.ip,  and self.roundnumber
        models = []
        for row in queryresults:
            with contextlib.redirect_stdout(devnull):
                models.append((dill.loads(row[3]), row[1]))
        #scale local weights
        weightsets=[]
        for w in models:
            we = self.scale_model_weights(w[0], self.weight_scaling_factor(w[1]))
            weightsets.append(we)
        
        final_weights = self.sum_scaled_weights(weightsets)
        self.model.set_weights(final_weights)
        self.roundnumber+=1
        gc.collect()
        del models
        del weightsets
        del final_weights
        tf.keras.backend.clear_session()
        gc.collect()
        metrics=self.test_global_model()
        self.losshistory.append(metrics['loss'])
        self.acchistory.append(metrics['accuracy'])
        self.recallhistory.append(metrics['recall'])
        tf.keras.backend.clear_session()
        gc.collect()
        metric=(metrics['accuracy']*metrics['recall'])/(2*metrics['accuracy']+metrics['recall'])
        if metric>self.best:
            self.best=metric
            self.model.save('./bestmodel-'+str(self.id))
        #for row in queryresults:
         #   print(row[1]+": "+row[4])

    def test_global_model(self):
        if self.test_set is None:
            raise Exception("No test set provided")
        return self.model.evaluate(self.test_set, batch_size=1, callbacks=self.callbacks, return_dict=True)
        
    def get_keras_model(self):
        return self.model
    
    def fit(self, each=1):
        self.test_global_model()
        for i in range(self.epochs):
            self.round(each, self.model)


class client():
    def __init__(self, ip, api_key=None):
        self.ip = ip
        self.api_key = api_key

    def getip(self):
        return self.ip
    def get_metadata(self):
        return requests.get("http://"+self.ip+"/metadata", headers={"apikey":self.api_key})
    
    def check_auth(self):
        return requests.get("http://"+self.ip+"/checkauth", headers={"apikey":self.api_key}).status_code==200
    
    def train(self, model, batch_size, modelid, each, roundnumber):
        return requests.get("http://"+self.ip+"/train", headers={"apikey":self.api_key}, params={"model":modelid, "bsize":batch_size, "db":modelid, "epochs":each, "roundnumber":roundnumber})
