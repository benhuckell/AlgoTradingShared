import numpy as np 
import pandas as pd 
from pandas_datareader import data as pdr
import matplotlib.pyplot as plt 
from datetime import date
from datetime import datetime as dt
import math


'''
Class representing a single order, and all information required to execute
'''
class Order:
    def __init__(self, date, ticker, action, shares, value):
        self.date = date
        self.ticker = ticker
        self.shares = shares
        self.action = action
        self.value = value


'''
A dictionary class of order objects. Retriveable by timestamp. Currently only handles one order per day.
'''
class Orders:
    def __init__(self):
        self.orderDict = {}
        self.orderSize = 0

    def __len__(self):
        return self.orderSize

    def add(self,order):
        if(order.date in self.orderDict.keys()):
            self.orderDict[order.date].append(order)
        else:
            self.orderDict[order.date] = [order]

        self.orderSize += 1

    def getOrders(self,date):
        try:
            return self.orderDict[date]
        except:
            return None

    def printOrderBook(self):
        print(self.orderDict)


'''
Class to represent an entire portfolio of cash and holdings
'''
class Portfolio:
    def __init__(self, startingCash):
        self.cash = startingCash
        self.holdings = {} #dict with company : shares owned

    #Execute an order to buy/sell a certain number of shares
    def executeActionShares(self,order,cost):
        if(order.action == "buy"):
            self.cash -= cost*order.shares

            if(order.ticker not in self.holdings.keys()):
                self.holdings[order.ticker] = order.shares
            else:
                self.holdings[order.ticker] += order.shares
                
        elif(order.action == "sell"):
            self.cash += cost*order.shares

            if(order.ticker not in self.holdings.keys()):        
                self.holdings[order.ticker] = -1*order.shares
            else:
                self.holdings[order.ticker] -= order.shares
   
        return

    #Execute an order to buy/sell a certain number of $ of a stock
    #Will need to eventually deal with the fractional case here
    def executeActionDollars(self,order,cost):
        if(order.action == "buy"):
            self.cash -= order.value

            if(order.ticker not in self.holdings.keys()):
                self.holdings[order.ticker] = order.value/cost
            else:
                self.holdings[order.ticker] += order.value/cost


        elif(order.action == "sell"):
            self.cash += order.value  

            if(order.ticker not in self.holdings.keys()):
                self.holdings[order.ticker] = -1*order.value/cost
            else:
                self.holdings[order.ticker] -= order.value/cost

        return

'''
Class used for the purposes of loading and saving tick data for the tickers specified
'''
class TickData:
    @staticmethod
    def getPivotTable(startDate, endDate):
        # Tickers list
        # We can add and delete any ticker from the list to get desired ticker live data
        tickers = ['ATWT','BRLL','HRAL','STEV','CGUD','GCLT','PTAH','TXTM','PVDG']
        today = date.today()

        createNewPivot = False

        try:
            if createNewPivot:
                raise Exception
            priceTable = pd.read_pickle("savedTickData.pkl")
            tickers = [ticker for ticker in tickers if ticker not in priceTable.columns]
        except:
            priceTable = pd.DataFrame()

        print("Loading tickers...")

        for ticker in tickers:
            print(tickers.index(ticker)+1,"/",len(tickers))
            priceTable[ticker] = pdr.get_data_yahoo(ticker, start=startDate, end=endDate)['Adj Close']

        #Splice df based on provided dates
        priceTable = priceTable.loc[priceTable.index.date >= startDate]

        #Pickle the df
        priceTable.to_pickle("savedTickData.pkl")

        #print(priceTable)
        return priceTable

'''
Main Backtesting class

Uses all other classes defined in this file

Will simulate a full backtest from startDate to endDate, by taking in a list of orders to execute
Upon completing, will print out relevant statistics, as well as an optional plot of portfolio performance
'''
class Backtest:
    def __init__(self, startDate, endDate, startingCash = 100):
        #Dates
        self.startDate = startDate
        self.endDate = endDate

        #Sim vars
        self.valueDf = pd.DataFrame(columns =["totalVal"])
        self.portfolio = Portfolio(startingCash)
        self.pivotTable = TickData.getPivotTable(self.startDate, self.endDate)

        #Result parameters
        self.finalValue = None
        self.totalReturn = None
        self.annualizedReturn = None

    def plotIndividualStock(self, ticker):
        buyDate = self.startDate

        orders = Orders()
        orders.add(Order(buyDate,ticker,'buy',0,self.portfolio.cash))

        self.simulate(orders)
        self.plotPortfolioValue()

        return

    
    def simulate(self,orders):
        startingCash = self.portfolio.cash
        print("Starting Cash:",startingCash)

        dateList = list(self.pivotTable.index.date)

        for date in dateList:
            valueToDate = self.calculateValue(date)

            #Need to add two order functionality
            orderList = orders.getOrders(date)
            if(orderList is not None):
                for order in orderList:
                    try:
                        cost = self.pivotTable.loc[str(order.date)][order.ticker]
                    except:
                        print("ERROR: Ticker does not exist")
                        return

                    if((order.shares is None or order.shares == 0) and order.value == 0):
                        if(order.action == "buy"):
                            order.value = self.portfolio.cash
                        elif(order.action == "sell"):
                            order.value = self.portfolio.holdings[order.ticker]*cost
                        self.portfolio.executeActionDollars(order,cost)
                    elif(order.shares is None or order.shares == 0):
                        self.portfolio.executeActionDollars(order,cost)
                    else:
                        self.portfolio.executeActionShares(order,cost)

                    #print(date, self.portfolio.holdings)
                

            self.valueDf.loc[date] = valueToDate

        self.finalValue = self.valueDf.loc[date]['totalVal']
        self.totalReturn = ((self.finalValue/startingCash)-1)*100

        yearsElapsed = (dateList[-1] - dateList[0]).days/365

        if(self.finalValue < 0):
            self.annualizedReturn = 0
        else:
            self.annualizedReturn = math.pow((self.finalValue/startingCash),(1/yearsElapsed))

        self.printResults()


    def printResults(self):

        print("---------- RESULTS -----------")
        print("Final Cash: $", round(self.portfolio.cash,2))
        print("Final Value: $",round(self.finalValue,2))
        print("Total Return:",round(self.totalReturn,2),"%")
        print("Annualized Return:",round(self.annualizedReturn,2),"%")
        print("Holdings:",self.portfolio.holdings)
        print("\n")

        return

    def calculateValue(self,date):
        stockValue = 0
        for ticker in self.portfolio.holdings.keys():
            price = self.pivotTable.loc[str(date)][ticker]
            stockValue += price*self.portfolio.holdings[ticker]

        totalValue = stockValue + self.portfolio.cash
        return totalValue

    def plotPortfolioValue(self):
        plotPort = plt.figure(2)
        plt.plot(self.valueDf)
        plt.show()
        return
