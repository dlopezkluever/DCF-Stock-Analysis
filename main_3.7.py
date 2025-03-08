# most complex, like main 3_1.py
# Where it builds off #ain_4.py (2.27) progress, making the new revamped functions seen in 3_1, but with the full implementation
# that uses a OOP for the Financial Data Acquisition implemetation and runs with the use of a main loop


import os
import numpy as np
import pandas as pd
import yfinance as yf
import time
from datetime import datetime 
import matplotlib.pyplot as plt
from tqdm import tqdm
import random
import requests
from sec_api import QueryApi, RenderApi
import pandas_datareader as pdr
import traceback
from scipy import stats
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning) 
    
# If you make seperate files for the main functions, be sure to install: 
# from wacc_calculator import calculate_wacc
# from growth_rate_estimator import calculate_growth_rates
# from terminal_value_calculator import calculate_terminal_value

 
class FinancialDataAcquisition:
    """
    Enhanced financial data acquisition module with multiple data sources
    and fallback mechanisms for reliable DCF analysis.
    """
    
    def __init__(self, sec_api_key=None, fmp_api_key=None, alpha_vantage_key=None):
        """
        Initialize with API keys for various financial data sources.
        
        Args:
            sec_api_key (str): API key for SEC API (https://sec-api.io)
            fmp_api_key (str): API key for Financial Modeling Prep
            alpha_vantage_key (str): API key for Alpha Vantage
        """
        self.sec_api_key = sec_api_key or os.environ.get('SEC_API_KEY')
        self.fmp_api_key = fmp_api_key or os.environ.get('FMP_API_KEY')
        self.alpha_vantage_key = alpha_vantage_key or os.environ.get('ALPHA_VANTAGE_KEY')
        
        # SEC API client if available
        self.sec_query_api = QueryApi(self.sec_api_key) if self.sec_api_key else None
        self.sec_render_api = RenderApi(self.sec_api_key) if self.sec_api_key else None
        
        # Standard SEC API headers
        self.sec_headers = {
            'User-Agent': 'Financial Analysis Tool user@example.com',
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'data.sec.gov'
        }
        
        # Base URLs
        self.SEC_SUBMISSION_BASE = "https://data.sec.gov/submissions/CIK{}.json"
        self.SEC_COMPANY_CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{}/us-gaap/{}.json"
        self.FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
        self.ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
    
    def get_financial_data(self, ticker, cik=None, retry_count=3):
        """
        Multi-source financial data acquisition with intelligent fallbacks.
        
        Args:
            ticker (str): Stock ticker symbol
            cik (str): Company CIK number (will be looked up if not provided)
            retry_count (int): Number of retry attempts per source
            
        Returns:
            dict: Standardized financial data for DCF analysis
        """
        print(f"\nFetching financial data for {ticker}...")
        
        # If CIK not provided, try to look it up
        if not cik:
            cik = self._get_cik_for_ticker(ticker)
        
        # Try sources in order of reliability
        data = None
        
        # 1. Try SEC Edgar API first (most authoritative)
        if self.sec_api_key:
            data = self._get_data_from_sec(ticker, cik, retry_count)
        
        # 2. Try Financial Modeling Prep if SEC failed
        if not data and self.fmp_api_key:
            data = self._get_data_from_fmp(ticker, retry_count)
            
        # 3. Try Alpha Vantage if previous sources failed
        if not data and self.alpha_vantage_key:
            data = self._get_data_from_alpha_vantage(ticker, retry_count)
            
        # 4. Fall back to Yahoo Finance as last resort
        if not data:
            data = self._get_data_from_yahoo(ticker, retry_count)
            
        return data
    
    def _get_cik_for_ticker(self, ticker):
        """Get CIK number for a ticker symbol"""
        try:
            # Try SEC API first
            if self.sec_api_key:
                query = {
                    "query": f"ticker:{ticker}",
                    "formTypes": ["10-K"],
                    "startDate": "2020-01-01",
                    "endDate": datetime.now().strftime("%Y-%m-%d")
                }
                response = self.sec_query_api.get_filings(query)
                if response and 'filings' in response and len(response['filings']) > 0:
                    return response['filings'][0]['cik']
            
            # Fallback to lookup table or other methods
            cik_lookup = {
                "AAPL": "0000320193", "MSFT": "0000789019", "AMZN": "0001018724", 
                "GOOGL": "0001652044", "TSLA": "0001318605", "META": "0001326801", 
                "NVDA": "0001045810", "PYPL": "0001633917", "ADBE": "0000796343", 
                "NFLX": "0001065280"
            }
            
            return cik_lookup.get(ticker)
        except Exception as e:
            print(f"Error looking up CIK for {ticker}: {e}")
            return None
    
    def _get_data_from_sec(self, ticker, cik, retry_count=3):
        """Get financial data from SEC EDGAR filings"""
        if not cik:
            print("Cannot fetch SEC data without CIK")
            return None
            
        for attempt in range(retry_count):
            try:
                # Ensure CIK is 10 digits with leading zeros
                cik_padded = cik.lstrip('0').zfill(10)
                
                # Get cash flow data
                cash_flow_data = self._get_sec_concept_data(cik_padded, "NetCashProvidedByUsedInOperatingActivities")
                capex_data = self._get_sec_concept_data(cik_padded, "PaymentsToAcquirePropertyPlantAndEquipment")
                
                if not cash_flow_data or not capex_data:
                    print(f"Missing required SEC data, trying alternative concepts...")
                    # Try alternative concepts
                    if not cash_flow_data:
                        cash_flow_data = self._get_sec_concept_data(cik_padded, "CashProvidedByUsedInOperatingActivities")
                    if not capex_data:
                        capex_data = self._get_sec_concept_data(cik_padded, "CapitalExpenditures")
                
                if not cash_flow_data or not capex_data:
                    print(f"Could not retrieve complete SEC cash flow data for {ticker}")
                    if attempt < retry_count - 1:
                        continue
                    return None
                
                # Get shares outstanding data
                shares_data = self._get_sec_concept_data(cik_padded, "CommonStockSharesOutstanding") or \
                             self._get_sec_concept_data(cik_padded, "WeightedAverageNumberOfSharesOutstandingBasic")
                
                if not shares_data:
                    print(f"Could not retrieve SEC shares data for {ticker}")
                    if attempt < retry_count - 1:
                        continue
                    return None
                
                # Extract the latest annual data
                latest_cash_flow = self._extract_latest_annual_value(cash_flow_data)
                latest_capex = self._extract_latest_annual_value(capex_data)
                latest_shares = self._extract_latest_annual_value(shares_data)
                
                if not all([latest_cash_flow, latest_capex, latest_shares]):
                    print(f"Missing latest values from SEC data for {ticker}")
                    if attempt < retry_count - 1:
                        continue
                    return None
                
                # Get current price from Yahoo Finance (SEC doesn't provide this)
                stock = yf.Ticker(ticker)
                current_price = stock.history(period="1d")["Close"].iloc[-1]
                
                # Calculate FCF (capex is usually negative in filings)
                # Make capex negative if positive
                if latest_capex > 0:
                    latest_capex = -latest_capex
                    
                free_cash_flow = latest_cash_flow + latest_capex
                
                # Create historical data for growth calculation
                historical_cash_flows = self._get_historical_annual_values(cash_flow_data, years=5)
                historical_capex = self._get_historical_annual_values(capex_data, years=5)
                
                # Make capex negative if positive
                historical_capex = [-x if x > 0 else x for x in historical_capex]
                
                # Calculate historical FCF
                historical_fcf = [cf + capex for cf, capex in zip(historical_cash_flows, historical_capex) if cf and capex]
                
                # Also get revenue data for growth calculations
                revenue_data = self._get_sec_concept_data(cik_padded, "Revenues") or \
                              self._get_sec_concept_data(cik_padded, "RevenueFromContractWithCustomerExcludingAssessedTax")
                historical_revenue = self._get_historical_annual_values(revenue_data, years=5)
                
                # Create a structure similar to what the rest of the code expects
                return {
                    'free_cash_flow': free_cash_flow,
                    'shares_outstanding': latest_shares,
                    'current_price': current_price,
                    'ticker': ticker,
                    'historical_fcf': historical_fcf,
                    'historical_revenue': historical_revenue,
                    'data_source': 'SEC EDGAR'
                }
                
            except Exception as e:
                print(f"SEC data attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    print(f"Retrying in 2 seconds...")
                    time.sleep(2)
        
        return None
    
    def _get_sec_concept_data(self, cik_padded, concept):
        """Get specific concept data from SEC API"""
        url = self.SEC_COMPANY_CONCEPT.format(cik_padded, concept)
        
        try:
            response = requests.get(url, headers=self.sec_headers)
            
            if response.status_code == 200:
                result = response.json()
                if 'units' in result and 'USD' in result['units']:
                    return result['units']['USD']
                return None
            else:
                print(f"Error fetching {concept} data: Status {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception while fetching {concept}: {e}")
            return None
    
    def _extract_latest_annual_value(self, concept_data):
        """Extract the most recent annual value from SEC concept data"""
        if not concept_data:
            return None
            
        # Filter for annual reports (10-K)
        annual_data = [item for item in concept_data if item.get('form') == '10-K']
        
        if not annual_data:
            # Try to use any data as fallback
            annual_data = concept_data
            
        # Sort by end date (most recent first)
        sorted_data = sorted(annual_data, key=lambda x: x.get('end', '1900-01-01'), reverse=True)
        
        if sorted_data:
            return sorted_data[0].get('val')
            
        return None
    
    def _get_historical_annual_values(self, concept_data, years=5):
        """Get historical annual values for a concept"""
        if not concept_data:
            return []
            
        # Filter for annual reports (10-K)
        annual_data = [item for item in concept_data if item.get('form') == '10-K']
        
        if not annual_data:
            # Try to use any data as fallback
            annual_data = concept_data
            
        # Sort by end date (most recent first)
        sorted_data = sorted(annual_data, key=lambda x: x.get('end', '1900-01-01'), reverse=True)
        
        # Get the values for the specified number of years
        values = []
        for i, data in enumerate(sorted_data):
            if i >= years:
                break
            values.append(data.get('val'))
            
        return values
    
    def _get_data_from_fmp(self, ticker, retry_count=3):
        """Get financial data from Financial Modeling Prep API"""
        if not self.fmp_api_key:
            return None
            
        for attempt in range(retry_count):
            try:
                # Get cash flow statement
                cash_flow_url = f"{self.FMP_BASE_URL}/cash-flow-statement/{ticker}?period=annual&limit=5&apikey={self.fmp_api_key}"
                cf_response = requests.get(cash_flow_url)
                
                if cf_response.status_code != 200:
                    print(f"FMP API error: {cf_response.status_code}")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                    
                cash_flow_data = cf_response.json()
                
                if not cash_flow_data:
                    print("No cash flow data from FMP")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                
                # Get current company profile for shares and price
                profile_url = f"{self.FMP_BASE_URL}/profile/{ticker}?apikey={self.fmp_api_key}"
                profile_response = requests.get(profile_url)
                
                if profile_response.status_code != 200:
                    print(f"FMP API profile error: {profile_response.status_code}")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                    
                profile_data = profile_response.json()
                
                if not profile_data or len(profile_data) == 0:
                    print("No profile data from FMP")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                
                # Extract the necessary data
                latest_cf = cash_flow_data[0]
                free_cash_flow = latest_cf.get('freeCashFlow')
                
                # If FCF not directly available, calculate it
                if free_cash_flow is None:
                    operating_cash_flow = latest_cf.get('netCashProvidedByOperatingActivities')
                    capital_expenditure = latest_cf.get('capitalExpenditure', 0)
                    # Make sure capex is negative
                    if capital_expenditure > 0:
                        capital_expenditure = -capital_expenditure
                    free_cash_flow = operating_cash_flow + capital_expenditure
                
                # Get historical FCF for growth calculations
                historical_fcf = []
                for cf in cash_flow_data:
                    fcf = cf.get('freeCashFlow')
                    if fcf is None:
                        ocf = cf.get('netCashProvidedByOperatingActivities')
                        capex = cf.get('capitalExpenditure', 0)
                        if capex > 0:
                            capex = -capex
                        fcf = ocf + capex
                    historical_fcf.append(fcf)
                
                # Get revenue data
                income_stmt_url = f"{self.FMP_BASE_URL}/income-statement/{ticker}?period=annual&limit=5&apikey={self.fmp_api_key}"
                income_response = requests.get(income_stmt_url)
                
                historical_revenue = []
                if income_response.status_code == 200:
                    income_data = income_response.json()
                    historical_revenue = [stmt.get('revenue') for stmt in income_data]
                
                # Extract profile information
                profile = profile_data[0]
                shares_outstanding = profile.get('mktCap') / profile.get('price') if profile.get('price', 0) > 0 else None
                current_price = profile.get('price')
                
                return {
                    'free_cash_flow': free_cash_flow,
                    'shares_outstanding': shares_outstanding,
                    'current_price': current_price,
                    'ticker': ticker,
                    'historical_fcf': historical_fcf,
                    'historical_revenue': historical_revenue,
                    'data_source': 'Financial Modeling Prep'
                }
                
            except Exception as e:
                print(f"FMP data attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    print(f"Retrying in 2 seconds...")
                    time.sleep(2)
        
        return None
    
    def _get_data_from_alpha_vantage(self, ticker, retry_count=3):
        """Get financial data from Alpha Vantage API"""
        if not self.alpha_vantage_key:
            return None
            
        for attempt in range(retry_count):
            try:
                # Get cash flow statement
                cf_url = f"{self.ALPHA_VANTAGE_BASE}?function=CASH_FLOW&symbol={ticker}&apikey={self.alpha_vantage_key}"
                cf_response = requests.get(cf_url)
                
                if cf_response.status_code != 200:
                    print(f"Alpha Vantage API error: {cf_response.status_code}")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                    
                cf_data = cf_response.json()
                
                if 'annualReports' not in cf_data or not cf_data['annualReports']:
                    print("No cash flow data from Alpha Vantage")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                
                # Get overview for shares outstanding
                overview_url = f"{self.ALPHA_VANTAGE_BASE}?function=OVERVIEW&symbol={ticker}&apikey={self.alpha_vantage_key}"
                overview_response = requests.get(overview_url)
                
                if overview_response.status_code != 200:
                    print(f"Alpha Vantage API overview error: {overview_response.status_code}")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return None
                    
                overview_data = overview_response.json()
                
                # Get current price
                quote_url = f"{self.ALPHA_VANTAGE_BASE}?function=GLOBAL_QUOTE&symbol={ticker}&apikey={self.alpha_vantage_key}"
                quote_response = requests.get(quote_url)
                current_price = None
                
                if quote_response.status_code == 200:
                    quote_data = quote_response.json()
                    if 'Global Quote' in quote_data and '05. price' in quote_data['Global Quote']:
                        current_price = float(quote_data['Global Quote']['05. price'])
                
                if not current_price:
                    # Fallback to Yahoo Finance for price
                    stock = yf.Ticker(ticker)
                    current_price = stock.history(period="1d")["Close"].iloc[-1]
                
                # Extract financial data
                latest_cf = cf_data['annualReports'][0]
                operating_cash_flow = float(latest_cf.get('operatingCashflow', 0))
                capital_expenditure = float(latest_cf.get('capitalExpenditures', 0))
                
                # Make sure capex is negative for FCF calculation
                if capital_expenditure > 0:
                    capital_expenditure = -capital_expenditure
                    
                free_cash_flow = operating_cash_flow + capital_expenditure
                
                # Get historical FCF
                historical_fcf = []
                for cf in cf_data['annualReports']:
                    ocf = float(cf.get('operatingCashflow', 0))
                    capex = float(cf.get('capitalExpenditures', 0))
                    if capex > 0:
                        capex = -capex
                    historical_fcf.append(ocf + capex)
                
                # Get revenue data
                income_url = f"{self.ALPHA_VANTAGE_BASE}?function=INCOME_STATEMENT&symbol={ticker}&apikey={self.alpha_vantage_key}"
                income_response = requests.get(income_url)
                
                historical_revenue = []
                if income_response.status_code == 200:
                    income_data = income_response.json()
                    if 'annualReports' in income_data:
                        historical_revenue = [float(stmt.get('totalRevenue', 0)) for stmt in income_data['annualReports']]
                
                # Get shares outstanding
                shares_outstanding = float(overview_data.get('SharesOutstanding', 0))
                
                if not shares_outstanding:
                    # Try to calculate from market cap
                    market_cap = float(overview_data.get('MarketCapitalization', 0))
                    if market_cap > 0 and current_price > 0:
                        shares_outstanding = market_cap / current_price
                
                return {
                    'free_cash_flow': free_cash_flow,
                    'shares_outstanding': shares_outstanding,
                    'current_price': current_price,
                    'ticker': ticker,
                    'historical_fcf': historical_fcf,
                    'historical_revenue': historical_revenue,
                    'data_source': 'Alpha Vantage'
                }
                
            except Exception as e:
                print(f"Alpha Vantage data attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    print(f"Retrying in 2 seconds...")
                    time.sleep(2)
        
        return None
    
    def _get_data_from_yahoo(self, ticker, retry_count=3):
        """Fallback to Yahoo Finance (your original method, but enhanced)"""
        for attempt in range(retry_count):
            try:
                stock = yf.Ticker(ticker)
                
                # Get cash flow statements with better error handling
                try:
                    cash_flow = stock.cashflow
                    if cash_flow is None or cash_flow.empty:
                        print("Primary cash flow data empty, trying quarterly...")
                        quarterly_cf = stock.quarterly_cashflow
                        if quarterly_cf is not None and not quarterly_cf.empty:
                            # Convert quarterly to annual by summing the most recent 4 quarters
                            if quarterly_cf.shape[1] >= 4:
                                cash_flow = quarterly_cf.iloc[:, :4].sum(axis=1).to_frame()
                except Exception as e:
                    print(f"Error fetching cash flow: {e}")
                    cash_flow = None
                
                if cash_flow is None or cash_flow.empty:
                    print("Could not retrieve cash flow data")
                    if attempt < retry_count - 1:
                        print(f"Retrying ({attempt + 1}/{retry_count})...")
                        time.sleep(2)
                        continue
                    return None
                
                # Calculate Free Cash Flow
                free_cash_flow = None
                if 'Free Cash Flow' in cash_flow.index:
                    free_cash_flow = cash_flow.loc['Free Cash Flow'].iloc[0]
                elif all(item in cash_flow.index for item in ['Operating Cash Flow', 'Capital Expenditure']):
                    operating_cash_flow = cash_flow.loc['Operating Cash Flow'].iloc[0]
                    capital_expenditure = cash_flow.loc['Capital Expenditure'].iloc[0]
                    free_cash_flow = operating_cash_flow + capital_expenditure  # CapEx is negative
                
                if free_cash_flow is None or np.isnan(free_cash_flow):
                    print(f"Cannot calculate FCF for {ticker}")
                    if attempt < retry_count - 1:
                        continue
                    return None
                
                # Get historical FCF for better growth calculations
                historical_fcf = []
                try:
                    # Get multiple years of data if available
                    for i in range(min(5, cash_flow.shape[1])):
                        if 'Free Cash Flow' in cash_flow.index:
                            fcf = cash_flow.loc['Free Cash Flow'].iloc[i]
                        elif all(item in cash_flow.index for item in ['Operating Cash Flow', 'Capital Expenditure']):
                            ocf = cash_flow.loc['Operating Cash Flow'].iloc[i]
                            capex = cash_flow.loc['Capital Expenditure'].iloc[i]
                            fcf = ocf + capex
                        else:
                            break
                        
                        if not np.isnan(fcf):
                            historical_fcf.append(fcf)
                except:
                    # If we can't get historical data, just use the latest
                    if free_cash_flow is not None and not np.isnan(free_cash_flow):
                        historical_fcf = [free_cash_flow]
                
                # Get historical revenue
                historical_revenue = []
                try:
                    income_stmt = stock.income_stmt
                    if income_stmt is not None and not income_stmt.empty and 'Total Revenue' in income_stmt.index:
                        for i in range(min(5, income_stmt.shape[1])):
                            rev = income_stmt.loc['Total Revenue'].iloc[i]
                            if not np.isnan(rev):
                                historical_revenue.append(rev)
                except:
                    pass
                
                # Get shares outstanding with multiple fallback methods
                shares_outstanding = None
                
                # Method 1: From info
                try:
                    shares_outstanding = stock.info.get('sharesOutstanding')
                except:
                    print("Could not get shares outstanding from info")
                
                # Method 2: From quarterly data
                if shares_outstanding is None or np.isnan(shares_outstanding):
                    try:
                        bal_sheet = stock.balance_sheet
                        if bal_sheet is not None and not bal_sheet.empty:
                            if 'Share Issued' in bal_sheet.index:
                                shares_outstanding = bal_sheet.loc['Share Issued'].iloc[0]
                    except:
                        print("Could not calculate shares outstanding from balance sheet")
                
                # Method 3: Use market cap / price
                if shares_outstanding is None or np.isnan(shares_outstanding):
                    try:
                        market_cap = stock.info.get('marketCap')
                        last_price = stock.history(period="1d")["Close"].iloc[-1]
                        if market_cap and last_price and last_price > 0:
                            shares_outstanding = market_cap / last_price
                    except:
                        print("Could not calculate shares outstanding from market cap")
                
                if shares_outstanding is None or np.isnan(shares_outstanding):
                    print(f"Could not determine shares outstanding for {ticker}")
                    if attempt < retry_count - 1:
                        continue
                    return None
                
                # Get current price
                try:
                    current_price = stock.history(period="1d")["Close"].iloc[-1]
                except:
                    print(f"Could not fetch current price for {ticker}")
                    if attempt < retry_count - 1:
                        continue
                    return None
                
                return {
                    'free_cash_flow': free_cash_flow,
                    'shares_outstanding': shares_outstanding,
                    'current_price': current_price,
                    'ticker': ticker,
                    'historical_fcf': historical_fcf,
                    'historical_revenue': historical_revenue,
                    'data_source': 'Yahoo Finance'
                }
            
            except Exception as e:
                print(f"Yahoo Finance attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    print(f"Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    print(f"All {retry_count} attempts failed for {ticker}")
                    return None

    """
    Enhanced financial data acquisition module with multiple data sources
    and fallback mechanisms for reliable DCF analysis.
    """

####################################################################################################################################################
############################ END OF FINANCIALDATAACQUISTION ########################################################################################
####################################################################################################################################################
############################ Calculation Functions Below    ########################################################################################
####################################################################################################################################################

####################################################################################################################################################
#################################    WACC  Calculation    ##########################################################################################
####################################################################################################################################################

def calculate_wacc(ticker, financial_data=None):
    """
    Calculate WACC with improved error handling, data validation and multiple external data sources.
    
    Args:
        ticker (str): Stock ticker symbol
        financial_data (dict): Financial data if already fetched
    
    Returns:
        dict: WACC components and final value
    """
    print(f"Calculating WACC for {ticker}...")
    
    try:
        if financial_data and 'stock' in financial_data:
            stock = financial_data['stock']
        else:
            stock = yf.Ticker(ticker)
        
        # Get risk-free rate from Treasury data
        risk_free_rate = get_treasury_yield()  # Implement this function to fetch current 10Y Treasury yield
        if risk_free_rate is None:
            risk_free_rate = 0.042  # Fallback value if API call fails
        
        # Get industry data from Damodaran dataset
        industry_data = get_damodaran_industry_data(ticker)  # Implement this to fetch industry beta, risk premium
        
        # Get balance sheet and financials with expanded timeframes
        try:
            # Try to get data for longer periods to increase chances of getting data
            balance_sheet = stock.balance_sheet
            financials = stock.financials
            income_statement = stock.income_stmt  # Get income statement explicitly
            cash_flow = stock.cashflow  # Get cash flow statement explicitly
            
            # Fallback to quarterly data if annual is empty
            if balance_sheet.empty or len(balance_sheet.columns) == 0:
                balance_sheet = stock.quarterly_balance_sheet
                if not balance_sheet.empty and len(balance_sheet.columns) > 0:
                    print("Using latest quarterly balance sheet")
            
            if financials.empty or len(financials.columns) == 0:
                financials = stock.quarterly_financials
                if not financials.empty and len(financials.columns) > 0:
                    print("Using latest quarterly financials")
                    
            if income_statement is None or (hasattr(income_statement, 'empty') and income_statement.empty):
                income_statement = stock.quarterly_income_stmt
                
            if cash_flow is None or (hasattr(cash_flow, 'empty') and cash_flow.empty):
                cash_flow = stock.quarterly_cashflow
                
        except Exception as e:
            print(f"Error getting financial statements: {e}")
            return default_wacc_values(ticker, industry_data)
        
        # Validate that we have the necessary data
        if ((balance_sheet is None or hasattr(balance_sheet, 'empty') and balance_sheet.empty) and 
            (financials is None or hasattr(financials, 'empty') and financials.empty)):
            print("Missing required financial statements")
            return default_wacc_values(ticker, industry_data)
        
        # Calculate total debt with improved robustness
        total_debt = 0
        debt_items = ['Total Debt', 'Long Term Debt', 'Short Long Term Debt', 
                    'Current Debt', 'Short Term Debt', 'Current Long Term Debt']
        
        # Check if balance sheet is available and not empty
        if balance_sheet is not None and not (hasattr(balance_sheet, 'empty') and balance_sheet.empty):
            for item in debt_items:
                if item in balance_sheet.index:
                    debt_value = balance_sheet.loc[item].iloc[0]
                    if not pd.isna(debt_value) and not np.isnan(debt_value):
                        total_debt += debt_value
        
        # If no debt items found in balance sheet, try to get from info
        if total_debt == 0:
            try:
                total_debt = stock.info.get('totalDebt', 0)
                if pd.isna(total_debt) or np.isnan(total_debt):
                    total_debt = 0
            except:
                pass
                
        # If still no debt, try alternative fields
        if total_debt == 0:
            try:
                # Sometimes available under different keys
                for field in ['longTermDebt', 'shortTermDebt', 'totalDebt']:
                    if field in stock.info:
                        value = stock.info.get(field, 0)
                        if value and not pd.isna(value) and not np.isnan(value):
                            total_debt += value
            except:
                pass
        
        # NEW: Check FRED API for total debt data as another data source
        if total_debt == 0:
            try:
                total_debt = get_fred_corporate_debt(ticker)
            except:
                pass
        
        # Get Market Cap (Equity Value) with multiple methods
        market_cap = None
        try:
            market_cap = stock.info.get('marketCap')
            if pd.isna(market_cap) or np.isnan(market_cap):
                market_cap = None
        except:
            pass
        
        if market_cap is None:
            try:
                # Try to get from info dict with multiple keys
                for field in ['marketCapitalization', 'enterpriseValue']:
                    val = stock.info.get(field)
                    if val and not pd.isna(val) and not np.isnan(val):
                        market_cap = val
                        break
            except:
                pass
        
        if market_cap is None:
            try:
                # Estimate from shares outstanding and price
                shares = stock.info.get('sharesOutstanding')
                price = stock.history(period="1d")["Close"].iloc[-1]
                if shares and price and not pd.isna(shares) and not np.isnan(shares):
                    market_cap = shares * price
            except:
                pass
                
        # Try to estimate market cap from financial statements if still not available
        if market_cap is None:
            try:
                if 'Common Stock' in balance_sheet.index:
                    shares = balance_sheet.loc['Common Stock'].iloc[0]
                    price = stock.history(period="1d")["Close"].iloc[-1]
                    if shares and price:
                        market_cap = shares * price
            except:
                pass
                
        # NEW: Check another data source for market cap
        if market_cap is None:
            try:
                market_cap = get_market_cap_from_alternative_source(ticker)
            except:
                pass
        
        if market_cap is None or np.isnan(market_cap) or market_cap == 0:
            print("Could not determine market cap, using industry average values")
            return default_wacc_values(ticker, industry_data)
        
        # Total Capital = Debt + Equity
        total_capital = total_debt + market_cap
        
        # Weight of Debt and Equity (with validation)
        weight_debt = total_debt / total_capital if total_capital > 0 else 0
        weight_equity = market_cap / total_capital if total_capital > 0 else 1
        
        # Validate weights sum to 1
        if abs(weight_debt + weight_equity - 1.0) > 0.01:
            weight_sum = weight_debt + weight_equity
            if weight_sum > 0:  # Prevent division by zero
                weight_debt = weight_debt / weight_sum
                weight_equity = weight_equity / weight_sum
            else:
                weight_debt = 0
                weight_equity = 1
        
        # Cost of Debt calculation with multiple methods
        cost_of_debt = None
        
        # NEW: First check bond yield data if available
        try:
            cost_of_debt = get_corporate_bond_yield(ticker)
            if cost_of_debt is not None and (cost_of_debt < 0.01 or cost_of_debt > 0.15):
                print(f"Bond yield data questionable: {cost_of_debt:.2%}")
                cost_of_debt = None
        except:
            pass
        
        # Method 1: Calculate from interest expense and total debt
        if cost_of_debt is None and financials is not None and not financials.empty and total_debt > 0:
            try:
                interest_fields = ['Interest Expense', 'Interest Expense, Net', 'Interest Paid', 'Net Interest Expense']
                interest_expense = None
                
                for field in interest_fields:
                    if field in financials.index:
                        value = abs(financials.loc[field].iloc[0])
                        if not pd.isna(value) and not np.isnan(value) and value > 0:
                            interest_expense = value
                            break
                
                if interest_expense is not None:
                    calculated_cod = interest_expense / total_debt
                    
                    # NEW: More sophisticated validation of cost of debt based on company size and credit rating
                    if market_cap > 200e9:  # Large cap likely has better credit rating
                        if 0.01 <= calculated_cod <= 0.06:
                            cost_of_debt = calculated_cod
                        else:
                            print(f"Large cap calculated cost of debt {calculated_cod:.2%} seems unreasonable")
                    elif market_cap > 10e9:  # Mid cap
                        if 0.02 <= calculated_cod <= 0.08:
                            cost_of_debt = calculated_cod
                        else:
                            print(f"Mid cap calculated cost of debt {calculated_cod:.2%} seems unreasonable")
                    else:  # Small cap
                        if 0.03 <= calculated_cod <= 0.12:
                            cost_of_debt = calculated_cod
                        else:
                            print(f"Small cap calculated cost of debt {calculated_cod:.2%} seems unreasonable")
            except Exception as e:
                print(f"Error calculating cost of debt from interest expense: {e}")
        
        # Method 2: Calculate from interest coverage ratio
        if cost_of_debt is None and income_statement is not None and not (hasattr(income_statement, 'empty') and income_statement.empty):
            try:
                ebit_fields = ['EBIT', 'Operating Income', 'Income Before Tax', 'Earnings Before Interest And Tax']
                ebit = None
                
                for field in ebit_fields:
                    if field in income_statement.index:
                        ebit_val = income_statement.loc[field].iloc[0]
                        if not pd.isna(ebit_val) and not np.isnan(ebit_val) and ebit_val > 0:
                            ebit = ebit_val
                            break
                
                interest_fields = ['Interest Expense', 'Interest Expense, Net', 'Interest Paid', 'Net Interest Expense']
                interest_expense = None
                
                # Try to get interest expense from income statement first
                for field in interest_fields:
                    if field in income_statement.index:
                        value = abs(income_statement.loc[field].iloc[0])
                        if not pd.isna(value) and not np.isnan(value) and value > 0:
                            interest_expense = value
                            break
                
                # If not found in income statement, try financials
                if interest_expense is None and financials is not None and not financials.empty:
                    for field in interest_fields:
                        if field in financials.index:
                            value = abs(financials.loc[field].iloc[0])
                            if not pd.isna(value) and not np.isnan(value) and value > 0:
                                interest_expense = value
                                break
                
                if ebit is not None and interest_expense is not None and interest_expense > 0:
                    interest_coverage = ebit / interest_expense
                    
                    # NEW: More granular scale for cost of debt based on interest coverage
                    # Updated to match current credit market conditions
                    if interest_coverage > 15:
                        cost_of_debt = risk_free_rate + 0.005  # AAA rating
                    elif interest_coverage > 10:
                        cost_of_debt = risk_free_rate + 0.01  # AA rating
                    elif interest_coverage > 7:
                        cost_of_debt = risk_free_rate + 0.015  # A+ rating
                    elif interest_coverage > 5:
                        cost_of_debt = risk_free_rate + 0.02  # A rating
                    elif interest_coverage > 4:
                        cost_of_debt = risk_free_rate + 0.025  # A- rating
                    elif interest_coverage > 3:
                        cost_of_debt = risk_free_rate + 0.035  # BBB rating
                    elif interest_coverage > 2.5:
                        cost_of_debt = risk_free_rate + 0.045  # BB+ rating
                    elif interest_coverage > 2:
                        cost_of_debt = risk_free_rate + 0.055  # BB rating
                    elif interest_coverage > 1.5:
                        cost_of_debt = risk_free_rate + 0.07  # B+ rating
                    elif interest_coverage > 1:
                        cost_of_debt = risk_free_rate + 0.09  # B rating
                    else:
                        cost_of_debt = risk_free_rate + 0.12  # CCC rating
            except Exception as e:
                print(f"Error calculating cost of debt from interest coverage: {e}")
                
        # Method 3: Use leverage ratio to estimate based on risk
        if cost_of_debt is None:
            try:
                # Approximate based on leverage and company size
                debt_to_capital = total_debt / total_capital if total_capital > 0 else 0
                
                # NEW: Use industry-specific data if available
                industry_premium = 0.0
                if industry_data and 'default_spread' in industry_data:
                    industry_premium = industry_data['default_spread']
                
                if market_cap > 200e9:  # Large cap
                    size_premium = 0.005
                elif market_cap > 10e9:  # Mid cap
                    size_premium = 0.01
                else:  # Small cap
                    size_premium = 0.02
                    
                if debt_to_capital > 0.7:  # Very high debt ratio
                    leverage_premium = 0.04
                elif debt_to_capital > 0.5:  # High debt ratio
                    leverage_premium = 0.03
                elif debt_to_capital > 0.3:  # Medium debt ratio
                    leverage_premium = 0.02
                elif debt_to_capital > 0.1:  # Low-Medium debt ratio
                    leverage_premium = 0.01
                else:  # Very low debt ratio
                    leverage_premium = 0.005
                    
                cost_of_debt = risk_free_rate + size_premium + leverage_premium + industry_premium
                
                # Sanity check
                if cost_of_debt < risk_free_rate:
                    cost_of_debt = risk_free_rate + 0.01  # Minimum premium over risk-free rate
            except Exception as e:
                print(f"Error calculating cost of debt from leverage: {e}")
        
        # Fallback
        if cost_of_debt is None or pd.isna(cost_of_debt) or np.isnan(cost_of_debt):
            print("Using default cost of debt")
            if industry_data and 'avg_cost_of_debt' in industry_data:
                cost_of_debt = industry_data['avg_cost_of_debt']
            else:
                cost_of_debt = risk_free_rate + 0.02  # Default premium over risk-free rate
        
        # Tax Rate calculation with additional methods
        tax_rate = None
        
        # Method 1: Calculate from income statements directly
        if income_statement is not None and not (hasattr(income_statement, 'empty') and income_statement.empty):
            try:
                if all(item in income_statement.index for item in ['Income Before Tax', 'Income Tax Expense']):
                    income_before_tax = income_statement.loc['Income Before Tax'].iloc[0]
                    income_tax_expense = income_statement.loc['Income Tax Expense'].iloc[0]
                    
                    if (income_before_tax > 0 and income_tax_expense > 0 and 
                        not pd.isna(income_before_tax) and not np.isnan(income_before_tax) and
                        not pd.isna(income_tax_expense) and not np.isnan(income_tax_expense)):
                        calculated_tax_rate = income_tax_expense / income_before_tax
                        # Validate the tax rate is reasonable
                        if 0.1 <= calculated_tax_rate <= 0.4:
                            tax_rate = calculated_tax_rate
            except Exception as e:
                print(f"Error calculating tax rate from income statement: {e}")
        
        # Method 2: Calculate from financials if income statement failed
        if tax_rate is None and financials is not None and not financials.empty:
            try:
                if all(item in financials.index for item in ['Income Before Tax', 'Income Tax Expense']):
                    income_before_tax = financials.loc['Income Before Tax'].iloc[0]
                    income_tax_expense = financials.loc['Income Tax Expense'].iloc[0]
                    
                    if (income_before_tax > 0 and income_tax_expense > 0 and 
                        not pd.isna(income_before_tax) and not np.isnan(income_before_tax) and
                        not pd.isna(income_tax_expense) and not np.isnan(income_tax_expense)):
                        calculated_tax_rate = income_tax_expense / income_before_tax
                        # Validate the tax rate is reasonable
                        if 0.1 <= calculated_tax_rate <= 0.4:
                            tax_rate = calculated_tax_rate
            except Exception as e:
                print(f"Error calculating tax rate from financials: {e}")
        
        # Method 3: Use effective tax rate from company info
        if tax_rate is None:
            try:
                if 'effectiveTaxRate' in stock.info:
                    effective_tax_rate = stock.info.get('effectiveTaxRate')
                    if effective_tax_rate and 0.1 <= effective_tax_rate <= 0.4:
                        tax_rate = effective_tax_rate
            except Exception as e:
                print(f"Error getting effective tax rate: {e}")
                
        # Method 4: Calculate average from historical data
        if tax_rate is None:
            try:
                historical_tax_rates = []
                
                # Try from income statement
                if (income_statement is not None and not (hasattr(income_statement, 'empty') and income_statement.empty) and
                    'Income Before Tax' in income_statement.index and 'Income Tax Expense' in income_statement.index):
                    # Calculate tax rates for all available periods
                    income_before_tax = income_statement.loc['Income Before Tax']
                    income_tax_expense = income_statement.loc['Income Tax Expense']
                    
                    for i in range(len(income_before_tax)):
                        if (i < len(income_tax_expense) and income_before_tax.iloc[i] > 0 and 
                            not pd.isna(income_before_tax.iloc[i]) and not np.isnan(income_before_tax.iloc[i]) and
                            not pd.isna(income_tax_expense.iloc[i]) and not np.isnan(income_tax_expense.iloc[i])):
                            rate = income_tax_expense.iloc[i] / income_before_tax.iloc[i]
                            if 0.1 <= rate <= 0.4:  # Validate the rate
                                historical_tax_rates.append(rate)
                
                # Try from financials
                if not historical_tax_rates and financials is not None and not financials.empty:
                    if 'Income Before Tax' in financials.index and 'Income Tax Expense' in financials.index:
                        income_before_tax = financials.loc['Income Before Tax']
                        income_tax_expense = financials.loc['Income Tax Expense']
                        
                        for i in range(len(income_before_tax)):
                            if (i < len(income_tax_expense) and income_before_tax.iloc[i] > 0 and 
                                not pd.isna(income_before_tax.iloc[i]) and not np.isnan(income_before_tax.iloc[i]) and
                                not pd.isna(income_tax_expense.iloc[i]) and not np.isnan(income_tax_expense.iloc[i])):
                                rate = income_tax_expense.iloc[i] / income_before_tax.iloc[i]
                                if 0.1 <= rate <= 0.4:  # Validate the rate
                                    historical_tax_rates.append(rate)
                
                if historical_tax_rates:
                    tax_rate = sum(historical_tax_rates) / len(historical_tax_rates)
            except Exception as e:
                print(f"Error calculating average tax rate: {e}")
        
        # NEW: Get country-specific tax rate
        if tax_rate is None:
            try:
                country = stock.info.get('country')
                if country:
                    country_tax_rates = {
                        'United States': 0.21,
                        'US': 0.21,
                        'USA': 0.21,
                        'United Kingdom': 0.19,
                        'UK': 0.19,
                        'Germany': 0.30,
                        'France': 0.28,
                        'Japan': 0.30,
                        'China': 0.25,
                        'Canada': 0.26,
                        'Ireland': 0.125,
                        'Singapore': 0.17,
                        # Add more countries as needed
                    }
                    if country in country_tax_rates:
                        tax_rate = country_tax_rates[country]
            except Exception as e:
                print(f"Error getting country-specific tax rate: {e}")
        
        # Fallback to standard corporate tax rate
        if tax_rate is None or pd.isna(tax_rate) or np.isnan(tax_rate):
            print("Using standard corporate tax rate")
            tax_rate = 0.21  # US corporate tax rate
        
        # After-tax Cost of Debt
        after_tax_cost_of_debt = cost_of_debt * (1 - tax_rate)
        
        # Cost of Equity using CAPM
        # Use fetched risk-free rate or default to current 10-year Treasury yield
        market_risk_premium = 0.05  # Historical equity risk premium
        if industry_data and 'market_risk_premium' in industry_data:
            market_risk_premium = industry_data['market_risk_premium']
        
        # Get beta with validation and multiple methods
        beta = None
        try:
            beta = stock.info.get('beta')
            if pd.isna(beta) or np.isnan(beta):
                beta = None
        except Exception as e:
            print(f"Error getting beta from stock info: {e}")
        
        # NEW: Get beta from Damodaran dataset if available
        if (beta is None or beta < 0.2 or beta > 3.0) and industry_data and 'beta' in industry_data:
            print("Using industry beta from Damodaran data")
            beta = industry_data['beta']
        
        # Validate beta or use alternative methods
        if beta is None or beta < 0.2 or beta > 3.0:
            print("Beta missing or unreasonable, estimating based on sector")
            try:
                # Method 1: Try to get sector from info
                sector = None
                try:
                    sector = stock.info.get('sector')
                except:
                    pass
                
                # Method 2: Try to get industry if sector failed
                if not sector:
                    try:
                        industry = stock.info.get('industry')
                        # Map industry to sector
                        industry_to_sector = {
                            'Internet Content': 'Technology',
                            'Software': 'Technology',
                            'Consumer Electronics': 'Technology',
                            'Computer Hardware': 'Technology',
                            'Online Retail': 'Consumer Cyclical',
                            'Auto Manufacturers': 'Consumer Cyclical',
                            'Internet Retail': 'Consumer Cyclical',
                            'E-Commerce': 'Consumer Cyclical',
                            'Semiconductors': 'Technology',
                            'Software—Application': 'Technology',
                            'Telecom Services': 'Communication Services',
                            'Telecom Equipment': 'Communication Services',
                            'Entertainment': 'Communication Services',
                            'Banking': 'Financial Services',
                            'Insurance': 'Financial Services',
                            'Asset Management': 'Financial Services',
                            'Biotechnology': 'Healthcare',
                            'Pharmaceutical': 'Healthcare',
                            'Medical Devices': 'Healthcare',
                            'Aerospace': 'Industrials',
                            'Defense': 'Industrials',
                            'Transportation': 'Industrials',
                            'Oil & Gas': 'Energy',
                            'Oil & Gas E&P': 'Energy',
                            'Oil & Gas Services': 'Energy',
                            'Retail': 'Consumer Cyclical',
                            'Restaurants': 'Consumer Cyclical',
                            'Utilities': 'Utilities',
                            'Electric Utilities': 'Utilities',
                            'Real Estate': 'Real Estate',
                            'REIT': 'Real Estate',
                        }
                        sector = industry_to_sector.get(industry)
                    except:
                        pass
                
                # Approximate beta by sector with updated values based on 2024 market conditions
                sector_betas = {
                    'Technology': 1.25,
                    'Financial Services': 1.15,
                    'Healthcare': 0.85,
                    'Consumer Cyclical': 1.35,
                    'Communication Services': 1.05,
                    'Industrials': 1.10,
                    'Consumer Defensive': 0.65,
                    'Energy': 1.25,
                    'Basic Materials': 1.15,
                    'Real Estate': 0.85,
                    'Utilities': 0.45
                }
                
                if sector and sector in sector_betas:
                    beta = sector_betas[sector]
                else:
                    # Method 3: Estimate based on volatility relative to market
                    try:
                        # Get stock price history
                        stock_history = stock.history(period="2y")  # Increased to 2 years for more data
                        
                        # Get market index (S&P 500) history
                        market = yf.Ticker("^GSPC")
                        market_history = market.history(period="2y")
                        
                        # Calculate returns
                        stock_returns = stock_history['Close'].pct_change().dropna()
                        market_returns = market_history['Close'].pct_change().dropna()
                        
                        # Make sure they have the same length
                        min_len = min(len(stock_returns), len(market_returns))
                        if min_len > 30:  # Ensure we have enough data points
                            # Align dates
                            stock_returns = stock_returns[-min_len:]
                            market_returns = market_returns[-min_len:]
                            
                            # Calculate covariance and variance
                            covariance = np.cov(stock_returns, market_returns)[0, 1]
                            market_variance = np.var(market_returns)
                            
                            # Calculate beta
                            calculated_beta = covariance / market_variance
                            
                            # Validate beta is reasonable
                            if 0.2 <= calculated_beta <= 3.0:
                                beta = calculated_beta
                    except Exception as e:
                        print(f"Error calculating beta from historical data: {e}")
            except Exception as e:
                print(f"Error estimating beta: {e}")
                
            # Fallback if all methods fail
            if beta is None:
                beta = 1.0
        
        # Calculate Cost of Equity
        cost_of_equity = risk_free_rate + beta * market_risk_premium
        
        # WACC Calculation
        wacc = (weight_debt * after_tax_cost_of_debt) + (weight_equity * cost_of_equity)
        
        # Validate final WACC
        if np.isnan(wacc) or pd.isna(wacc) or not (0.05 <= wacc <= 0.20):
            print(f"WACC calculation resulted in unusual value: {wacc}, adjusting...")
            # Use sector as a guide for realistic WACC
            try:
                sector = stock.info.get('sector')
                if sector:
                    # Sector-specific baseline WACC values updated for 2024
                    sector_base_wacc = {
                        'Technology': 0.095,
                        'Financial Services': 0.085,
                        'Healthcare': 0.08,
                        'Consumer Cyclical': 0.09,
                        'Communication Services': 0.085,
                        'Industrials': 0.09,
                        'Consumer Defensive': 0.075,
                        'Energy': 0.10,
                        'Basic Materials': 0.09,
                        'Real Estate': 0.08,
                        'Utilities': 0.07
                    }
                    base_wacc = sector_base_wacc.get(sector, 0.09)
                    # Adjust based on beta if available
                    if beta and not np.isnan(beta) and not pd.isna(beta):
                        wacc = base_wacc + (beta - 1) * 0.01
                    else:
                        wacc = base_wacc
                else:
                    wacc = 0.09
            except:
                wacc = 0.09
            
            # Ensure WACC is within reasonable bounds
            wacc = min(max(wacc, 0.05), 0.20)
        
        return {
            'wacc': wacc,
            'cost_of_equity': cost_of_equity,
            'after_tax_cost_of_debt': after_tax_cost_of_debt,
            'weight_debt': weight_debt,
            'weight_equity': weight_equity,
            'beta': beta,
            'tax_rate': tax_rate,
            'total_debt': total_debt,
            'market_cap': market_cap
        }
        
    except Exception as e:
        print(f"Error calculating WACC: {e}")
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}")
        return default_wacc_values(ticker)


#------------ Perhaps see about making the functions more detailed or use multiple sources ----#

def get_fred_corporate_debt(ticker):
    """
    Fetch corporate debt data from alternative sources.
    
    Args:
        ticker (str): Stock ticker symbol
    
    Returns:
        float: Total corporate debt or 0 if not found
    """
    try:
        # Use yFinance as primary source
        stock = yf.Ticker(ticker)
        
        # Try multiple fields for total debt
        debt_fields = [
            'Total Debt', 
            'totalDebt', 
            'longTermDebt', 
            'Total Current Liabilities', 
            'Total Non-Current Liabilities'
        ]
        
        for field in debt_fields:
            try:
                debt = stock.info.get(field, 0)
                if debt and not pd.isna(debt) and not np.isnan(debt) and debt > 0:
                    return float(debt)
            except:
                continue
        
        # Fallback to balance sheet
        try:
            balance_sheet = stock.balance_sheet
            if not balance_sheet.empty:
                debt_columns = [
                    'Total Debt', 
                    'Long Term Debt', 
                    'Short Long Term Debt', 
                    'Current Debt'
                ]
                for col in debt_columns:
                    if col in balance_sheet.index:
                        debt = balance_sheet.loc[col].iloc[0]
                        if not pd.isna(debt) and not np.isnan(debt) and debt > 0:
                            return float(debt)
        except:
            pass
        
        return 0
    except Exception as e:
        print(f"Error fetching corporate debt for {ticker}: {e}")
        return 0

def get_damodaran_industry_data(ticker):
    """
    Fetch industry-specific data from Damodaran's publicly available datasets.
    
    Args:
        ticker (str): Stock ticker symbol
    
    Returns:
        dict: Industry-specific financial metrics
    """
    try:
        # Use yFinance to get industry
        stock = yf.Ticker(ticker)
        industry = stock.info.get('industry', '').lower()
        sector = stock.info.get('sector', '').lower()
        
        # Damodaran-like industry default values (as of 2024)
        industry_data = {
            # Default values for common industries
            'technology': {
                'beta': 1.25,
                'market_risk_premium': 0.05,
                'default_spread': 0.02,
                'avg_cost_of_debt': 0.045
            },
            'financial services': {
                'beta': 1.15,
                'market_risk_premium': 0.048,
                'default_spread': 0.015,
                'avg_cost_of_debt': 0.04
            },
            'healthcare': {
                'beta': 0.85,
                'market_risk_premium': 0.052,
                'default_spread': 0.025,
                'avg_cost_of_debt': 0.05
            },
            'consumer cyclical': {
                'beta': 1.35,
                'market_risk_premium': 0.055,
                'default_spread': 0.03,
                'avg_cost_of_debt': 0.055
            },
            # Add more industries as needed
            'default': {
                'beta': 1.0,
                'market_risk_premium': 0.05,
                'default_spread': 0.025,
                'avg_cost_of_debt': 0.045
            }
        }
        
        # Match industry or sector to data
        for key, data in industry_data.items():
            if key in industry or key in sector:
                return data
        
        return industry_data['default']
    except Exception as e:
        print(f"Error fetching Damodaran industry data for {ticker}: {e}")
        return {
            'beta': 1.0,
            'market_risk_premium': 0.05,
            'default_spread': 0.025,
            'avg_cost_of_debt': 0.045
        }

def get_market_cap_from_alternative_source(ticker):
    """
    Fetch market cap from alternative sources.
    
    Args:
        ticker (str): Stock ticker symbol
    
    Returns:
        float: Market capitalization or 0 if not found
    """
    try:
        # Use yFinance as primary source
        stock = yf.Ticker(ticker)
        
        # Try multiple methods to get market cap
        market_cap_methods = [
            stock.info.get('marketCap'),
            stock.info.get('marketCapitalization'),
            stock.info.get('enterpriseValue')
        ]
        
        for method in market_cap_methods:
            if method and not pd.isna(method) and not np.isnan(method) and method > 0:
                return float(method)
        
        # Try calculating from shares and price
        try:
            shares = stock.info.get('sharesOutstanding')
            price = stock.history(period="1d")["Close"].iloc[-1]
            if shares and price:
                return float(shares * price)
        except:
            pass
        
        return 0
    except Exception as e:
        print(f"Error fetching market cap for {ticker}: {e}")
        return 0

def get_corporate_bond_yield(ticker):
    """
    Fetch corporate bond yield from alternative sources.
    
    Args:
        ticker (str): Stock ticker symbol
    
    Returns:
        float: Corporate bond yield or None if not found
    """
    try:
        # Use yFinance to get company info
        stock = yf.Ticker(ticker)
        
        # Try to get credit rating or other relevant information
        try:
            credit_rating = stock.info.get('creditRating', '').upper()
        except:
            credit_rating = ''
        
        # Baseline corporate bond yields based on credit ratings (as of 2024)
        rating_yields = {
            'AAA': 0.04,
            'AA+': 0.045,
            'AA': 0.047,
            'AA-': 0.05,
            'A+': 0.055,
            'A': 0.06,
            'A-': 0.065,
            'BBB+': 0.07,
            'BBB': 0.075,
            'BBB-': 0.08,
            'BB+': 0.09,
            'BB': 0.10,
            'B+': 0.11,
            'B': 0.12,
            'CCC': 0.14
        }
        
        # If credit rating is found, use corresponding yield
        if credit_rating in rating_yields:
            return rating_yields[credit_rating]
        
        # Fallback: use industry and size to estimate yield
        try:
            industry = stock.info.get('industry', '').lower()
            market_cap = stock.info.get('marketCap', 0)
            
            # Baseline yield
            base_yield = 0.05
            
            # Adjust for industry risk
            industry_risk = {
                'technology': 0.01,
                'financial services': -0.005,
                'healthcare': 0.005,
                'consumer cyclical': 0.015,
                'energy': 0.02,
                'utilities': -0.01
            }
            
            for key, risk_adjustment in industry_risk.items():
                if key in industry:
                    base_yield += risk_adjustment
                    break
            
            # Adjust for company size
            if market_cap > 200e9:  # Large cap
                base_yield -= 0.01
            elif market_cap < 2e9:  # Small cap
                base_yield += 0.02
            
            return max(0.04, min(base_yield, 0.15))
        except:
            # Very conservative default
            return 0.06
    except Exception as e:
        print(f"Error fetching corporate bond yield for {ticker}: {e}")
        return None

#-------------------------- This function requires a helper function to get yield data ---------#

def get_treasury_yield():
    """
    Get current 10-year Treasury yield from multiple reliable sources.
    
    Returns:
        float: Current 10-year Treasury yield, or None if unable to retrieve
    """
    # Method 1: FRED API (Federal Reserve Economic Data)
    try:
        treasury_data = pdr.get_data_fred('DGS10')
        if not treasury_data.empty:
            latest_yield = treasury_data.iloc[-1, 0] / 100  # Convert percentage to decimal
            if 0.01 <= latest_yield <= 0.10:  # Sanity check
                return latest_yield
    except Exception as e:
        print(f"FRED API Treasury yield retrieval failed: {e}")
    
    # Method 2: Yahoo Finance Treasury Yield
    try:
        import yfinance as yf
        treasury_ticker = yf.Ticker('^TNX')  # 10-year Treasury Yield index
        treasury_info = treasury_ticker.info
        
        if 'previousClose' in treasury_info:
            yield_value = treasury_info['previousClose'] / 100  # Convert percentage to decimal
            if 0.01 <= yield_value <= 0.10:  # Sanity check
                return yield_value
    except Exception as e:
        print(f"Yahoo Finance Treasury yield retrieval failed: {e}")
    
    # Method 3: US Treasury Direct API (if available)
    try:
        import requests
        from datetime import datetime, timedelta
        
        # Get today's date and format
        today = datetime.now().strftime('%m/%d/%Y')
        
        # Treasury Direct API endpoint
        url = f"https://www.treasury.gov/resource-center/data-chart-center/interest-rates/Pages/TextView.aspx?data=yield"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            # Parsing logic would depend on the exact API response format
            # This is a placeholder and might need adjustment based on actual API structure
            import re
            
            # Look for 10-year yield pattern
            match = re.search(r'10 Year\s*(\d+\.\d+)', response.text)
            if match:
                yield_value = float(match.group(1)) / 100  # Convert to decimal
                if 0.01 <= yield_value <= 0.10:  # Sanity check
                    return yield_value
    except Exception as e:
        print(f"US Treasury Direct API retrieval failed: {e}")
    
    # Method 4: Hardcoded recent historical average as fallback
    try:
        current_month = datetime.now().month
        
        # Rough approximations based on recent historical trends
        # These values should be periodically updated to reflect current market conditions
        yearly_yields = {
            1: 0.0425,   # January
            2: 0.0435,   # February 
            3: 0.0445,   # March
            4: 0.0455,   # April
            5: 0.0465,   # May
            6: 0.0475,   # June
            7: 0.0485,   # July
            8: 0.0475,   # August
            9: 0.0465,   # September
            10: 0.0455,  # October
            11: 0.0445,  # November
            12: 0.0435   # December
        }
        
        # Use month-specific yield, or default to a standard value
        return yearly_yields.get(current_month, 0.042)
    
    except Exception as e:
        print(f"Fallback yield calculation failed: {e}")
    
    # Ultimate fallback
    print("Warning: Unable to retrieve Treasury yield. Using standard long-term average.")
    return 0.042  # Long-term historical average

#--- Default values for wacc calculation, see about making them more detailed later ---#

def default_wacc_values(ticker, industry_data=None):
    """
    Provide default WACC values when detailed calculation is not possible.
    
    Args:
        ticker (str): Stock ticker symbol
        industry_data (dict, optional): Industry-specific data if available
    
    Returns:
        dict: Default WACC and related values
    """
    # Base values from current market conditions (as of 2024)
    default_return = {
        'wacc': 0.09,  # 9% default WACC
        'cost_of_equity': 0.10,  # 10% estimated cost of equity
        'after_tax_cost_of_debt': 0.04,  # 4% after-tax cost of debt
        'weight_debt': 0.3,  # 30% debt
        'weight_equity': 0.7,  # 70% equity
        'beta': 1.0,  # Market beta
        'tax_rate': 0.21,  # US corporate tax rate
        'total_debt': 0,
        'market_cap': 0
    }
    
    # If industry data is provided, adjust defaults
    if industry_data:
        if 'avg_wacc' in industry_data:
            default_return['wacc'] = industry_data['avg_wacc']
        if 'beta' in industry_data:
            default_return['beta'] = industry_data['beta']
        if 'market_risk_premium' in industry_data:
            # Adjust cost of equity based on industry risk premium
            risk_free_rate = 0.042  # Current 10-year Treasury yield
            default_return['cost_of_equity'] = risk_free_rate + default_return['beta'] * industry_data['market_risk_premium']
    
    print(f"Using default WACC values for {ticker}")
    return default_return

####################################################################################################################################################
################################# Growth Rate Calculation ##########################################################################################
####################################################################################################################################################

def calculate_growth_rates(ticker, cik, financial_data=None, years_historical=5):
    """
    Calculate growth rates with improved data validation and regression analysis.
    
    Args:
        ticker (str): Stock ticker symbol
        cik (str): Company's CIK number
        financial_data (dict): Financial data if already fetched
        years_historical (int): Number of historical years to analyze
    
    Returns:
        dict: Growth rates and components
    """
    print(f"Calculating growth rates for {ticker}...")
    
    try:
        # Initialize with default values in case of failure
        default_values = default_growth_values(ticker, True)
        
        # Try to get stock data from yfinance or financial_data
        if financial_data and 'stock' in financial_data:
            stock = financial_data['stock']
        else:
            try:
                stock = yf.Ticker(ticker)
            except Exception as e:
                print(f"Error fetching stock data: {e}")
                return default_values
        
        # Get cash flow data with multiple fallback methods
        cash_flow_stmt = get_cash_flow_data(stock, financial_data)
        
        # Get revenue data with multiple fallback methods
        revenues = get_revenue_data(stock)
        
        # If we still don't have enough data, use defaults
        if (cash_flow_stmt is None or cash_flow_stmt.empty or len(cash_flow_stmt.columns) < 2 or
            revenues is None or len(revenues) < 2):
            print("Insufficient financial data for growth calculation")
            return default_values
        
        # Calculate FCF and growth rates with robust error handling
        historical_fcf, fcf_growth_rates, avg_historical_growth = calculate_fcf_growth(cash_flow_stmt)
        
        # Calculate revenue growth rates with robust error handling
        revenue_growth_rates, avg_revenue_growth = calculate_revenue_growth(revenues)
        
        # Get analyst estimates from multiple sources with better validation
        analyst_growth_estimate = get_improved_analyst_estimates(stock, ticker)
        
        # Perform regression analysis for growth projection with error handling
        regression_growth_rate = calculate_robust_regression_growth(historical_fcf)
        
        # Determine company size and apply appropriate growth caps - more nuanced approach
        market_cap, company_size, max_growth, industry_category = determine_company_size_and_industry(stock, ticker)
        
        # Combine different growth estimates with weighted approach
        valid_estimates = combine_growth_estimates(
            avg_historical_growth, fcf_growth_rates,
            avg_revenue_growth, revenue_growth_rates,
            analyst_growth_estimate, regression_growth_rate,
            industry_category
        )
        
        # Calculate final weighted growth rate with intelligent capping
        weighted_growth = calculate_intelligent_weighted_growth(
            valid_estimates, 
            max_growth, 
            market_cap, 
            company_size,
            ticker,
            industry_category
        )
        
        # Return results in the expected format
        return {
            'short_term_growth': weighted_growth,
            'historical_fcf_growth': avg_historical_growth,
            'revenue_growth': avg_revenue_growth,
            'analyst_estimate': analyst_growth_estimate,
            'regression_growth': regression_growth_rate,
            'company_size': company_size,
            'max_growth_cap': max_growth,
            'growth_components': {
                'fcf_growth_rates': fcf_growth_rates,
                'revenue_growth_rates': revenue_growth_rates,
                'valid_estimates': valid_estimates
            }
        }
    except Exception as e:
        print(f"Error calculating growth rates: {e}")
        traceback.print_exc()  # Show detailed error information
        return default_growth_values(ticker)

def get_improved_analyst_estimates(stock, ticker):
    """
    Get analyst growth estimates from multiple sources with improved validation.
    
    Args:
        stock: yfinance Ticker object
        ticker: Stock ticker symbol for additional data sources
    
    Returns:
        float: Validated analyst growth estimate
    """
    analyst_estimates = []
    
    # Method 1: earningsGrowth from info
    try:
        growth = stock.info.get('earningsGrowth')
        if growth is not None and not np.isnan(growth) and 0 <= growth <= 1.0:
            analyst_estimates.append((growth, 0.4))  # Weight of 0.4
    except Exception as e:
        print(f"Error getting earningsGrowth: {e}")
    
    # Method 2: Use analyst target price vs current price
    try:
        target_price = stock.info.get('targetMeanPrice')
        current_price = stock.info.get('currentPrice', stock.info.get('regularMarketPrice'))
        
        if target_price and current_price and current_price > 0:
            # Calculate implied annual growth rate (assuming 1-year target)
            implied_growth = (target_price / current_price) - 1
            
            # Only use if reasonable
            if 0 <= implied_growth <= 0.5:
                analyst_estimates.append((implied_growth, 0.2))  # Weight of 0.2
    except Exception as e:
        print(f"Error calculating implied growth from target price: {e}")
    
    # Method 3: Use forward P/E vs. trailing P/E ratio
    try:
        forward_pe = stock.info.get('forwardPE')
        trailing_pe = stock.info.get('trailingPE')
        
        if forward_pe and trailing_pe and trailing_pe > 0 and forward_pe > 0:
            # Rough approximation based on PE ratios
            implied_growth = (trailing_pe / forward_pe) - 1
            
            # Only use if reasonable
            if 0 <= implied_growth <= 0.5:
                analyst_estimates.append((implied_growth, 0.2))  # Weight of 0.2
    except Exception as e:
        print(f"Error calculating growth from PE ratios: {e}")
    
    # Method 4: Use EPS growth data
    try:
        # Try quarterly first
        lt_growth = stock.info.get('earningsQuarterlyGrowth')
        if lt_growth is not None and not np.isnan(lt_growth) and -0.5 <= lt_growth <= 1.0:
            analyst_estimates.append((lt_growth, 0.2))  # Weight of 0.2
    except Exception as e:
        print(f"Error getting earnings quarterly growth: {e}")
    
    # Method 5: Use sector/industry average as fallback
    try:
        industry = stock.info.get('industry', '')
        sector = stock.info.get('sector', '')
        if industry or sector:
            industry_growth = get_industry_growth_rate(industry, sector)
            if industry_growth is not None:
                analyst_estimates.append((industry_growth, 0.1))  # Lower weight for industry average
    except Exception as e:
        print(f"Error getting industry growth: {e}")
    
    # Calculate weighted average of all valid estimates
    if analyst_estimates:
        total_weight = sum(weight for _, weight in analyst_estimates)
        if total_weight > 0:
            weighted_estimate = sum(estimate * weight for estimate, weight in analyst_estimates) / total_weight
            
            # Apply additional validation for high estimates
            if weighted_estimate > 0.3:
                print(f"Warning: Very high analyst growth estimate of {weighted_estimate:.2%} for {ticker}")
                # Cap extreme values more aggressively and apply discount
                weighted_estimate = min(weighted_estimate, 0.5) * 0.8
                
            return weighted_estimate
    
    # Default to a reasonable estimate based on market average if no data
    print(f"No valid analyst estimates found for {ticker}, using market average")
    return 0.07  # 7% as fallback (long-term market average)

def calculate_robust_regression_growth(historical_fcf):
    """
    Perform regression analysis for growth projection with improved error handling.
    
    Args:
        historical_fcf: Historical FCF Series
    
    Returns:
        float: Regression-based growth rate
    """
    regression_growth_rate = None
    
    if historical_fcf is not None and len(historical_fcf) >= 3:
        try:
            # Create a copy of the data to avoid modifying the original
            fcf_data = historical_fcf.copy()
            
            # Handle zeros and negative values
            min_positive = fcf_data[fcf_data > 0].min() if (fcf_data > 0).any() else 1
            small_value = min_positive * 0.1
            fcf_data[fcf_data <= 0] = small_value
            
            # Create array of years (0 = oldest)
            years = np.arange(len(fcf_data))
            
            # Log transform for exponential growth model
            log_fcf = np.log(fcf_data.values)
            
            # Linear regression on log values
            slope, intercept, r_value, p_value, std_err = stats.linregress(years, log_fcf)
            
            # Convert slope to growth rate
            regression_growth_rate = np.exp(slope) - 1
            
            # Validate regression results
            if r_value**2 < 0.3:  # Poor fit
                print(f"Regression has poor fit (R²={r_value**2:.2f}), adjusting reliability")
                # Downweight the regression result due to poor fit
                regression_growth_rate *= 0.7
            
            # Cap extreme growth rates
            regression_growth_rate = max(min(regression_growth_rate, 0.3), -0.2)
            
        except Exception as e:
            print(f"Error in regression calculation: {e}")
            # Try an alternative approach if the first one fails
            try:
                # Simple year-over-year growth rate calculation as fallback
                growth_rates = []
                for i in range(1, len(historical_fcf)):
                    current = max(historical_fcf.iloc[i-1], small_value)
                    previous = max(historical_fcf.iloc[i], small_value)
                    
                    growth_rate = (current / previous) - 1
                    growth_rates.append(growth_rate)
                
                if growth_rates:
                    # Trim extreme values for more stability
                    growth_rates = [g for g in growth_rates if -0.5 <= g <= 1.0]
                    if growth_rates:
                        regression_growth_rate = np.median(growth_rates)  # Median for robustness
            except Exception as inner_e:
                print(f"Alternative regression approach also failed: {inner_e}")
    
    return regression_growth_rate

def determine_company_size_and_industry(stock, ticker):
    """
    Determine company size, industry, and apply appropriate growth caps.
    
    Args:
        stock: yfinance Ticker object
        ticker: Stock ticker symbol
    
    Returns:
        tuple: (market_cap, company_size, max_growth, industry_category)
    """
    try:
        market_cap = stock.info.get('marketCap', 0)
        industry = stock.info.get('industry', '')
        sector = stock.info.get('sector', '')
        
        # Determine industry growth characteristics
        industry_lower = industry.lower() if industry else ''
        sector_lower = sector.lower() if sector else ''
        
        # Categorize industry for growth potential
        if any(keyword in industry_lower or keyword in sector_lower 
               for keyword in ['tech', 'software', 'semiconductor', 'internet', 'artificial intelligence', 'ai', 'cloud']):
            industry_category = 'high_growth'
        elif any(keyword in industry_lower or keyword in sector_lower 
                 for keyword in ['health', 'biotech', 'medical', 'pharmaceutical', 'comm', 'media', 'entertainment', 'consumer discretionary']):
            industry_category = 'medium_growth'
        elif any(keyword in industry_lower or keyword in sector_lower 
                 for keyword in ['financial', 'bank', 'insurance', 'industrial', 'manufacturing', 'material']):
            industry_category = 'cyclical'
        elif any(keyword in industry_lower or keyword in sector_lower 
                 for keyword in ['utility', 'energy', 'telecom', 'consumer staple', 'food', 'retail']):
            industry_category = 'stable'
        else:
            industry_category = 'average'
        
        # Determine size-based growth caps but adjust based on industry characteristics
        if market_cap > 1e12:  # Over $1 trillion
            company_size = "Mega Cap"
            base_growth_cap = 0.10  # 10% base cap for mega caps
        elif market_cap > 1e11:  # Over $100 billion
            company_size = "Large Cap"
            base_growth_cap = 0.12  # 12% base cap for large caps
        elif market_cap > 1e10:  # Over $10 billion
            company_size = "Mid Cap"
            base_growth_cap = 0.15  # 15% base cap for mid caps
        elif market_cap > 1e9:  # Over $1 billion
            company_size = "Small Cap"
            base_growth_cap = 0.20  # 20% base cap for small caps
        else:
            company_size = "Micro Cap"
            base_growth_cap = 0.25  # 25% base cap for micro caps
        
        # Adjust growth cap based on industry
        industry_adjustments = {
            'high_growth': 0.05,     # +5% for high growth industries
            'medium_growth': 0.03,   # +3% for medium growth industries
            'cyclical': 0.01,        # +1% for cyclical industries
            'stable': -0.02,         # -2% for stable industries
            'average': 0             # No adjustment for average industries
        }
        
        # Apply industry adjustment to base growth cap
        max_growth = base_growth_cap + industry_adjustments.get(industry_category, 0)
        
        # Special case handling for very large companies in high growth sectors (like major tech)
        if market_cap > 5e11 and industry_category == 'high_growth':
            # Check recent growth performance to justify higher cap
            try:
                # Get historical financials for validation
                income = stock.income_stmt
                if income is not None and not income.empty and 'Total Revenue' in income.index:
                    revenues = income.loc['Total Revenue']
                    
                    # If we have at least 3 years of data, calculate CAGR
                    if len(revenues) >= 3:
                        oldest = revenues.iloc[-1]
                        newest = revenues.iloc[0]
                        years = len(revenues) - 1
                        
                        if oldest > 0:
                            revenue_cagr = (newest / oldest) ** (1 / years) - 1
                            
                            # If historical CAGR justifies higher growth cap, adjust accordingly
                            if revenue_cagr > max_growth:
                                max_growth = min(revenue_cagr * 0.9, max_growth + 0.05)  # Allow up to 5% increase
                                print(f"Adjusted growth cap for {ticker} based on historical performance: {max_growth:.2%}")
            except Exception as e:
                print(f"Error checking historical performance for cap adjustment: {e}")
        
        # Ensure reasonable bounds for growth cap
        max_growth = max(min(max_growth, 0.30), 0.05)  # Between 5% and 30%
        
        return market_cap, company_size, max_growth, industry_category
    
    except Exception as e:
        print(f"Error determining company size: {e}")
        # Default values
        return 0, "Unknown", 0.15, "average"

def combine_growth_estimates(avg_historical_growth, fcf_growth_rates, 
                            avg_revenue_growth, revenue_growth_rates,
                            analyst_growth_estimate, regression_growth_rate,
                            industry_category):
    """
    Combine different growth estimates with improved weighted approach.
    
    Args:
        Various growth metrics
        industry_category: Category of the industry
    
    Returns:
        dict: Valid growth estimates with weights
    """
    valid_estimates = {}
    
    # Determine weights based on industry category and data reliability
    # High growth industries rely more on forward-looking estimates
    # Stable industries rely more on historical performance
    industry_weight_adjustments = {
        'high_growth': {'historical_fcf': -0.05, 'revenue_growth': -0.05, 'analyst_estimate': 0.1, 'regression': 0},
        'medium_growth': {'historical_fcf': 0, 'revenue_growth': 0, 'analyst_estimate': 0.05, 'regression': -0.05},
        'cyclical': {'historical_fcf': 0.05, 'revenue_growth': 0.05, 'analyst_estimate': -0.05, 'regression': -0.05},
        'stable': {'historical_fcf': 0.1, 'revenue_growth': 0.05, 'analyst_estimate': -0.1, 'regression': -0.05},
        'average': {'historical_fcf': 0, 'revenue_growth': 0, 'analyst_estimate': 0, 'regression': 0}
    }
    
    # Base weights - will be adjusted by industry and data quality
    base_weights = {
        'historical_fcf': 0.35,
        'revenue_growth': 0.25,
        'analyst_estimate': 0.25,
        'regression': 0.15
    }
    
    # Adjust weights based on industry
    adjustments = industry_weight_adjustments.get(industry_category, industry_weight_adjustments['average'])
    
    # Add historical FCF growth if valid
    if avg_historical_growth is not None and -0.2 <= avg_historical_growth <= 0.5:
        reliability = 'High' if len(fcf_growth_rates) >= 4 else 'Medium' if len(fcf_growth_rates) >= 2 else 'Low'
        
        # Base weight adjusted by reliability and industry
        weight = base_weights['historical_fcf'] + adjustments['historical_fcf']
        if reliability == 'High':
            weight += 0.05
        elif reliability == 'Low':
            weight -= 0.1
        
        weight = max(min(weight, 0.5), 0.1)  # Constrain between 10% and 50%
        
        valid_estimates['historical_fcf'] = {
            'value': avg_historical_growth,
            'weight': weight,
            'reliability': reliability
        }
    
    # Add revenue growth if valid
    if avg_revenue_growth is not None and -0.2 <= avg_revenue_growth <= 0.5:
        reliability = 'High' if len(revenue_growth_rates) >= 4 else 'Medium' if len(revenue_growth_rates) >= 2 else 'Low'
        
        # Base weight adjusted by reliability and industry
        weight = base_weights['revenue_growth'] + adjustments['revenue_growth']
        if reliability == 'High':
            weight += 0.05
        elif reliability == 'Low':
            weight -= 0.1
        
        weight = max(min(weight, 0.5), 0.1)  # Constrain between 10% and 50%
        
        valid_estimates['revenue_growth'] = {
            'value': avg_revenue_growth,
            'weight': weight,
            'reliability': reliability
        }
    
    # Add analyst estimate if valid
    if analyst_growth_estimate is not None and 0 <= analyst_growth_estimate <= 0.5:
        # Adjust weight based on industry
        weight = base_weights['analyst_estimate'] + adjustments['analyst_estimate']
        weight = max(min(weight, 0.5), 0.1)  # Constrain between 10% and 50%
        
        valid_estimates['analyst_estimate'] = {
            'value': analyst_growth_estimate,
            'weight': weight,
            'reliability': 'Medium'  # Default reliability
        }
    
    # Add regression growth if valid
    if regression_growth_rate is not None and -0.2 <= regression_growth_rate <= 0.3:
        # Adjust weight based on industry
        weight = base_weights['regression'] + adjustments['regression']
        weight = max(min(weight, 0.5), 0.1)  # Constrain between 10% and 50%
        
        valid_estimates['regression'] = {
            'value': regression_growth_rate,
            'weight': weight,
            'reliability': 'Medium'  # Default reliability
        }
    
    return valid_estimates

def calculate_intelligent_weighted_growth(valid_estimates, max_growth, market_cap, company_size, ticker, industry_category):
    """
    Calculate final weighted growth rate with intelligent capping.
    
    Args:
        valid_estimates: Dict of valid growth estimates
        max_growth: Maximum allowed growth rate
        market_cap: Company market capitalization
        company_size: Size category of the company
        ticker: Stock ticker symbol
        industry_category: Industry growth category
    
    Returns:
        float: Intelligently weighted and capped growth rate
    """
    # Default to a conservative growth rate if no valid estimates
    if not valid_estimates:
        print(f"No valid growth estimates available for {ticker}, using default growth")
        return get_conservative_default_growth(company_size, industry_category)
    
    # Normalize weights
    total_weight = sum(item['weight'] for item in valid_estimates.values())
    weighted_growth = sum(item['value'] * (item['weight'] / total_weight) 
                    for item in valid_estimates.values())
    
    # Apply intelligent capping based on company characteristics
    # For very large cap companies, apply stricter caps due to size constraints
    if market_cap > 5e11:  # $500B+
        # For mega caps, consider law of large numbers
        if weighted_growth > max_growth:
            print(f"Growth rate {weighted_growth:.2%} exceeds cap for {company_size}, applying gradual reduction")
            
            # Apply gradual reduction rather than hard cap
            excess = weighted_growth - max_growth
            reduction_factor = 0.7  # Reduce excess by 70%
            
            adjusted_growth = max_growth + (excess * (1 - reduction_factor))
            print(f"Adjusted growth from {weighted_growth:.2%} to {adjusted_growth:.2%}")
            weighted_growth = adjusted_growth
    else:
        # For smaller companies, allow more flexibility in growth rates
        if weighted_growth > max_growth:
            # Check if we have strong evidence for higher growth
            strong_evidence = False
            
            # If analyst estimates and historical growth both suggest higher growth,
            # we may have strong evidence
            if ('analyst_estimate' in valid_estimates and 
                'historical_fcf' in valid_estimates and
                valid_estimates['analyst_estimate']['value'] > max_growth and
                valid_estimates['historical_fcf']['value'] > max_growth * 0.8):
                strong_evidence = True
            
            if strong_evidence:
                # Allow exceeding the cap by up to 20% if we have strong evidence
                cap_extension = max_growth * 0.2
                new_cap = max_growth + cap_extension
                
                if weighted_growth > new_cap:
                    print(f"Strong evidence for high growth, but {weighted_growth:.2%} still exceeds extended cap of {new_cap:.2%}")
                    weighted_growth = new_cap
                else:
                    print(f"Strong evidence for high growth, allowing {weighted_growth:.2%} above standard cap of {max_growth:.2%}")
            else:
                print(f"Growth rate {weighted_growth:.2%} exceeds cap for company size, using {max_growth:.2%}")
                weighted_growth = max_growth
    
    # Sanity check on final growth rate
    if weighted_growth < 0:
        print(f"Warning: Negative growth rate calculated: {weighted_growth:.2%}")
        # Use small positive growth instead of negative growth
        weighted_growth = max(0.01, weighted_growth + 0.03)
    
    # For high-profile tech companies, cross-check with market expectations
    if ticker in ['AMZN', 'GOOGL', 'AAPL', 'MSFT', 'META', 'TSLA'] and industry_category == 'high_growth':
        expected_ranges = {
            'AMZN': (0.10, 0.18),   # Amazon expected growth range
            'GOOGL': (0.08, 0.15),  # Google expected growth range
            'AAPL': (0.05, 0.12),   # Apple expected growth range
            'MSFT': (0.08, 0.15),   # Microsoft expected growth range
            'META': (0.08, 0.15),   # Meta expected growth range
            'TSLA': (0.15, 0.25)    # Tesla expected growth range
        }
        
        if ticker in expected_ranges:
            min_expected, max_expected = expected_ranges[ticker]
            
            if weighted_growth < min_expected:
                print(f"Calculated growth rate {weighted_growth:.2%} for {ticker} is below typical expectations, adjusting to {min_expected:.2%}")
                weighted_growth = min_expected
            elif weighted_growth > max_expected:
                print(f"Calculated growth rate {weighted_growth:.2%} for {ticker} is above typical expectations, adjusting to {max_expected:.2%}")
                weighted_growth = max_expected
    
    print(f"Final weighted growth rate for {ticker}: {weighted_growth:.2%}")
    return weighted_growth

def get_conservative_default_growth(company_size, industry_category):
    """
    Get conservative default growth based on company size and industry.
    
    Args:
        company_size: Size category of the company
        industry_category: Industry growth category
    
    Returns:
        float: Default growth rate
    """
    # Base growth rates by company size
    size_defaults = {
        "Mega Cap": 0.04,
        "Large Cap": 0.05,
        "Mid Cap": 0.06,
        "Small Cap": 0.08,
        "Micro Cap": 0.10,
        "Unknown": 0.05
    }
    
    # Industry adjustments
    industry_adjustments = {
        'high_growth': 0.04,
        'medium_growth': 0.02,
        'cyclical': 0.01,
        'stable': -0.01,
        'average': 0.00
    }
    
    # Get base rate by size
    base_rate = size_defaults.get(company_size, 0.05)
    
    # Apply industry adjustment
    adjustment = industry_adjustments.get(industry_category, 0.00)
    
    return base_rate + adjustment

def get_industry_growth_rate(industry, sector):
    """
    Get estimated growth rate for an industry or sector.
    This function would ideally connect to an external API or database.
    
    Args:
        industry: Industry name
        sector: Sector name
    
    Returns:
        float: Estimated industry growth rate
    """
    # This is a simplified version - in production you would use an API
    # or database to get up-to-date industry growth rates
    
    # Define some common industry/sector growth rates
    industry_rates = {
        # Technology
        'software': 0.15,
        'semiconductor': 0.12,
        'internet': 0.18,
        'information technology': 0.12,
        'technology': 0.12,
        
        # Healthcare
        'biotechnology': 0.14,
        'pharmaceuticals': 0.08,
        'healthcare': 0.07,
        'medical devices': 0.09,
        
        # Consumer
        'consumer discretionary': 0.06,
        'consumer staples': 0.04,
        'retail': 0.05,
        'e-commerce': 0.15,
        
        # Communications
        'communication services': 0.08,
        'media': 0.06,
        'telecommunications': 0.03,
        
        # Financial
        'financial services': 0.06,
        'banks': 0.04,
        'insurance': 0.05,
        'financials': 0.05,
        
        # Industrial
        'industrials': 0.05,
        'manufacturing': 0.04,
        'aerospace': 0.06,
        
        # Other
        'energy': 0.03,
        'utilities': 0.02,
        'real estate': 0.04,
        'materials': 0.04
    }
    
    # Try to match industry first
    if industry:
        industry_lower = industry.lower()
        for key, rate in industry_rates.items():
            if key in industry_lower:
                return rate
    
    # Fall back to sector if no industry match
    if sector:
        sector_lower = sector.lower()
        for key, rate in industry_rates.items():
            if key in sector_lower:
                return rate
    
    # Default if no match
    return 0.06  # 6% as a general default

def calculate_fcf_growth(cash_flow_stmt):
    """
    Calculate FCF and growth rates with improved error handling.
    
    Args:
        cash_flow_stmt: Cash flow statement DataFrame
    
    Returns:
        tuple: (historical_fcf, fcf_growth_rates, avg_historical_growth)
    """
    historical_fcf = None
    fcf_growth_rates = []
    avg_historical_growth = None
    
    # Try multiple approaches to get FCF
    fcf_row_names = [
        'Free Cash Flow',
        'freeCashFlow',
        'Free Cash Flow to Firm',
        'FCF'
    ]
    
    # Diiferentiate based on industry whether to add precidence to historical or compaititve cash flows (FCF or FCFE)

    # Try to get FCF directly using various possible row names
    for row_name in fcf_row_names:
        if row_name in cash_flow_stmt.index:
            historical_fcf = cash_flow_stmt.loc[row_name]
            break
    
    # If not found directly, calculate from components
    if historical_fcf is None:
        component_pairs = [
            ('Operating Cash Flow', 'Capital Expenditure'),
            ('Cash Flow from Operations', 'Capital Expenditures'),
            ('Cash Flow from Operating Activities', 'Capital Expenditures'),
            ('Net Cash Provided by Operating Activities', 'Purchase of Property and Equipment'),
            ('netCashProvidedByOperatingActivities', 'capitalExpenditures')
        ]
        
        for op_flow_name, capex_name in component_pairs:
            if op_flow_name in cash_flow_stmt.index and capex_name in cash_flow_stmt.index:
                op_cash_flow = cash_flow_stmt.loc[op_flow_name]
                cap_ex = cash_flow_stmt.loc[capex_name]
                historical_fcf = op_cash_flow + cap_ex  # CapEx is typically negative
                break
    
    # If we have FCF data, calculate growth rates
    if historical_fcf is not None and len(historical_fcf) >= 2:
        # Sort by date (recent first)
        historical_fcf = historical_fcf.sort_index(ascending=False)
        
        # Calculate growth rates between years
        for i in range(1, len(historical_fcf)):
            current_fcf = historical_fcf.iloc[i-1]
            previous_fcf = historical_fcf.iloc[i]
            
            # Skip if previous FCF is zero or negative
            if previous_fcf <= 0:
                continue
                
            growth_rate = (current_fcf / previous_fcf) - 1
            
            # Only include reasonable growth rates
            if -0.5 <= growth_rate <= 1.0:
                fcf_growth_rates.append(growth_rate)
        
        # Calculate average growth rate
        if fcf_growth_rates:
            # Use median for robustness against outliers
            avg_historical_growth = np.median(fcf_growth_rates)
            
            # Apply sanity check to average growth
            if avg_historical_growth > 0.3:
                print(f"Warning: Very high historical FCF growth rate: {avg_historical_growth:.2%}")
                # Discount extremely high growth rates
                avg_historical_growth = 0.3 - (0.1 * (avg_historical_growth - 0.3) / 0.2)
            elif avg_historical_growth < -0.2:
                print(f"Warning: Very negative historical FCF growth rate: {avg_historical_growth:.2%}")
                # Limit negative growth
                avg_historical_growth = -0.1
    
    return historical_fcf, fcf_growth_rates, avg_historical_growth

def calculate_revenue_growth(revenues):
    """
    Calculate revenue growth rates with robust error handling.
    
    Args:
        revenues: Revenue Series
    
    Returns:
        tuple: (revenue_growth_rates, avg_revenue_growth)
    """
    revenue_growth_rates = []
    avg_revenue_growth = None
    
    if revenues is not None and len(revenues) >= 2:
        # Sort revenues (recent first)
        if hasattr(revenues, 'sort_index'):
            revenues = revenues.sort_index(ascending=False)
        
        # Calculate year-over-year growth rates
        for i in range(1, len(revenues)):
            current_revenue = revenues.iloc[i-1] if hasattr(revenues, 'iloc') else revenues[i-1]
            previous_revenue = revenues.iloc[i] if hasattr(revenues, 'iloc') else revenues[i]
            
            # Skip if previous revenue is zero or negative
            if previous_revenue <= 0:
                continue
                
            growth_rate = (current_revenue / previous_revenue) - 1
            
            # Only include reasonable growth rates
            if -0.5 <= growth_rate <= 1.0:
                revenue_growth_rates.append(growth_rate)
        
        # Calculate average growth rate
        if revenue_growth_rates:
            # Use median for robustness against outliers
            avg_revenue_growth = np.median(revenue_growth_rates)
            
            # Apply sanity check to average growth
            if avg_revenue_growth > 0.3:
                print(f"Warning: Very high historical revenue growth rate: {avg_revenue_growth:.2%}")
                # Discount extremely high growth rates
                avg_revenue_growth = 0.3 - (0.1 * (avg_revenue_growth - 0.3) / 0.2)
    
    return revenue_growth_rates, avg_revenue_growth

def get_cash_flow_data(stock, financial_data=None):
    """
    Get cash flow data with multiple fallback methods.
    
    Args:
        stock: yfinance Ticker object
        financial_data: Pre-fetched financial data
    
    Returns:
        DataFrame: Cash flow statement
    """
    cash_flow_stmt = None
    
    try:
        # Try getting from pre-fetched data
        if financial_data and 'cash_flow' in financial_data:
            cash_flow_stmt = financial_data['cash_flow']
            
        # Fall back to yfinance directly
        if cash_flow_stmt is None or cash_flow_stmt.empty:
            cash_flow_stmt = stock.cashflow
            
        # If still empty, try quarterly data
        if cash_flow_stmt is None or cash_flow_stmt.empty:
            cash_flow_stmt = stock.quarterly_cashflow
            
        # Additional fallback using alternative methods
        if cash_flow_stmt is None or cash_flow_stmt.empty:
            # Maybe try a different source like FMP API
            pass
            
    except Exception as e:
        print(f"Error retrieving cash flow data: {e}")
    
    return cash_flow_stmt

def get_revenue_data(stock):
    """
    Get revenue data with multiple fallback methods.
    
    Args:
        stock: yfinance Ticker object
    
    Returns:
        Series: Revenue data
    """
    revenues = None
    
    try:
        # Try income statement
        income = stock.income_stmt
        if income is not None and not income.empty and 'Total Revenue' in income.index:
            revenues = income.loc['Total Revenue']
        
        # If not found, try alternative names
        if revenues is None or len(revenues) < 2:
            revenue_row_names = [
                'Revenue', 
                'totalRevenue',
                'Total Revenue', 
                'Sales'
            ]
            
            for name in revenue_row_names:
                if name in income.index:
                    revenues = income.loc[name]
                    break
        
        # If still not found, try quarterly data
        if revenues is None or len(revenues) < 2:
            q_income = stock.quarterly_income_stmt
            if q_income is not None and not q_income.empty:
                for name in revenue_row_names:
                    if name in q_income.index:
                        revenues = q_income.loc[name]
                        break
    
    except Exception as e:
        print(f"Error retrieving revenue data: {e}")
    
    return revenues


########################################################
# Function to integrate with Estimize API if available #
########################################################
################## Come back to later ##################
########################################################

def get_estimize_consensus(ticker):
    """
    Get consensus estimates from Estimize API.
    Note: Requires Estimize API credentials.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        float: Consensus growth estimate or None
    """
    try:
        # This is a placeholder for Estimize API integration
        # In actual implementation, you would:
        # 1. Make API call to Estimize
        # 2. Parse response for EPS growth estimates
        # 3. Convert to revenue/earnings growth estimates
        
        # For now, return None to fall back to other methods
        return None
    except Exception as e:
        print(f"Error fetching Estimize data: {e}")
        return None

####################################################################
# Function to get Federal Reserve Economic Data for sector context #
####################################################################
################## Come back to later ##############################
####################################################################


def get_fred_sector_data(sector):
    """
    Get economic data for a sector from FRED API.
    Note: Requires fredapi library and API key.
    
    Args:
        sector: Company's sector
    
    Returns:
        float: Sector growth context or None
    """
    try:
        # This is a placeholder for FRED API integration
        # In actual implementation, you would:
        # 1. Map the sector to relevant FRED series IDs
        # 2. Fetch the data using fredapi
        # 3. Calculate growth rates or other relevant metrics
        
        # Sector growth mappings (simplified - would be dynamic in production)
        sector_growth = {
            'Technology': 0.10,
            'Healthcare': 0.08,
            'Consumer Discretionary': 0.06,
            'Consumer Staples': 0.04,
            'Financials': 0.05,
            'Industrials': 0.04,
            'Energy': 0.03,
            'Materials': 0.04,
            'Utilities': 0.02,
            'Communication Services': 0.07,
            'Real Estate': 0.04
        }
        
        return sector_growth.get(sector, None)
    except Exception as e:
        print(f"Error fetching FRED data: {e}")
        return None

def get_max_growth_cap(market_cap):
    """
    Determine the maximum sustainable growth rate cap based on market capitalization.
    
    Args:
        market_cap (float): Company's market capitalization
    
    Returns:
        float: Maximum sustainable growth rate cap
    """
    if market_cap <= 0:
        return 0.05  # Conservative default for invalid market cap
    
    # Logarithmic scaling to create smooth transitions between market cap ranges
    log_market_cap = np.log10(market_cap)
    
    if log_market_cap >= 12:  # $1 trillion+ (mega-cap)
        return 0.08  # Very conservative growth cap
    elif log_market_cap >= 11:  # $100 billion+ (large-cap)
        return 0.10
    elif log_market_cap >= 10:  # $10 billion+ (large-cap)
        return 0.12
    elif log_market_cap >= 9:  # $1 billion+ (mid-cap)
        return 0.15
    elif log_market_cap >= 8:  # $100 million+ (small-cap)
        return 0.20
    else:  # Micro-cap
        return 0.25
    
def get_company_size_category(market_cap):
    """
    Categorize company size based on market capitalization.
    
    Args:
        market_cap (float): Company's market capitalization
    
    Returns:
        str: Company size category
    """
    if market_cap <= 0:
        return 'Unknown'
    
    # Logarithmic scaling for market cap categories
    log_market_cap = np.log10(market_cap)
    
    if log_market_cap >= 12:
        return 'Mega-Cap'
    elif log_market_cap >= 11:
        return 'Large-Cap (Tier 1)'
    elif log_market_cap >= 10:
        return 'Large-Cap (Tier 2)'
    elif log_market_cap >= 9:
        return 'Mid-Cap'
    elif log_market_cap >= 8:
        return 'Small-Cap'
    elif log_market_cap >= 6:
        return 'Micro-Cap'
    else:
        return 'Nano-Cap'

def default_growth_values(ticker, get_industry_average=False):
    """
    Provide default growth values based on industry averages and company characteristics.
    
    Args:
        ticker (str): Stock ticker symbol
        get_industry_average (bool): Whether to attempt to get industry averages
    
    Returns:
        dict: Default growth values
    """
    print(f"Calculating default growth values for {ticker}...")
    
    # Start with a conservative default
    default_growth = 0.03
    market_cap = 0
    sector = ''
    industry = ''
    
    if get_industry_average:
        try:
            stock = yf.Ticker(ticker)
            
            # Get company characteristics
            market_cap = stock.info.get('marketCap', 0)
            sector = stock.info.get('sector', '')
            industry = stock.info.get('industry', '')
            
            # Financial metrics for adjustments
            pe_ratio = stock.info.get('trailingPE', None)
            forward_pe = stock.info.get('forwardPE', None)
            dividend_yield = stock.info.get('dividendYield', None)
            profit_margins = stock.info.get('profitMargins', None)
            roe = stock.info.get('returnOnEquity', None)
            beta = stock.info.get('beta', None)
            
            # Try to get industry average growth from external function
            industry_growth = get_industry_growth_rate(industry, sector)
            if industry_growth is not None:
                default_growth = industry_growth
            
            # Base growth rate by company size - logarithmic scale for smoother transitions
            if market_cap > 0:
                # Convert market cap to log scale (base 10)
                log_market_cap = np.log10(market_cap)
                
                # Adjust base growth rate based on company size (logarithmic scaling)
                if log_market_cap >= 12:  # $1 trillion+
                    size_growth = 0.04
                elif log_market_cap >= 11:  # $100 billion+
                    size_growth = 0.05
                elif log_market_cap >= 10:  # $10 billion+
                    size_growth = 0.06
                elif log_market_cap >= 9:  # $1 billion+
                    size_growth = 0.08
                elif log_market_cap >= 8:  # $100 million+
                    size_growth = 0.10
                else:
                    size_growth = 0.12
                
                # If no industry growth available, use size-based growth
                if industry_growth is None:
                    default_growth = size_growth
            
            # Sector-based adjustments
            growth_sectors = ['technology', 'information technology', 'communication services', 
                            'healthcare', 'consumer discretionary', 'software', 'internet', 'semiconductor']
            stable_sectors = ['utilities', 'consumer staples', 'energy', 'real estate']
            cyclical_sectors = ['industrials', 'materials', 'financials']
            
            sector_lower = (sector + ' ' + industry).lower()
            
            # Apply sector adjustments with adaptive weights based on company size
            sector_weight = min(0.3, 15 / (market_cap ** 0.1)) if market_cap > 0 else 0.2
            
            if any(s in sector_lower for s in growth_sectors):
                default_growth = default_growth * (1 - sector_weight) + (default_growth + 0.02) * sector_weight
            elif any(s in sector_lower for s in stable_sectors):
                default_growth = default_growth * (1 - sector_weight) + (default_growth - 0.01) * sector_weight
            elif any(s in sector_lower for s in cyclical_sectors):
                default_growth = default_growth * (1 - sector_weight) + (default_growth + 0.01) * sector_weight
            
            # Special case handling for well-known high-growth companies
            ticker_upper = ticker.upper()
            high_growth_tech = {'AMZN': 0.15, 'AAPL': 0.08, 'MSFT': 0.12, 'GOOGL': 0.10, 
                               'GOOG': 0.10, 'META': 0.12, 'NFLX': 0.15, 'TSLA': 0.20}
            
            if ticker_upper in high_growth_tech:
                high_growth_value = high_growth_tech[ticker_upper]
                # Blend with calculated growth (giving more weight to preset value)
                default_growth = default_growth * 0.3 + high_growth_value * 0.7
            
            # Financial metric adjustments
            adjustments = 0
            metrics_count = 0
            
            # PE ratio adjustment with more nuanced approach
            if pe_ratio and not np.isnan(pe_ratio) and pe_ratio > 0:
                # Log scale for smoother PE adjustment
                pe_adj = 0.01 * (np.log10(pe_ratio) - np.log10(20))
                adjustments += min(max(pe_adj, -0.02), 0.02)  # Cap between -2% and +2%
                metrics_count += 1
            
            # Forward PE vs Trailing PE comparison (growth indicator)
            if forward_pe and pe_ratio and not np.isnan(forward_pe) and not np.isnan(pe_ratio) and forward_pe > 0 and pe_ratio > 0:
                pe_ratio_ratio = pe_ratio / forward_pe
                if pe_ratio_ratio > 1.1:  # Expecting earnings growth
                    adjustments += min((pe_ratio_ratio - 1) * 0.05, 0.015)  # Cap at 1.5%
                elif pe_ratio_ratio < 0.9:  # Expecting earnings decline
                    adjustments -= min((1 - pe_ratio_ratio) * 0.05, 0.015)  # Cap at -1.5%
                metrics_count += 1
            
            # Dividend yield adjustment with progressive scale
            if dividend_yield and not np.isnan(dividend_yield) and dividend_yield > 0:
                # Higher dividend usually means lower growth, but relationship isn't linear
                if dividend_yield > 0.07:  # 7%+ (very high yield)
                    adjustments -= 0.025
                elif dividend_yield > 0.04:  # 4-7%
                    adjustments -= 0.015
                elif dividend_yield > 0.02:  # 2-4%
                    adjustments -= 0.01
                metrics_count += 1
            
            # Profit margin adjustment with progressive tiers
            if profit_margins and not np.isnan(profit_margins) and profit_margins > -1:
                if profit_margins > 0.25:  # Exceptional margins (25%+)
                    adjustments += 0.015
                elif profit_margins > 0.15:  # Very good margins (15-25%)
                    adjustments += 0.01
                elif profit_margins > 0.08:  # Good margins (8-15%)
                    adjustments += 0.005
                elif profit_margins < 0:  # Negative margins
                    adjustments -= 0.01
                metrics_count += 1
            
            # Return on Equity adjustment
            if roe and not np.isnan(roe) and roe > -1:
                if roe > 0.25:  # Exceptional ROE (25%+)
                    adjustments += 0.01
                elif roe > 0.15:  # Good ROE (15-25%)
                    adjustments += 0.005
                elif roe < 0:  # Negative ROE
                    adjustments -= 0.01
                metrics_count += 1
            
            # Beta adjustment (refined)
            if beta and not np.isnan(beta) and beta > 0:
                # Higher beta usually correlates with higher growth potential
                beta_adj = (beta - 1) * 0.01
                adjustments += min(max(beta_adj, -0.01), 0.015)  # Cap between -1% and +1.5%
                metrics_count += 1
            
            # Apply financial metrics adjustments (average of all valid adjustments)
            if metrics_count > 0:
                metrics_weight = min(0.4, 0.1 * metrics_count)  # More metrics = more confidence
                average_adjustment = adjustments / metrics_count
                default_growth = default_growth * (1 - metrics_weight) + (default_growth + average_adjustment) * metrics_weight
            
            # Check recent performance indicators
            try:
                # Price momentum (1-year price change)
                hist = stock.history(period="1y")
                if not hist.empty and len(hist) > 20:  # Ensure we have meaningful data
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    yearly_return = (end_price / start_price) - 1
                    
                    # Price momentum adjustment
                    momentum_adj = 0
                    if yearly_return > 0.5:  # 50%+ return (strong momentum)
                        momentum_adj = 0.015
                    elif yearly_return > 0.2:  # 20-50% return
                        momentum_adj = 0.01
                    elif yearly_return < -0.3:  # 30%+ decline
                        momentum_adj = -0.015
                    elif yearly_return < -0.1:  # 10-30% decline
                        momentum_adj = -0.01
                    
                    # Apply momentum adjustment with appropriate weight
                    momentum_weight = 0.15  # 15% weight to momentum factor
                    default_growth = default_growth * (1 - momentum_weight) + (default_growth + momentum_adj) * momentum_weight
            except Exception as e:
                print(f"Error calculating price momentum: {e}")
            
            # Sanity checks and caps based on company size
            max_growth_cap = get_max_growth_cap(market_cap)
            min_growth = 0.01  # 1% minimum growth
            
            # Apply caps with some flexibility for extreme cases
            if ticker_upper in ['TSLA', 'NVDA'] and default_growth > max_growth_cap:
                # Special exception for hyper-growth companies
                default_growth = min(default_growth, max_growth_cap * 1.2)
            else:
                default_growth = min(default_growth, max_growth_cap)
            
            default_growth = max(default_growth, min_growth)
            
            print(f"Adjusted default growth for {ticker}: {default_growth:.2%}")
            
        except Exception as e:
            print(f"Error getting company info for default growth: {e}")
            # Use more conservative default if we encounter errors
            default_growth = 0.03
    
    # Create complete result dict matching the structure expected by the main function
    return {
        'short_term_growth': default_growth,
        'historical_fcf_growth': default_growth * 0.9,  # Slightly more conservative
        'revenue_growth': default_growth * 1.1,  # Revenue often grows slightly faster than FCF
        'analyst_estimate': default_growth * 1.2,  # Analysts tend to be optimistic
        'regression_growth': default_growth * 0.85,  # Regression often more conservative
        'company_size': get_company_size_category(market_cap),
        'max_growth_cap': get_max_growth_cap(market_cap),
        'growth_components': {
            'fcf_growth_rates': [],
            'revenue_growth_rates': [],
            'valid_estimates': {
                'default': {
                    'value': default_growth,
                    'weight': 1.0,
                    'reliability': 'Medium' if get_industry_average else 'Low'
                }
            }
        }
    }

##############################################################################################################################################################################
#--------------------------- In 3.3 there's another, more advanced, but incomplete default_growth_values function, use if this one fails ------------------------------------#
##############################################################################################################################################################################

####################################################################################################################################################
################################# Terminal Value Calculation #######################################################################################
####################################################################################################################################################

def calculate_terminal_value(final_year_fcf, short_term_growth, wacc, ticker, years_projection=10):
    """
    Calculate terminal value with improved methodology addressing extreme valuations.
    
    Args:
        final_year_fcf: Last known free cash flow
        short_term_growth: Initial growth rate
        wacc: Weighted Average Cost of Capital
        ticker: Stock ticker symbol
        years_projection: Number of years to project (default 10)
    
    Returns:
        Dictionary containing all DCF components
    """
    # Input validation with more informative messages
    if np.isnan(wacc) or wacc <= 0:
        print(f"Warning for {ticker}: Invalid WACC ({wacc}), using default 9%")
        wacc = 0.09
        
    if np.isnan(short_term_growth):
        print(f"Warning for {ticker}: Invalid growth rate, using default 3%")
        short_term_growth = 0.03
        
    # Cap short-term growth at reasonable levels based on WACC
    if short_term_growth > wacc - 0.02:
        original_growth = short_term_growth
        short_term_growth = min(short_term_growth, wacc - 0.02)
        print(f"Warning for {ticker}: Reducing short-term growth from {original_growth:.2%} to {short_term_growth:.2%} (WACC - 2%)")
    
    # Get company information for terminal growth estimation
    try:
        stock = yf.Ticker(ticker)
        market_cap = stock.info.get('marketCap', 0)
        sector = stock.info.get('sector', '')
        industry = stock.info.get('industry', '')
        
        # Fallback for missing data
        if market_cap == 0 or not market_cap:
            print(f"Warning for {ticker}: Unable to retrieve market cap, estimating based on available data")
            # Try to estimate market cap from price and shares outstanding
            last_price = stock.history(period="1d").get('Close', [0]).iloc[-1]
            shares_out = stock.info.get('sharesOutstanding', 0)
            market_cap = last_price * shares_out if shares_out > 0 else 0
    except Exception as e:
        print(f"Warning for {ticker}: Error retrieving company data: {str(e)}")
        market_cap = 0
        sector = ''
        industry = ''
    
    # Base long-term growth on economic fundamentals (global GDP growth approximation)
    base_terminal_growth = 0.025  # 2.5% baseline (global GDP growth approximation)
    
    # Adjust terminal growth based on company size with more graduations
    size_adjustment = 0
    if market_cap > 1e12:  # Over $1 trillion
        size_adjustment = -0.01  # Mega caps converge lower (-1%)
    elif market_cap > 5e11:  # $500B to $1T
        size_adjustment = -0.0075  # Very large caps (-0.75%)
    elif market_cap > 1e11:  # $100B to $500B
        size_adjustment = -0.005  # Large caps (-0.5%)
    elif market_cap > 1e10:  # $10B to $100B
        size_adjustment = -0.0025  # Mid caps (-0.25%)
    elif market_cap > 2e9:  # $2B to $10B
        size_adjustment = 0  # Small caps (no adjustment)
    else:  # Under $2B
        size_adjustment = 0.0025  # Micro caps (+0.25%)
    
    # Industry-specific adjustments
    industry_adjustment = 0
    tech_industries = ['technology', 'information technology', 'software', 'semiconductors', 'internet']
    defensive_industries = ['utilities', 'consumer staples', 'healthcare', 'telecom']
    cyclical_industries = ['consumer discretionary', 'industrials', 'materials']
    
    sector_lower = sector.lower()
    industry_lower = industry.lower()
    
    # Check both sector and industry for better matching
    if any(term in sector_lower or term in industry_lower for term in tech_industries):
        industry_adjustment = 0.003  # Technology sectors (+0.3%)
    elif any(term in sector_lower or term in industry_lower for term in defensive_industries):
        industry_adjustment = -0.003  # Defensive sectors (-0.3%)
    elif any(term in sector_lower or term in industry_lower for term in cyclical_industries):
        industry_adjustment = 0  # Cyclical sectors (no adjustment)
    
    # Calculate the terminal growth rate with constraints
    long_term_gdp_growth = base_terminal_growth + size_adjustment + industry_adjustment
    
    # Safety constraints to prevent unrealistic terminal growth
    long_term_gdp_growth = max(0.01, min(long_term_gdp_growth, 0.04))  # Bound between 1-4%
    
    # Ensure terminal growth < WACC (for Gordon Growth Model validity)
    if long_term_gdp_growth >= wacc - 0.01:
        original_growth = long_term_gdp_growth
        long_term_gdp_growth = wacc - 0.02  # At least 2% below WACC
        print(f"Warning for {ticker}: Terminal growth rate {original_growth:.2%} too close to WACC {wacc:.2%}, adjusted to {long_term_gdp_growth:.2%}")
    
    # Create smoother transition from short-term to long-term growth
    growth_rates = []
    for year in range(1, years_projection + 1):
        # Use a more natural curve for transition (sigmoid-like)
        if year <= 3:
            # First 3 years: Full short-term growth
            growth_rates.append(short_term_growth)
        else:
            # Years 4-10: Sigmoid transition to long-term growth
            # Transformed position in range [0,1]
            position = (year - 3) / (years_projection - 3)
            # Apply sigmoid-like formula for smoother transition
            transition_factor = 1 / (1 + np.exp(-10 * (position - 0.5)))
            growth_rate = short_term_growth - (transition_factor * (short_term_growth - long_term_gdp_growth))
            growth_rates.append(growth_rate)
    
    # Calculate FCF for each projected year with varying growth rates
    projected_fcfs = [final_year_fcf]
    for rate in growth_rates:
        # Check for reasonableness of FCF growth
        new_fcf = projected_fcfs[-1] * (1 + rate)
        projected_fcfs.append(new_fcf)
    
    # Remove the initial FCF as it's the actual last year
    projected_fcfs = projected_fcfs[1:]
    
    # Validate FCF projections
    if any(fcf <= 0 for fcf in projected_fcfs):
        print(f"Warning for {ticker}: Negative FCF projections detected, check input data")
    
    # Calculate present value of explicit period FCFs
    pv_fcfs = []
    for year, fcf in enumerate(projected_fcfs, start=1):
        pv_fcf = fcf / ((1 + wacc) ** year)
        pv_fcfs.append(pv_fcf)
    
    # Terminal value using two-stage approach
    # First calculate using Gordon Growth
    terminal_fcf = projected_fcfs[-1] * (1 + long_term_gdp_growth)
    gordon_terminal_value = terminal_fcf / (wacc - long_term_gdp_growth)
    
    # Then calculate using Exit Multiple method (typically 8-14x for mature companies)
    final_year_ebitda_multiple = 10  # Adjust based on sector norms if needed
    exit_multiple_value = projected_fcfs[-1] * final_year_ebitda_multiple
    
    # Use a weighted average of the two methods for more balanced results
    terminal_value = 0.7 * gordon_terminal_value + 0.3 * exit_multiple_value
    
    # Sanity check on terminal value (shouldn't be more than 70-80% of total value)
    pv_terminal_value = terminal_value / ((1 + wacc) ** years_projection)
    total_dcf_value = sum(pv_fcfs) + pv_terminal_value
    
    # If terminal value is more than 75% of total, apply dampening
    terminal_value_percentage = pv_terminal_value / total_dcf_value if total_dcf_value > 0 else 0
    if terminal_value_percentage > 0.75:
        dampening_factor = 0.75 / terminal_value_percentage
        original_terminal_value = pv_terminal_value
        pv_terminal_value *= dampening_factor
        print(f"Warning for {ticker}: Terminal value too dominant ({terminal_value_percentage:.1%} of total), dampened by factor of {dampening_factor:.2f}")
        total_dcf_value = sum(pv_fcfs) + pv_terminal_value
    
    # Calculate percentage of value from terminal value (useful diagnostic)
    terminal_value_percentage = pv_terminal_value / total_dcf_value if total_dcf_value > 0 else 0
    
    return {
        'projected_fcfs': projected_fcfs,
        'pv_fcfs': pv_fcfs,
        'terminal_value': terminal_value,
        'pv_terminal_value': pv_terminal_value,
        'growth_rates': growth_rates,
        'terminal_growth_rate': long_term_gdp_growth,
        'terminal_value_percentage': terminal_value_percentage,
        'total_dcf_value': total_dcf_value
    }


####################################################################################################################################################
################################## Full Discount Rate Calculation with Opt. Monte Carlo Sim. #######################################################
####################################################################################################################################################


def perform_advanced_dcf_analysis(financial_data, ticker, cik=None):
    """
    Perform a comprehensive DCF analysis based on financial data
    
    Args:
        financial_data (dict): Financial data from FinancialDataAcquisition
        ticker (str): Stock ticker symbol
        cik (str, optional): Company CIK number
        
    Returns:
        dict: DCF analysis results
    """
    if not financial_data:
        print(f"No financial data available for {ticker}")
        return None
    
    # Calculate WACC (Discount Rate)
    wacc_data = calculate_wacc(ticker)
    discount_rate = wacc_data['wacc']
    
    # Calculate Growth Rates
    growth_data = calculate_growth_rates(ticker, cik, financial_data)
    growth_rate = growth_data['short_term_growth']
    
    # Get FCF and shares outstanding
    free_cash_flow = financial_data['free_cash_flow']
    shares_outstanding = financial_data['shares_outstanding']
    current_price = financial_data['current_price']
    
    # Calculate Terminal Value and DCF
    terminal_data = calculate_terminal_value(free_cash_flow, growth_rate, discount_rate, ticker)
    
    # Calculate intrinsic value per share
    intrinsic_value_per_share = terminal_data['total_dcf_value'] / shares_outstanding
    
    # Determine valuation
    if not np.isnan(intrinsic_value_per_share) and not np.isnan(current_price) and current_price > 0:
        valuation_gap = (intrinsic_value_per_share / current_price - 1) * 100
        is_undervalued = intrinsic_value_per_share > current_price
    else:
        valuation_gap = np.nan
        is_undervalued = None
    
    # Prepare results
    results = {
        'ticker': ticker,
        'fcf': free_cash_flow,
        'shares_outstanding': shares_outstanding,
        'current_price': current_price,
        'discount_rate': discount_rate,
        'growth_rate': growth_rate,
        'dcf_value': terminal_data['total_dcf_value'],
        'intrinsic_value': intrinsic_value_per_share,
        'valuation_gap': valuation_gap,
        'is_undervalued': is_undervalued,
        'detailed_growth': growth_data,
        'detailed_wacc': wacc_data,
        'detailed_projections': terminal_data
    }
    
    return results

def run_monte_carlo_simulation(financial_data, ticker, cik=None, iterations=1000):
    """
    Run a Monte Carlo simulation to establish confidence intervals for DCF valuation
    
    Args:
        financial_data (dict): Financial data from FinancialDataAcquisition
        ticker (str): Stock ticker symbol
        cik (str, optional): Company CIK number
        iterations (int): Number of simulation iterations
        
    Returns:
        dict: Simulation results with percentiles
    """
    print(f"\nRunning Monte Carlo simulation for {ticker} ({iterations} iterations)...")
    
    # Base case DCF
    base_case = perform_advanced_dcf_analysis(financial_data, ticker, cik)
    if not base_case:
        return None
    
    # Extract key values
    base_fcf = financial_data['free_cash_flow']
    base_discount = base_case['discount_rate']
    base_growth = base_case['growth_rate']
    shares = financial_data['shares_outstanding']
    
    # Define variation ranges (percentage points)
    fcf_variation = 0.10  # ±10%
    discount_variation = 0.02  # ±2 percentage points
    growth_variation = 0.02  # ±2 percentage points
    
    # Simulation results
    simulated_values = []
    
    for _ in tqdm(range(iterations)):
        # Random variations
        sim_fcf = base_fcf * (1 + random.uniform(-fcf_variation, fcf_variation))
        sim_discount = max(0.04, base_discount + random.uniform(-discount_variation, discount_variation))
        sim_growth = max(0.01, base_growth + random.uniform(-growth_variation, growth_variation))
        
        # Calculate terminal value with simulated parameters
        sim_terminal = calculate_terminal_value(sim_fcf, sim_growth, sim_discount, ticker)
        
        # Calculate intrinsic value per share
        sim_value = sim_terminal['total_dcf_value'] / shares
        simulated_values.append(sim_value)
    
    # Sort results for percentiles
    simulated_values.sort()
    
    # Calculate percentiles
    percentiles = {
        '5th': np.percentile(simulated_values, 5),
        '25th': np.percentile(simulated_values, 25),
        '50th': np.percentile(simulated_values, 50),
        '75th': np.percentile(simulated_values, 75),
        '95th': np.percentile(simulated_values, 95)
    }
    
    # Return detailed simulation results
    return {
        'base_case': base_case['intrinsic_value'],
        'mean': np.mean(simulated_values),
        'median': np.median(simulated_values),
        'std_dev': np.std(simulated_values),
        'percentiles': percentiles,
        'current_price': financial_data['current_price'],
        'probability_undervalued': sum(1 for x in simulated_values if x > financial_data['current_price']) / iterations * 100,
        'all_values': simulated_values
    }

def print_dcf_results(dcf_results, financial_data, monte_carlo=None):
    """
    Print formatted DCF analysis results
    
    Args:
        dcf_results (dict): Results from perform_advanced_dcf_analysis
        financial_data (dict): Original financial data
        monte_carlo (dict, optional): Monte Carlo simulation results
    """
    if not dcf_results:
        print("DCF analysis failed. Check for errors in the estimator functions.")
        return
    
    # Extract key values from results
    ticker = dcf_results['ticker']
    free_cash_flow = dcf_results['fcf']
    shares_outstanding = dcf_results['shares_outstanding']
    current_price = dcf_results['current_price']
    discount_rate = dcf_results['discount_rate']
    growth_rate = dcf_results['growth_rate']
    total_dcf = dcf_results['dcf_value']
    intrinsic_value_per_share = dcf_results['intrinsic_value']
    valuation_gap = dcf_results['valuation_gap']
    
    # Detailed components
    wacc_details = dcf_results['detailed_wacc']
    growth_details = dcf_results['detailed_growth']
    projection_details = dcf_results['detailed_projections']
    
    # Get the projected FCFs and present values
    projected_fcfs = projection_details['projected_fcfs']
    pv_fcfs = projection_details['pv_fcfs']
    terminal_value = projection_details['terminal_value']
    pv_terminal_value = projection_details['pv_terminal_value']
    years = len(projected_fcfs)
    
    # Print detailed results
    print(f"\n{'='*50}")
    print(f"DCF Valuation Results for {ticker}")
    print(f"{'='*50}")
    print(f"Free Cash Flow (Latest): ${free_cash_flow:,.2f}")
    print(f"WACC (Discount Rate): {discount_rate:.2%}")
    print(f"Projected Growth Rate: {growth_rate:.2%}")
    print(f"Data Source: {financial_data.get('data_source', 'Unknown')}")
    
    # Print WACC components
    print("\n--- WACC Components ---")
    print(f"Cost of Equity: {wacc_details['cost_of_equity']:.2%}")
    print(f"After-tax Cost of Debt: {wacc_details['after_tax_cost_of_debt']:.2%}")
    print(f"Debt Weight: {wacc_details['weight_debt']:.2%}")
    print(f"Equity Weight: {wacc_details['weight_equity']:.2%}")
    print(f"Beta: {wacc_details['beta']:.2f}")
    
    # Print Growth Components
    print("\n--- Growth Rate Components ---")
    if growth_details.get('historical_fcf_growth') is not None:
        print(f"Historical FCF Growth: {growth_details['historical_fcf_growth']:.2%}")
    if growth_details.get('revenue_growth') is not None:
        print(f"Historical Revenue Growth: {growth_details['revenue_growth']:.2%}")
    if growth_details.get('analyst_estimate') is not None:
        print(f"Analyst Growth Estimate: {growth_details['analyst_estimate']:.2%}")
    if growth_details.get('regression_growth') is not None:
        print(f"Regression-based Growth: {growth_details['regression_growth']:.2%}")
    
    # Print FCF Projections
    print("\n--- FCF Projections ---")
    growth_rates = projection_details['growth_rates']
    for i, (fcf, pv, rate) in enumerate(zip(projected_fcfs, pv_fcfs, growth_rates), start=1):
        print(f"Year {i}: FCF ${fcf:,.2f} (Growth: {rate:.2%}, PV: ${pv:,.2f})")
    
    # Print DCF Valuation Summary
    print(f"\n--- DCF Valuation Summary ---")
    print(f"Present Value of Future FCF: ${sum(pv_fcfs):,.2f}")
    print(f"Terminal Value: ${terminal_value:,.2f}")
    print(f"Present Value of Terminal Value: ${pv_terminal_value:,.2f}")
    print(f"Total DCF Value: ${total_dcf:,.2f}")
    print(f"Shares Outstanding: {shares_outstanding:,}")
    print(f"Intrinsic Value per Share: ${intrinsic_value_per_share:.2f}")
    print(f"Current Market Price: ${current_price:.2f}")
    
    # Determine if the stock is under or overvalued
    if intrinsic_value_per_share > current_price:
        print(f"✅ {ticker} is UNDERVALUED by {valuation_gap:.2f}%")
    else:
        print(f"⚠️ {ticker} is OVERVALUED by {abs(valuation_gap):.2f}%")
    
    # Print Monte Carlo results if available
    if monte_carlo:
        print("\n--- Monte Carlo Simulation Results ---")
        print(f"Median Intrinsic Value: ${monte_carlo['median']:.2f}")
        print(f"Mean Intrinsic Value: ${monte_carlo['mean']:.2f}")
        print(f"Standard Deviation: ${monte_carlo['std_dev']:.2f}")
        print(f"5th Percentile: ${monte_carlo['percentiles']['5th']:.2f}")
        print(f"95th Percentile: ${monte_carlo['percentiles']['95th']:.2f}")
        print(f"Probability of Being Undervalued: {monte_carlo['probability_undervalued']:.1f}%")
    
    # Sensitivity analysis
    print("\n--- Sensitivity Analysis ---")
    base_discount = discount_rate
    base_growth = growth_rate
    
    # Create ranges around the calculated rates
    discount_ranges = [
        max(0.04, base_discount - 0.02),
        max(0.05, base_discount - 0.01),
        base_discount,
        base_discount + 0.01,
        base_discount + 0.02
    ]
    
    growth_ranges = [
        max(0.01, base_growth - 0.015),
        max(0.015, base_growth - 0.0075),
        base_growth,
        base_growth + 0.0075,
        base_growth + 0.015
    ]
    
    sensitivity_results = []
    
    for d_rate in discount_ranges:
        row = []
        for g_rate in growth_ranges:
            # Use the terminal value calculation function for consistent methodology
            tv_data = calculate_terminal_value(free_cash_flow, g_rate, d_rate, ticker)
            value_per_share = tv_data['total_dcf_value'] / shares_outstanding
            row.append(value_per_share)
        sensitivity_results.append(row)
    
    # Create a DataFrame for better visualization
    sensitivity_df = pd.DataFrame(sensitivity_results, 
                                index=[f"Discount {d*100:.1f}%" for d in discount_ranges],
                                columns=[f"Growth {g*100:.1f}%" for g in growth_ranges])
    
    print("\nIntrinsic Value per Share Sensitivity Table:")
    print(sensitivity_df)

def plot_monte_carlo_results(monte_carlo_results, ticker):
    """
    Create visualization of Monte Carlo simulation results
    
    Args:
        monte_carlo_results (dict): Results from the Monte Carlo simulation
        ticker (str): Stock ticker symbol
    """
    if not monte_carlo_results:
        return
    
    plt.figure(figsize=(12, 8))
    
    # Histogram of simulated values
    plt.hist(monte_carlo_results['all_values'], bins=50, alpha=0.7, color='blue')
    
    # Add vertical lines for key values
    plt.axvline(monte_carlo_results['current_price'], color='red', linestyle='--', 
                linewidth=2, label=f'Current Price (${monte_carlo_results["current_price"]:.2f})')
    
    plt.axvline(monte_carlo_results['base_case'], color='green', linestyle='-', 
                linewidth=2, label=f'Base Case DCF (${monte_carlo_results["base_case"]:.2f})')
    
    plt.axvline(monte_carlo_results['percentiles']['5th'], color='orange', linestyle=':', 
                linewidth=2, label=f'5th Percentile (${monte_carlo_results["percentiles"]["5th"]:.2f})')
    
    plt.axvline(monte_carlo_results['percentiles']['95th'], color='orange', linestyle=':', 
                linewidth=2, label=f'95th Percentile (${monte_carlo_results["percentiles"]["95th"]:.2f})')
    
    # Add title and labels
    plt.title(f'Monte Carlo DCF Simulation for {ticker} ({len(monte_carlo_results["all_values"])} iterations)', fontsize=16)
    plt.xlabel('Intrinsic Value per Share ($)', fontsize=14)
    plt.ylabel('Frequency', fontsize=14)
    
    # Add a text box with key statistics
    textstr = '\n'.join((
        f'Median: ${monte_carlo_results["median"]:.2f}',
        f'Mean: ${monte_carlo_results["mean"]:.2f}',
        f'Std Dev: ${monte_carlo_results["std_dev"]:.2f}',
        f'Prob. Undervalued: {monte_carlo_results["probability_undervalued"]:.1f}%'))
    
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
             verticalalignment='top', bbox=props)
    
    plt.legend()
    plt.tight_layout()
    
    # Save the plot
    plt.savefig(f'{ticker}_monte_carlo_dcf.png', dpi=300)
    
    print(f"\nMonte Carlo DCF plot saved as {ticker}_monte_carlo_dcf.png")

def main():
    """
    Main function to run DCF analysis on a list of stocks
    """
    print("DCF Analysis Tool - Enhanced Version")
    print("=" * 50)
    
    # Step 1: Set up API keys (either in environment variables or passed directly)
    # Option 1: Set environment variables
    # os.environ['SEC_API_KEY'] = 'your_sec_api_key'  # https://sec-api.io
    # os.environ['FMP_API_KEY'] = 'your_fmp_api_key'  # Financial Modeling Prep
    # os.environ['ALPHA_VANTAGE_KEY'] = 'your_alpha_vantage_key'  # Alpha Vantage
    
    # Step 2: Initialize the data acquisition object
    data_acquisition = FinancialDataAcquisition()
    
    # Step 3: Define ticker symbols to analyze
    # You can use your existing test_stocks or define a new list
    test_stocks = [
        ("AAPL", "0000320193"), 
        ("MSFT", "0000789019"), 
        ("AMZN", "0001018724"), 
        ("GOOGL", "0001652044"),  
        ("TSLA", "0001318605"), 
        ("META", "0001326801"), # Updated from FB
        ("NVDA", "0001045810"), 
        ("PYPL", "0001633917"), 
        ("ADBE", "0000796343"), 
        ("NFLX", "0001065280")
    ]
    
    # Set Monte Carlo simulation flag
    run_monte_carlo = True  # Set to False to disable Monte Carlo simulation
    monte_carlo_iterations = 300
    
    # Step 4: Process each stock
    for stock in test_stocks:
        time.sleep(6)  # Add a delay to avoid rate limits
        ticker, cik = stock
        
        print(f"\n{'*' * 70}")
        print(f"Processing {ticker} (CIK: {cik})")
        print(f"{'*' * 70}")
        
        # Get financial data using the enhanced acquisition class
        financial_data = data_acquisition.get_financial_data(ticker, cik)
        
        if financial_data:
            print(f"\n✅ Retrieved financial data for {ticker} from {financial_data.get('data_source', 'Unknown')}:")
            print(f"   Free Cash Flow: ${financial_data['free_cash_flow']:,.2f}")
            print(f"   Shares Outstanding: {financial_data['shares_outstanding']:,}")
            print(f"   Current Price: ${financial_data['current_price']:.2f}")
            
            # Perform DCF analysis
            print("\nCalculating DCF valuation...")
            dcf_results = perform_advanced_dcf_analysis(financial_data, ticker, cik)
            
            # Run Monte Carlo simulation if enabled
            monte_carlo_results = None
            if run_monte_carlo and dcf_results:
                monte_carlo_results = run_monte_carlo_simulation(
                    financial_data, ticker, cik, monte_carlo_iterations
                )
                
                # Plot Monte Carlo results
                if monte_carlo_results:
                    plot_monte_carlo_results(monte_carlo_results, ticker)
            
            # Print the results
            print_dcf_results(dcf_results, financial_data, monte_carlo_results)
            
        else:
            print(f"\n❌ Failed to retrieve required financial data for {ticker}.")

if __name__ == "__main__":
    main()
