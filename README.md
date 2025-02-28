# DCF-Stock-Analysis

A comprehensive financial analysis tool designed for medium to long-term investment decision-making that leverages discounted cash flow (DCF) modeling to determine the intrinsic value of publicly traded companies by analyzing historical financial data, projecting future cash flows &amp; comparing the calculated fair value against current market prices.

# Preface
This project is early in development. View this document, and thus repository as a whole, as an early draft to be subject to iterative correction until otherwise announced.  

# Features
Automated Financial Data Retrieval: Direct integration with SEC EDGAR database to obtain official financial statements
Fundamental Analysis: Processes balance sheets, income statements, and cash flow statements to extract key metrics
DCF Valuation Model: Implements industry-standard DCF methodology with configurable parameters
Comparative Analysis: Benchmarks companies against industry peers and historical performance
Visualization Dashboard: Interactive charts and graphs displaying valuation results and sensitivity analyses
Batch Processing: Analyze multiple stocks simultaneously for portfolio assessment

# Technology Stack
Backend (Data Processing):
Python 3.8+: Core programming language
Pandas: Data manipulation and analysis
NumPy: Numerical computations
Scikit-learn: Statistical analysis and regression for growth rate predictions
edgartools: API wrapper for SEC EDGAR database access
BeautifulSoup: Web scraping supplementary financial information
yFinance: Additional market data retrieval
MATLAB Integration: Advanced financial modeling capabilities

Frontend (Presentation):
Django: Web framework for building the application interface
Jinja2: Templating engine for dynamic content rendering
Bootstrap: Responsive UI components and styling
Plotly/Dash: Interactive data visualization components

Deployment:
Heroku: Cloud platform for application hosting
PostgreSQL: Database for storing processed financial data and analysis results
Docker: Containerization for consistent development and deployment environments

# Setup Instructions
Installation prerequisites:
Python 3.8+
pip (Python package manager)
Git

Clone the repository:
git clone https://github.com/yourusername/dcf-stock-analyzer.git
cd dcf-stock-analyzer

Create and activate virtual environment:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

Install dependencies:
pip install -r requirements.txt

Set up environment variables:
cp .env.example .env

Edit .env file with your API keys and configuration

Initialize the database:
python manage.py migrate

Run the development server:
python manage.py runserver

# Configuration
Edit config.yaml to set DCF model parameters:
Forecast period (default: 10 years)
Terminal growth rate (default: 2.5%)
Discount rate methodology (WACC or custom)
Historical data lookback period

# Basic Analysis
pythonCopyfrom dcf_analyzer import StockAnalyzer

Initialize analyzer for a single company:
analyzer = StockAnalyzer(ticker="AAPL")

Perform complete DCF analysis:
result = analyzer.run_dcf_analysis()

View summary results:
print(result.summary())

Generate detailed report:
analyzer.generate_report("AAPL_DCF_Analysis.pdf")
Batch Analysis
pythonCopyfrom dcf_analyzer import BatchAnalyzer

Initialize analyzer for multiple companies:
tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "META"]
batch = BatchAnalyzer(tickers=tickers)

Run analysis with custom parameters:
results = batch.run_analysis(
    forecast_years=10,
    terminal_growth=0.02,
    margin_of_safety=0.15
)

Export results to CSV:
batch.export_results("portfolio_analysis.csv")

# Financial Methodology
The DCF Stock Analyzer implements a standard discounted cash flow model following these steps:

Historical Data Analysis:
Calculate historical free cash flow (FCF) growth rates
Analyze financial ratios and trends
Compare with industry benchmarks

Growth Rate Projection:
Forecast future FCF using regression analysis
Apply industry-specific growth constraints
Consider analyst estimates when available

Terminal Value Calculation:
Apply perpetuity growth method for terminal value
TV = FCF₁₀ × (1 + g) ÷ (r - g)
Where g = long-term growth rate, r = discount rate

Present Value Calculation:
Discount all projected cash flows to present value
PV = FCF₍ₙ₎ ÷ (1 + r)ⁿ

Intrinsic Value Determination:
Sum all discounted cash flows
Divide by shares outstanding
Apply margin of safety (configurable)


Understanding Applicable Financial Concepts:
Free Cash Flow (FCF):The cash a company generates after accounting for capital expenditures (e.g., building factories, buying equipment).
FCF = Operating Cash Flow − Capital Expenditures
Growth Rate:
The rate at which a company’s revenue or free cash flow is expected to grow.
Can be historical (based on past performance) or projected (based on industry trends).
Terminal Value (TV):
The value of the company at the end of the forecast period (e.g., 10 years).
Represents the company’s value beyond the forecast period, assuming stable growth.
Discount Rate (r):
The rate used to discount future cash flows to their present value.
Often the Weighted Average Cost of Capital (WACC), which reflects the company’s cost of debt and equity.
Discounted Cash Flow (DCF):
The sum of all future cash flows discounted back to their present value.
Intrinsic Value per Share:
The fair value of a single share of the company’s stock.
Formula:
Intrinsic Value=DCF / Total Shares Outstanding

Step-by-Step Process
Step 1: Forecast Free Cash Flows (FCF)
Collect Historical Data:
Use the company’s financial statements (10-K, 10-Q) to find historical FCF.
Calculate the historical growth rate of FCF.
Project Future FCF:
Use the historical growth rate or a reasonable estimate (e.g., industry average) to project FCF for the next 10 years.

Where:
t: time
g: Growth rate.
Step 2: Calculate Terminal Value (TV)
Assume a Long-Term Growth Rate:
Use a conservative growth rate (e.g., 2-3%) for the terminal value.

Where:
FCF10  : Free cash flow in year 10.
g: Long-term growth rate.
r: Discount rate.
Step 3: Discount Future Cash Flows
Calculate Present Value of FCF:
Discount each year’s FCF back to its present value.

Calculate Present Value of Terminal Value:
Discount the terminal value back to its present value.


Step 4: Sum All Present Values
Calculate Discount Cash Flow (DCF):
Sum the present values of all FCFs and the terminal value.

Step 5: Calculate Intrinsic Value per Share
Divide DCF by Shares Outstanding:

Step 6: Compare to Current Stock Price
Determine Over/Undervaluation:
If the intrinsic value > current stock price, the stock is undervalued.
If the intrinsic value < current stock price, the stock is overvalued.

Example Calculation for a hypothetical company:

Make Assumptions
Current FCF: $100 million.
Growth Rate (g): 5% for the first 10 years, 3% terminal growth.
Discount Rate (r): 8%.
Shares Outstanding :0 million.

Step 1: Forecast FCF

Year, FCF (in millions):
1 = $105.00
2 = $110.25
3 = $115.76
4 = $121.55
5 = $127.63
6 = $134.01
7 = $140.71
8 = $147.75
9 = $155.13
10 = $162.89
Step 2: Calculate Terminal Value (TV)

Step 3: Discount Future Cash Flows (DCF)


Year
FCF (in millions)
PV of FCF (in millions)
1
$105.00
$97.22
2
$110.25
$94.56
3
$115.76
$92.00
4
$121.55
$89.54
5
$127.63
$87.17
6
$134.01
$84.89
7
$140.71
$82.70
8
$147.75
$80.59
9
$155.13
$78.56
10
$162.89
$76.61




Step 4: Sum All Present Values
DCF = 97.22 + 94.56 + 92.00 + 89.54 + 87.17+ 84.89 + 82.7
+ 80.59 + 78.56 +76.61 + 1,554.77 = 2,418.61
Step 5: Calculate Intrinsic Value per Share
Intrinsic Value = 2,418.61 / 50 = $48.37
Using a margin of error of 10-20%: 
If the current stock price is $53.21(10% error), $58.08 (20% error) the stock is overvalued.
If the current stock price is $43.53 (10% error) , $38.70 (20% error), the stock is undervalued.


Discounted Cash Flow Modeling Techniques
Discounted Cash Flow Model Components
I'll walk you through the key methods for developing an accurate DCF model to determine a stock's intrinsic value:
Growth Rate Estimation
There are several approaches to estimate future growth rates:
Historical performance analysis: Calculate the company's past growth rates for revenue, earnings, and free cash flow to establish a baseline.
Management guidance: Review forward-looking statements from company executives about anticipated growth.
Industry analysis: Compare to industry averages and growth forecasts from reliable sources.
Competitive positioning: Assess market share trends, competitive advantages, and potential market expansion.
Regression analysis: Use statistical methods to project growth based on historical data and relevant variables.
Bottom-up forecasting: Build detailed projections for each business segment or product line.
Step-by-Step Growth Rate Estimation for DCF Model
I'll walk through the detailed calculations for growth rate estimation, including where to find the necessary data in financial documents:
1. Historical Growth Rate Calculation
Data sources:
Annual Reports (10-K)
Quarterly Reports (10-Q)
Investor Presentations
Step-by-step calculation:
Collect historical financial data (minimum 5 years):
Revenue: Income Statement (first line)
EBITDA: Income Statement (calculated as Operating Income + Depreciation & Amortization)
Net Income: Income Statement (bottom line)
Free Cash Flow: Cash Flow Statement or calculated as:
Operating Cash Flow (from Cash Flow Statement)
Minus Capital Expenditures (from Cash Flow Statement, "Purchases of Property, Plant & Equipment")
Calculate year-over-year growth rates:

Annual Growth Rate = (Current Year Value / Previous Year Value) - 1


Calculate Compound Annual Growth Rate (CAGR):

CAGR = (Ending Value / Beginning Value)^(1/n) - 1
 Where n = number of years
Calculate weighted average growth rate (giving more weight to recent years):

Weighted Average = (Year 1 × 0.1) + (Year 2 × 0.15) + (Year 3 × 0.2) + (Year 4 × 0.25) + (Year 5 × 0.3)


2. Fundamental Growth Rate Drivers
Data sources:
Management Discussion & Analysis (MD&A) section of Annual Report
Earnings Call Transcripts
Industry Reports
Key metrics to analyze:
Return on Invested Capital (ROIC):
ROIC = NOPAT / Invested Capital


NOPAT (Net Operating Profit After Tax) = Operating Income × (1 - Tax Rate)
Operating Income: Income Statement
Tax Rate: Income Statement (Income Tax Expense / Income Before Tax)
Invested Capital = Total Assets - Current Liabilities
Total Assets: Balance Sheet
Current Liabilities: Balance Sheet
Reinvestment Rate:

Reinvestment Rate = (Capital Expenditures + Change in Working Capital) / NOPAT


Capital Expenditures: Cash Flow Statement
Change in Working Capital: Cash Flow Statement or calculated as:
Δ Working Capital = Δ Current Assets - Δ Current Liabilities (excluding cash and short-term debt)
NOPAT: Calculated above
Fundamental Growth Rate:
  Fundamental Growth Rate = ROIC × Reinvestment Rate
3. Market Size and Penetration Analysis
Data sources:
Industry Reports
Company Investor Presentations
Annual Report (Business Section)
Steps:
Calculate Total Addressable Market (TAM):
Find industry size data from market research reports
Company often discloses TAM estimates in investor presentations
Calculate current market share:

Market Share = Company Revenue / Total Market Size


Company Revenue: Income Statement
Total Market Size: Industry Reports
Project market share growth:
Review historical market share trends
Assess competitive position (from Business Overview in Annual Report)
Consider management guidance on market expansion
4. Segment-Based Growth Projection
Data sources:
Segment Reporting in Annual Report (Note disclosures)
Product or Geographic Breakdowns in MD&A
Steps:
Identify growth rates for each business segment:
Calculate historical growth for each segment using segment revenue data
Segment data is typically found in the Notes to Financial Statements
Weight each segment by revenue contribution:

Segment Weight = Segment Revenue / Total Revenue


Calculate weighted growth rate:

Weighted Growth = Σ (Segment Growth Rate × Segment Weight)
5. Regression Analysis
Data sources:
Historical Financial Data
Macroeconomic Indicators
Steps:
Identify independent variables that correlate with company growth:
GDP growth (from economic data)
Industry-specific metrics
Relevant economic indicators
Run regression analysis:
Company Growth = α + β₁(Variable 1) + β₂(Variable 2) + ... + ε
Use regression model to forecast growth based on projected values of independent variables
6. Final Growth Rate Determination
Create projection scenarios:
Base case: Weighted average of historical and fundamental growth rates
Optimistic case: Higher end of historical range or analyst estimates
Pessimistic case: Lower end of historical range or industry growth
Apply growth rate decay:
Start with initial growth rate (from steps above)
Gradually reduce growth rate over projection period
Converge to terminal growth rate (typically 2-3%, in line with long-term GDP)
Document assumptions and perform sensitivity analysis on final growth rates
Future Cash Flow Projection
Free Cash Flow to Firm (FCFF):
EBIT × (1 - Tax Rate) + Depreciation & Amortization - Capital Expenditures - Change in Working Capital
Free Cash Flow to Equity (FCFE):
Net Income + Depreciation & Amortization - Capital Expenditures - Change in Working Capital - Net Borrowing
Scenario analysis: Develop multiple scenarios (base, optimistic, pessimistic) to account for uncertainty.
Explicit forecast period: Typically 5-10 years with detailed year-by-year projections.
Step-by-Step Future Cash Flow Projection
Data sources:
Income Statement (10-K, 10-Q)
Balance Sheet
Cash Flow Statement
Management Guidance
Analyst Reports
1. Free Cash Flow to Firm (FCFF) Calculation
Calculate EBIT (Earnings Before Interest and Taxes):
Found directly on Income Statement or:
Revenue - COGS - Operating Expenses
Calculate NOPAT (Net Operating Profit After Tax):
NOPAT = EBIT × (1 - Tax Rate)
Tax Rate: Income Statement (Income Tax Expense / Income Before Tax)
Add back non-cash expenses:
+ Depreciation & Amortization
Found on Cash Flow Statement or Notes to Financial Statements
Subtract Capital Expenditures:
 - Capital Expenditures
Found on Cash Flow Statement ("Purchases of Property, Plant & Equipment")
Subtract Change in Net Working Capital:
 
- Δ Working Capital


Calculate as:
Δ (Current Assets - Cash) - Δ (Current Liabilities - Short-term Debt)
All components found on Balance Sheet
Final FCFF Formula:
FCFF = EBIT × (1 - Tax Rate) + Depreciation & Amortization - Capital Expenditures - Δ Working Capital
2. Project Each Component Forward
Revenue Projection:
Apply growth rates from previous section
Consider different growth rates for different time periods
Account for cyclicality if applicable
EBIT Margin Projection:
Historical EBIT margins from Income Statement
Project future margins based on:
Historical trends
Management guidance on operational efficiency
Industry benchmarks
Competitive landscape
Tax Rate Projection:
Use effective tax rate from Income Statement
Adjust for announced tax policy changes
Consider tax benefits from loss carryforwards (found in tax footnotes)
D&A Projection:
Historical D&A as percentage of revenue or fixed assets
Adjust for anticipated asset base changes
Consider useful life of assets (found in Notes to Financial Statements)
CapEx Projection:
Historical CapEx as percentage of revenue
Adjust for planned expansion or contraction (from MD&A or earnings calls)
Consider industry-specific investment cycles
Working Capital Projection:
Historical working capital as percentage of revenue
Adjust for efficiency improvements
Consider industry-specific seasonality
3. Time Value of Money Adjustment
Discount each projected cash flow:
	Present Value of FCF = FCF × (1 / (1 + r)^t)
 Where:
r = discount rate (WACC)
t = time period (years)
4. Error Margin Calculation
Sensitivity analysis:
Create matrix varying key inputs by ±5%, ±10%, ±15%
Calculate resulting range of present values
Monte Carlo simulation:
Assign probability distributions to key variables
Run multiple iterations (1000+)
Establish confidence intervals (e.g., 90% confidence interval)
Standard error reporting:

Value Range = Base Case Value ± (Standard Deviation × Z-score)


For 95% confidence interval, Z-score = 1.96
Terminal Value Calculation
Perpetuity Growth Method:
Terminal Value = FCF in final year × (1 + Long-term Growth Rate) ÷ (Discount Rate - Long-term Growth Rate)
Long-term growth rate is typically set at or below GDP growth (2-3%)
Exit Multiple Method:
Terminal Value = Financial Metric in final year × Appropriate Multiple
Common multiples include EV/EBITDA, P/E, or EV/Sales
Multiples should reflect expected maturity stage of the company
Step-by-Step Terminal Value Calculation
Data sources:
Projected Financial Statements
Industry Reports
GDP Forecasts
Industry Transaction Multiples
1. Perpetuity Growth Method
Determine final year's normalized FCF:
Take final year of explicit forecast
Adjust for any abnormalities or one-time items
Source: Projected Cash Flow Statement
Determine long-term growth rate (g):
Long-term GDP growth forecasts (economic reports)
Industry maturity assessment (industry reports)
Inflation expectations (central bank projections)
Typically 2-3% for mature companies/markets
Source: Economic forecasts, central bank targets
Terminal Value Calculation:
	Terminal Value = FCF_final × (1 + g) / (WACC - g)


Discount Terminal Value to present:
	PV of Terminal Value = Terminal Value / (1 + WACC)^n
 Where n = number of years in explicit forecast period
2. Exit Multiple Method
Determining appropriate financial metric:
EBITDA, EBIT, Revenue, or Earnings
Source: Projected Income Statement
Selecting appropriate multiple:
Current industry trading multiples
Source: Financial databases, industry reports
Recent M&A transaction multiples
Source: M&A databases, investment banking reports
Historical average multiples for the company
Source: Historical market data
Terminal Value Calculation:
         Terminal Value = Financial Metric_final × Selected Multiple


Discount Terminal Value to present:
	PV of Terminal Value = Terminal Value / (1 + WACC)^n
3. Error Margin for Terminal Value
Multiple methods comparison:
Calculate terminal value using both methods
Compare results to establish range
Sensitivity analysis:
Vary growth rate by ±0.5%, ±1%, ±1.5%
Vary multiple by ±1x, ±2x, ±3x
Document range of outcomes
Report error range:
      Terminal Value Range = Base Case Value ± Percentage Error
Typically ±15-25% for terminal value
Discount Rate Determination
Weighted Average Cost of Capital (WACC) for FCFF:
WACC = (E÷V) × Cost of Equity + (D÷V) × Cost of Debt × (1 - Tax Rate)
Where E=Equity value, D=Debt value, V=Total value (E+D)
Cost of Equity calculation methods:
Capital Asset Pricing Model (CAPM): Cost of Equity = Risk-free Rate + Beta × Market Risk Premium
Fama-French Three-Factor Model (incorporating size and value factors)
Arbitrage Pricing Theory (APT)
Dividend Discount Model
Risk-free rate: Typically the yield on 10-year government bonds
Beta calculation:
Regression of stock returns against market returns
Industry average betas
Fundamental beta based on operating leverage and financial leverage
Market risk premium: Historical average (4-7%) or implied from current market valuations
Cost of Debt:
Current yield on the company's bonds
Interest rates on recent debt issuances
Credit rating-based estimates
Step-by-Step WACC Calculation
Data sources:
Balance Sheet
Income Statement
Market Data Services (Bloomberg, Capital IQ)
Treasury Yield Curves
Credit Rating Reports
1. Cost of Equity (CAPM Method) Calculation
Determining Risk-Free Rate (Rf):
Use 10-year government bond yield
Source: Treasury Department website, financial data providers
Beta (β) Calculation:
Option 1: Regression analysis
Run regression: Stock Returns = α + β × Market Returns
Source: Historical stock and market index price data (min. 60 months)
Option 2: Use published beta
Source: Financial data providers (Bloomberg, Yahoo Finance)
Option 3: Industry average beta adjusted for leverage
Unlevered Beta = Levered Beta / [1 + (1 - Tax Rate) × (Debt/Equity)]
Re-lever using company's capital structure
Company Beta = Unlevered Beta × [1 + (1 - Tax Rate) × (Company's Debt/Equity)]
Source: Industry reports, company financial statements
Determining Market Risk Premium (MRP):
Historical average (4-7%)
Implied from current market conditions
Survey-based estimates
Source: Academic research, investment bank publications
Cost of Equity Calculation:
Cost of Equity = Rf + β × MRP
Size premium addition (if applicable):
For smaller companies (market cap < $2 billion)
Typically 1-3% additional premium
Source: Size premium studies (e.g., Ibbotson/Duff & Phelps)
2. Cost of Debt Calculation
Determining pre-tax cost of debt:
Option 1: Yield-to-maturity on outstanding bonds
Source: Bond pricing services, financial data providers
Option 2: Interest expense divided by total debt
Average Interest Rate = Interest Expense / Average Debt Balance
Source: Income Statement and Balance Sheet
Option 3: Credit-rating based estimate
Source: Credit rating agency publications (Moody's, S&P)
After-tax cost of debt calculation:
After-tax Cost of Debt = Pre-tax Cost of Debt × (1 - Tax Rate)
Tax Rate: Income Statement (Income Tax Expense / Income Before Tax)
3. WACC Calculation
Determining target capital structure:
Market value of equity
Source: Stock price × Shares outstanding
Market value of debt
Source: Balance Sheet or bond pricing services
Calculate weights
Equity Weight = Equity Value / (Equity Value + Debt Value)
Debt Weight = Debt Value / (Equity Value + Debt Value)


Calculating WACC:
WACC = (Equity Weight × Cost of Equity) + (Debt Weight × After-tax Cost of Debt)


4. Error Margin for Discount Rate
Sensitivity analysis:
Vary beta by ±0.2
Vary risk-free rate by ±0.5%
Vary market risk premium by ±1%
Document range of outcomes
Report error range:
WACC Range = Base Case WACC ± Error Margin
Typically ±1-2% for WACC
Monte Carlo simulation:
Assign probability distributions to key inputs
Run multiple iterations
Establish confidence intervals
95% Confidence Interval = Base Case WACC ± (1.96 × Standard Deviation)


Putting It All Together
Final DCF formula with error margins:
Intrinsic Value = Σ [FCF_t / (1 + WACC)^t] + [Terminal Value / (1 + WACC)^n] ± Error Margin
Where:
FCF_t = Free Cash Flow in year t
WACC = Weighted Average Cost of Capital (with range)
n = Number of years in explicit forecast
Terminal Value = Calculated using either perpetuity or multiple method (with range)
Error Margin = Combined uncertainty from all components
The final valuation should be presented as a range rather than a single point estimate to acknowledge the inherent uncertainty in the DCF methodology.




# Project Structure
Copydcf-stock-analyzer/
├── dcf_analyzer/             # Core analysis package
│   ├── __init__.py
│   ├── data_retrieval/       # Data acquisition modules
│   ├── models/               # Financial models
│   ├── utils/                # Helper functions
│   └── visualization/        # Chart generation
├── web_interface/            # Django web application
│   ├── dashboard/            # Main interface app
│   ├── templates/            # HTML templates
│   └── static/               # CSS, JS, images
├── scripts/                  # Utility scripts
├── tests/                    # Test suite
├── docs/                     # Documentation
├── config/                   # Configuration files
├── requirements.txt          # Python dependencies
├── manage.py                 # Django management script
└── README.md                 # This file

# Roadmap
TBA (To Be Addressed) 

# Contributing
Sage Markley: Finance
Daniel Lopez: Tech
Email me at Lopezklu@yahoo.com if you would like to contribute!

# Fork the repository
Create your feature branch (git checkout -b feature/amazing-feature)
Commit your changes (git commit -m 'Add some amazing feature')
Push to the branch (git push origin feature/amazing-feature)
Open a Pull Request

# License
FAÑYE LLC.

# Acknowledgments
Financial models based on industry-standard DCF methodology
Inspired by professional equity research practices
Special thanks to the open-source financial analysis community
