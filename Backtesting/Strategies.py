import numpy as np 
import pandas as pd 
from pandas_datareader import data as pdr
import matplotlib.pyplot as plt 
from datetime import date
from datetime import datetime 
import math
from Backtest import Order, Orders, Portfolio, Backtest, TickData

'''
Helper class with calculation functions
'''
class Calculate:
    '''
    Input:
        priceTable: Dataframe with daily price values
        maDaysList: List of number of days over which to calculate moving average values
        maNamesList: List of names to use for the MA columns
        ticker: Assuming that ticker is the name of the column of price data

    Output:
        Dataframe with MA column appended to the end
    '''
    @staticmethod
    def calculateMovingAvgs(priceTable, maDaysList, maNamesList, tickers):
        
        maNameList = []

        for ticker in tickers:
            for ma in maDaysList:
                colName = str(ma) + " Day MA"
                maNameList.append(colName)
                priceTable[(ticker,colName)] = np.nan
                priceTable[(ticker,colName)] = priceTable[(ticker,"Price")].rolling(window=ma).mean()

        return priceTable

    @staticmethod
    def convertToMultiIndex(priceTable, tickers):

        priceTable.columns = pd.MultiIndex.from_tuples([(ticker,"Price") for ticker in tickers])

        return priceTable

    @staticmethod
    #Currently, can only handle 1 MA
    def calculatePercentageOverMA(maTable, tickers, maName):

        for ticker in tickers:
            maTable[(ticker,"% over MA")] = 100*((maTable[(ticker,"Price")]-maTable[(ticker,maName)])/maTable[(ticker,"Price")])
    
        return maTable


'''
Baseline Strategy - Buy and Hold security for duration specified
    - Used as a baseline to assess other strategies
'''
class BuyHold:
    def __init__(self, tickers, startDate, endDate):
        self.tickers = tickers
        self.startDate = startDate
        self.endDate = endDate
        

    '''
    Backtests the strategy, using the Backtesting.py framework
    
    Inputs:
        - startingCash (optional): Amount of cash to start the backtest with
        - plotReturn (optional): Plot the portfolio value over time
    '''
    def backtest(self, startingCash = 100, plotReturn = True):
        print("---------- STARTING BACKTEST-----------")
        print("Backtest Strategy: Buy+Hold")

        orders = Orders()

        for ticker in self.tickers:
            order = Order(self.startDate, ticker, 'buy', 0, startingCash)
            orders.add(order)

        backtestInstance = Backtest(self.startDate, self.endDate, startingCash)
        backtestInstance.simulate(orders)

        if plotReturn:
            backtestInstance.plotPortfolioValue()

        return


'''
Moving Average Cross Strategy
    - Buy when maLower rises above maUpper (ex when 8 day crosses 21 day)
    - Sell when maLower falls below maUpper

Inputs:
    - maLower: lower moving average (eg 8)
    - maUpper: upper moving average (eg 21)


NOTE: NOT UP TO DATE, NO GUARANTEE THIS SHIT WORKS
'''
class MACross:
    def __init__(self, ticker, maLower, maUpper, startDate, endDate):
        #Set start and end dates
        self.startDate = startDate
        self.endDate = endDate

        self.ticker = ticker
        self.maDaysList = [maLower, maUpper]
        self.maNamesList = [str(maLower) + " Day MA", str(maUpper) + " Day MA"] #find a better way of doing this

        self.tickData = TickData.getPivotTable(self.startDate, self.endDate)

        #Try to find ticker price data in tick data class, catch exception if it doesnt exist
        try:
            self.priceTable = self.tickData.filter([self.ticker])
        except:
            print("Ticker not found in pivot table")

        #Generate crossover dates and orders from defined functions
        self.crossoverDates = self.findCrossoverDates()
        self.orders = self.generateOrders()


    '''
    Find all dates where MA crossovers happen between the two supplied moving averages

    Returns a list of dates

    IMPORTANT: KIND OF BROKEN - need to add functionality to make sure that the first crossover date is a true buy signal
    Right now there is nothing checking this
    '''
    def findCrossoverDates(self):

        maTable = Calculate.calculateMovingAvgs(self.priceTable, self.maDaysList, self.maNamesList, self.ticker)

        previousLower = maTable[self.maNamesList[0]].shift(1)
        previousUpper = maTable[self.maNamesList[1]].shift(1)
        crossing = (((maTable[self.maNamesList[0]] < maTable[self.maNamesList[1]]) & (previousLower >= previousUpper))
            | ((maTable[self.maNamesList[0]] > maTable[self.maNamesList[1]]) & (previousLower <= previousUpper)))

        crossoverDates = maTable.loc[crossing.values == True].index

        return crossoverDates

    '''
    Uses generated list of dates, alternates between buy and sell orders
    Starts with buy order
    '''
    def generateOrders(self):
        orders = Orders()

        nextAction = "Buy"
        for date in self.crossoverDates:
            if(nextAction == "Buy"):
                orders.add(Order(date.date(), self.ticker, 'buy', 0, 0))
                nextAction = "Sell"
            else:
                orders.add(Order(date.date(), self.ticker, 'sell', 0, 0))
                nextAction = "Buy"
        
        return orders

    '''
    Plot the price along side vertical bars designating crossover dates or buy/sell points
        - Red lines are buy signals
        - Blue lines are sell signals
    '''
    def plotCrossoverDates(self):
        
        plt.plot(self.priceTable[self.ticker])
        
        for date in self.crossoverDates:
            if(self.orders.getOrder(date.date()).action == "buy"):
                plt.axvline(x=date, color='r', linestyle='--')
            elif(self.orders.getOrder(date.date()).action == "sell"):
                plt.axvline(x=date, color='b', linestyle='--')

        plt.show()

        return

    '''
    Backtests the strategy, using the Backtesting.py framework
    
    Inputs:
        - startingCash (optional): Amount of cash to start the backtest with
        - plotReturn (optional): Plot the portfolio value over time
    '''
    def backtest(self, startingCash = 100, plotReturn = True):
        backtestInstance = Backtest(self.startDate, self.endDate, startingCash)
        backtestInstance.simulate(self.orders)

        if plotReturn:
            backtestInstance.plotPortfolioValue()

        return

    
'''
Moving Average Rebound Strategy
    - Buy when price goes from greater than [upperPercentage] above [maDays] MA to lower than [lowerPercentage] above [maDays] MA
    - Sell when price goes from lower the [lowerPercentage] above [maDays] MA to higher than [upperPercentage] above [maDays] MA
    - TOBEADDED: If price stays below moving average for more then [nDaysBelowToSell], sell if holding stock

Inputs:
    - ticker
    - maDays: Moving average to use for calculations
    - lowerPercentage: smaller percentage to trigger buy (eg. 5%)
    - upperPercentage: higher percentage to trigger sell (eg. 30%)
'''
class MARebound:
    def __init__(self, tickers, maDays, lowerPercentage, upperPercentage, startDate, endDate, nDaysBelowToSell = 2):
        self.tickers = tickers
        self.maDays = maDays
        self.maName = str(self.maDays) +  " Day MA"
        self.lowerPercentage = lowerPercentage
        self.upperPercentage = upperPercentage
        
        self.startDate = startDate
        self.endDate = endDate

        self.nDaysBelowToSell = nDaysBelowToSell
    
        self.tickData = TickData.getPivotTable(self.startDate, self.endDate)

        self.buyOrderDict = {}
        self.sellOrderDict = {}

        #Try to find ticker price data in tick data class, catch exception if it doesnt exist
        try:
            self.priceTable = self.tickData.filter(self.tickers)
        except:
            print("Ticker not found in pivot table")

        self.priceTable = Calculate.convertToMultiIndex(self.priceTable, self.tickers)

        #Add column to dataframe with desired moving averages
        self.maTable = Calculate.calculateMovingAvgs(self.priceTable, [self.maDays], [self.maName], self.tickers)

        #Generate orders
        self.orders = self.generateOrders()

    def generateOrders(self):
    
        orders = Orders()

        #Add column to dataframe maTable with % price is above/below the MA
        #This value will be used to find buy/sell points
        self.maTable = Calculate.calculatePercentageOverMA(self.maTable, self.tickers, self.maName)

        #For plotting purposes - will move eventually


        #Iterate through all dates in simulation, look for buy/sell signals
        #Fill up our orders object

        #Leaving it at needing to adjust this for loop to deal with multiple tickers
        #Will need to also adjust the 0,0 buy/sells since they are using entire account for each one
        for ticker in self.tickers:
            firstActionBuy = True #ensure that first actions for each ticker is a buy
            hitLowerPercentage = False
            hitUpperPercentage = False

            buyList = []
            sellList = []

            for date, row in self.maTable.iterrows():

                if(row[(ticker,"% over MA")] > self.upperPercentage):
                    hitUpperPercentage = True

                if(row[(ticker,"% over MA")] < self.lowerPercentage):
                    hitLowerPercentage = True

                #If price goes < [lowerPercentage] above MA, from a point > [upperPercentage] above MA, buy
                if(hitUpperPercentage and row[(ticker,"% over MA")] < self.lowerPercentage):
                    buyList.append(date.date())
                    orders.add(Order(date.date(), ticker, 'buy', 0, 100))
                    firstActionBuy = False
                    hitUpperPercentage = False

                #If price goes > [upperPercentage] above MA, from a point < [lowerPercentage] above MA, sell
                if(hitLowerPercentage and row[(ticker,"% over MA")] > self.upperPercentage  and firstActionBuy == False):
                    sellList.append(date.date())
                    orders.add(Order(date.date(), ticker, 'sell', 0, 0))
                    hitLowerPercentage = False

            self.buyOrderDict[ticker] = buyList
            self.sellOrderDict[ticker] = sellList
            
        return orders

    def plotOrderDates(self, ticker):
        plt.plot(self.maTable[(ticker,"Price")])

        #Plot execution dates

        for xc in self.buyOrderDict[ticker]:
            plt.axvline(x=xc, color='r', linestyle='--')

        for xc in self.sellOrderDict[ticker]:
            plt.axvline(x=xc, color='b', linestyle='--')

        plt.show()  



    '''
    Backtests the strategy, using the Backtesting.py framework
    
    Inputs:
        - startingCash (optional): Amount of cash to start the backtest with
        - plotReturn (optional): Plot the portfolio value over time
    '''
    def backtest(self, startingCash = 100, plotReturn = True):
        print("---------- STARTING BACKTEST-----------")
        print("Backtest Strategy: MARebound")

        backtestInstance = Backtest(self.startDate, self.endDate, startingCash)
        backtestInstance.simulate(self.orders)

        if plotReturn:
            backtestInstance.plotPortfolioValue()

        return
        
    

if __name__ == '__main__':
    
    #macross = MACross('ATWT', 15, 50, date(2018,1,5), date(2021,2,13))
    #macross.plotCrossoverDates()
    #macross.backtest()
    

    maRebound = MARebound(['STEV'], 8, 5, 50, date(2018,1,5), date(2021,2,13))
    #maRebound.plotOrderDates('STEV')
    maRebound.backtest(100,plotReturn=True)

    #buyHold = BuyHold(['STEV','ATWT'], date(2018,1,5), date(2021,2,13))
    #buyHold.backtest(200, plotReturn = False)


        


