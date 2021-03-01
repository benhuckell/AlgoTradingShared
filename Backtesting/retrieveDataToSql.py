import urllib
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
import pyodbc
import matplotlib.pyplot as plt

CONNECTION_STRING = r'DRIVER={SQL Server};SERVER=localhost\SQLEXPRESS01;DATABASE=Financials;Trusted_Connection=yes;'
FILE_PATH = 'D:/TEMP2.csv'
SYMS_TO_INCLUDE = ['permno','cnum','gvkey','cik','tic','fyear','revt','dvt','ebitda','cshpri','epspx','prcc_f']
NUM_ROWS = 2325000

class CRSPData: 
    def __init__(self,connectionString = CONNECTION_STRING, file_path = FILE_PATH):
        self.connectionString = connectionString
        self.file_path = file_path
        self.columns = pd.read_csv(file_path, nrows=1).columns.tolist()
        #print(self.columns)
        
        self.connection = pyodbc.connect(self.connectionString)
        self.engine = create_engine("mssql+pyodbc://", poolclass=StaticPool, creator=lambda: self.connection)
        return
    
    def getColumnNames(self):
        return self.columns

    def loadToSQL(self, table_name, symsToInclude = SYMS_TO_INCLUDE, rows = 1000, skip_rows = 0, operation = 'append', chunk_size = 1):

        @event.listens_for(self.engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
            if executemany:
                cursor.fast_executemany = True

        indicesToInclude = [self.columns.index(x) for x in symsToInclude]

        table = pd.read_csv(self.file_path, usecols=indicesToInclude, skiprows = range(1,skip_rows+1) ,nrows=rows)

        try:
            table.to_sql(table_name,con=self.engine,if_exists=operation, chunksize = chunk_size, index=False)
        except ValueError:
            print("Error: Check operation - must be replace or append")
        except TypeError:
            print("Chunk Size must be an integer")
        
        return

    def SQLToDF(self):
        sql = "SELECT * FROM [Financials].[dbo].[Test2]"
        data = pd.read_sql(sql,self.connection)
        return data



'''
Example Usage
'''
'''
#Initialize class
crspData = CRSPData(CONNECTION_STRING, FILE_PATH)

#Test load data to pandas df
testDf = crspData.SQLToDF()
testDf = testDf.drop_duplicates()
testDf['mktCap'] = testDf['prcc_f']*testDf['cshpri']
testDf['mktCap'] = testDf['mktCap'].round(2)
print(testDf)

plt.plot(testDf['fyear'], testDf['mktCap'])
plt.show()
'''
'''
#Run this to load all data
step = 25000
for i in range(0,NUM_ROWS//step):
    crspData.loadToSQL(table_name = 'Test2',operation = 'append', skip_rows = i*step, rows = step)
    print(i*step)

print("Done")
'''


#crspData.loadToSQL(table_name = 'Fundamental Data', operation = 'append', skip_rows = 2325000, rows = 25000)


