import unicodedata #character support for autocomplete 
from sqlalchemy import create_engine, text, MetaData #DB channel
from sqlalchemy.dialects.postgresql.dml import OnConflictDoNothing #Db conflict handler 

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


    def __init__(self, user, passwd, host, port, database):
        self.user = user
        self.passwd = passwd
        self.host = host
        self.port = port
        self.database = database

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
