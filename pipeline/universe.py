"""The chart universe: ~200 series in the spirit of Druckenmiller's daily scan.

Druckenmiller has said many times that he looks at ~200 charts a day, but he has
never published the list. This set is rebuilt from what he has said he watches:
liquidity and the Fed, the rate of change in rates, the dollar, credit, commodities,
sector and industry leadership, global markets, and the tape of bellwether stocks.

Each entry: (id, name, source, symbol, group, polarity, why)
  source   : "yf" (Yahoo Finance), "fred" (St. Louis Fed), "ratio" (a/b of two ids),
             "spread" (a-b of two ids), "netliq" (special)
  polarity : +1 rising is good for risk assets, -1 rising is bad for risk, 0 neutral
"""

GROUPS = [
    ("liquidity", "Liquidity & Fed"),
    ("rates", "Rates & Curve"),
    ("credit", "Credit & Stress"),
    ("fx", "Dollar & FX"),
    ("commod", "Commodities"),
    ("macro", "Economy"),
    ("us", "US Indices & Breadth"),
    ("sectors", "Sectors vs S&P"),
    ("industries", "Industries & Themes"),
    ("factors", "Factors & Ratios"),
    ("global", "Global Equities"),
    ("crypto", "Crypto"),
    ("stocks", "Bellwether Stocks"),
]

U = []


def add(id, name, src, sym, group, pol, why=""):
    U.append(dict(id=id, name=name, src=src, sym=sym, group=group, pol=pol, why=why))


# ---------------- Liquidity & Fed ----------------
add("WALCL", "Fed balance sheet", "fred", "WALCL", "liquidity", 1, "QE/QT: the tide under every asset")
add("WTREGEN", "Treasury General Account", "fred", "WTREGEN", "liquidity", -1, "TGA rebuilds drain reserves")
add("RRPONTSYD", "Reverse repo facility", "fred", "RRPONTSYD", "liquidity", -1, "Spare cash parked at the Fed")
add("NETLIQ", "Net liquidity (BS - TGA - RRP)", "netliq", "", "liquidity", 1, "Druck's core liquidity gauge")
add("WRESBAL", "Bank reserves", "fred", "WRESBAL", "liquidity", 1, "Scarce reserves = funding stress")
add("M2SL", "M2 money supply", "fred", "M2SL", "liquidity", 1, "Broad money growth")
add("DFF", "Fed funds effective", "fred", "DFF", "liquidity", -1, "Policy rate")
add("SOFR", "SOFR", "fred", "SOFR", "liquidity", -1, "Overnight funding rate")
add("NFCI", "Chicago Fed financial conditions", "fred", "NFCI", "liquidity", -1, "Above 0 = tighter than average")
add("STLFSI4", "St. Louis Fed stress index", "fred", "STLFSI4", "liquidity", -1, "Composite market stress")

# ---------------- Rates & Curve ----------------
add("DGS3MO", "3-month T-bill", "fred", "DGS3MO", "rates", -1, "Where the market thinks the Fed is")
add("DGS2", "2-year Treasury", "fred", "DGS2", "rates", -1, "Fed expectations for the next 2 years")
add("DGS5", "5-year Treasury", "fred", "DGS5", "rates", -1, "")
add("DGS10", "10-year Treasury", "fred", "DGS10", "rates", -1, "Discount rate for all assets")
add("DGS30", "30-year Treasury", "fred", "DGS30", "rates", -1, "Term premium / fiscal worry")
add("T10Y2Y", "2s10s curve", "fred", "T10Y2Y", "rates", 0, "Bear steepening = fiscal stress")
add("T10Y3M", "3m10y curve", "fred", "T10Y3M", "rates", 0, "Classic recession signal")
add("DFII10", "10-year real yield (TIPS)", "fred", "DFII10", "rates", -1, "The real cost of money; gold hates it")
add("T5YIE", "5-year breakeven inflation", "fred", "T5YIE", "rates", -1, "Market's inflation expectations")
add("T10YIE", "10-year breakeven inflation", "fred", "T10YIE", "rates", -1, "")
add("MORTGAGE30US", "30-year mortgage rate", "fred", "MORTGAGE30US", "rates", -1, "Housing affordability")
add("TLT", "20+yr Treasury ETF", "yf", "TLT", "rates", 0, "Long bond price")
add("MOVE", "MOVE (bond volatility)", "yf", "^MOVE", "rates", -1, "Bond vol leads equity vol")

# ---------------- Credit & Stress ----------------
add("HYOAS", "High-yield spread", "fred", "BAMLH0A0HYM2", "credit", -1, "Credit leads equities at turns")
add("IGOAS", "Investment-grade spread", "fred", "BAMLC0A0CM", "credit", -1, "")
add("CCCOAS", "CCC spread", "fred", "BAMLH0A3HYC", "credit", -1, "Weakest borrowers crack first")
add("BBBOAS", "BBB spread", "fred", "BAMLC0A4CBBB", "credit", -1, "")
add("HYG", "High-yield bond ETF", "yf", "HYG", "credit", 1, "")
add("LQD", "IG corporate bond ETF", "yf", "LQD", "credit", 0, "")
add("BKLN", "Leveraged loans ETF", "yf", "BKLN", "credit", 1, "Floating-rate risk appetite")
add("HYG_IEF", "Junk vs Treasuries (HYG/IEF)", "ratio", "HYG/IEF", "credit", 1, "Risk appetite in bonds")
add("VIX", "VIX", "yf", "^VIX", "credit", -1, "Equity fear gauge")
add("VIX3M", "VIX 3-month", "yf", "^VIX3M", "credit", -1, "")
add("VIXTS", "VIX / VIX3M (term structure)", "ratio", "VIX/VIX3M", "credit", -1, "Above 1 = acute panic")
add("SKEW", "SKEW index", "yf", "^SKEW", "credit", -1, "Tail-hedge demand")
add("IEF", "7-10yr Treasury ETF", "yf", "IEF", "credit", 0, "")

# ---------------- Dollar & FX ----------------
add("DXY", "US Dollar index", "yf", "DX-Y.NYB", "fx", -1, "Strong dollar = global tightening")
add("EURUSD", "Euro", "yf", "EURUSD=X", "fx", 1, "")
add("USDJPY", "USD/JPY", "yf", "JPY=X", "fx", 0, "Yen carry trade barometer")
add("USDCNY", "USD/CNY", "yf", "CNY=X", "fx", -1, "China's FX policy")
add("GBPUSD", "British pound", "yf", "GBPUSD=X", "fx", 1, "")
add("AUDUSD", "Australian dollar", "yf", "AUDUSD=X", "fx", 1, "China/commodity proxy")
add("USDCAD", "USD/CAD", "yf", "CAD=X", "fx", -1, "")
add("USDCHF", "USD/CHF", "yf", "CHF=X", "fx", 0, "Haven flows")
add("USDMXN", "USD/MXN", "yf", "MXN=X", "fx", -1, "EM carry favorite")
add("USDBRL", "USD/BRL", "yf", "BRL=X", "fx", -1, "")
add("USDKRW", "USD/KRW", "yf", "KRW=X", "fx", -1, "Global trade/semis currency")
add("USDINR", "USD/INR", "yf", "INR=X", "fx", -1, "")
add("CEW", "EM currency basket (CEW)", "yf", "CEW", "fx", 1, "")
add("AUDJPY", "AUD/JPY (risk cross)", "yf", "AUDJPY=X", "fx", 1, "Pure risk-on/off cross")

# ---------------- Commodities ----------------
add("WTI", "WTI crude", "yf", "CL=F", "commod", 0, "Growth signal, but a spike is a tax")
add("BRENT", "Brent crude", "yf", "BZ=F", "commod", 0, "")
add("NATGAS", "Natural gas", "yf", "NG=F", "commod", 0, "")
add("GASOLINE", "RBOB gasoline", "yf", "RB=F", "commod", -1, "Consumer tax")
add("COPPER", "Copper", "yf", "HG=F", "commod", 1, "Dr. Copper: global growth + electrification")
add("GOLD", "Gold", "yf", "GC=F", "commod", 0, "Distrust of fiat / central-bank buying")
add("SILVER", "Silver", "yf", "SI=F", "commod", 0, "")
add("PLATINUM", "Platinum", "yf", "PL=F", "commod", 0, "")
add("CORN", "Corn", "yf", "ZC=F", "commod", 0, "")
add("WHEAT", "Wheat", "yf", "ZW=F", "commod", 0, "")
add("SOYBEAN", "Soybeans", "yf", "ZS=F", "commod", 0, "")
add("CATTLE", "Live cattle", "yf", "LE=F", "commod", 0, "")
add("URANIUM", "Uranium miners (URA)", "yf", "URA", "commod", 0, "Nuclear/AI power build-out")
add("LITHIUM", "Lithium & battery (LIT)", "yf", "LIT", "commod", 0, "")
add("DBC", "Broad commodities (DBC)", "yf", "DBC", "commod", 0, "")
add("CU_AU", "Copper / gold", "ratio", "COPPER/GOLD", "commod", 1, "Growth vs fear; tracks the 10y")
add("AU_AG", "Gold / silver", "ratio", "GOLD/SILVER", "commod", -1, "Rising = defensive")
add("OIL_AU", "Oil / gold", "ratio", "WTI/GOLD", "commod", 0, "")

# ---------------- Economy ----------------
add("ICSA", "Initial jobless claims", "fred", "ICSA", "macro", -1, "Most timely labor data")
add("CCSA", "Continuing claims", "fred", "CCSA", "macro", -1, "How hard it is to get rehired")
add("UNRATE", "Unemployment rate", "fred", "UNRATE", "macro", -1, "Sahm rule watch")
add("PAYEMS", "Nonfarm payrolls", "fred", "PAYEMS", "macro", 1, "")
add("CPI", "CPI (index)", "fred", "CPIAUCSL", "macro", -1, "")
add("CORECPI", "Core CPI (index)", "fred", "CPILFESL", "macro", -1, "")
add("COREPCE", "Core PCE (index)", "fred", "PCEPILFE", "macro", -1, "The Fed's target")
add("INDPRO", "Industrial production", "fred", "INDPRO", "macro", 1, "")
add("RETAIL", "Retail sales", "fred", "RSAFS", "macro", 1, "")
add("HOUST", "Housing starts", "fred", "HOUST", "macro", 1, "")
add("PERMIT", "Building permits", "fred", "PERMIT", "macro", 1, "Leads starts")
add("UMCSENT", "Consumer sentiment (UMich)", "fred", "UMCSENT", "macro", 1, "")
add("TCU", "Capacity utilization", "fred", "TCU", "macro", 1, "")
add("JTSJOL", "Job openings (JOLTS)", "fred", "JTSJOL", "macro", 1, "")

# ---------------- US Indices & Breadth ----------------
add("SPX", "S&P 500", "yf", "^GSPC", "us", 1, "")
add("NDX", "Nasdaq 100", "yf", "^NDX", "us", 1, "")
add("DJI", "Dow Jones", "yf", "^DJI", "us", 1, "")
add("RUT", "Russell 2000", "yf", "^RUT", "us", 1, "Rate-sensitive, domestic economy")
add("DJT", "Dow Transports", "yf", "^DJT", "us", 1, "Dow theory: goods actually moving")
add("SPW", "S&P equal-weight (RSP)", "yf", "RSP", "us", 1, "")
add("RSP_SPY", "Breadth: equal-weight / cap-weight", "ratio", "SPW/SPY", "us", 1, "Rising = broad participation")
add("IWM_SPY", "Small caps / S&P", "ratio", "IWM/SPY", "us", 1, "")
add("SPY", "SPY", "yf", "SPY", "us", 1, "")
add("QQQ", "QQQ", "yf", "QQQ", "us", 1, "")
add("IWM", "IWM", "yf", "IWM", "us", 1, "")
add("MDY", "S&P midcap", "yf", "MDY", "us", 1, "")
add("QQQ_SPY", "Nasdaq / S&P", "ratio", "QQQ/SPY", "us", 0, "Growth leadership")

# ---------------- Sectors (price; relative computed vs SPY) ----------------
for t, n in [("XLK", "Technology"), ("XLF", "Financials"), ("XLE", "Energy"), ("XLV", "Health care"),
             ("XLI", "Industrials"), ("XLY", "Consumer discretionary"), ("XLP", "Consumer staples"),
             ("XLU", "Utilities"), ("XLB", "Materials"), ("XLRE", "Real estate"), ("XLC", "Communications")]:
    add(t, n + f" ({t})", "yf", t, "sectors", 1 if t not in ("XLP", "XLU") else 0, "")

# ---------------- Industries & Themes ----------------
for t, n, w in [
    ("SMH", "Semiconductors", "The AI capex cycle's heartbeat"),
    ("IGV", "Software", "AI winner or AI victim?"),
    ("KRE", "Regional banks", "Credit creation for Main Street"),
    ("KBE", "Banks", ""),
    ("XHB", "Homebuilders (XHB)", "Leads the cycle"),
    ("ITB", "Home construction (ITB)", ""),
    ("XRT", "Retail", "Consumer health"),
    ("IYT", "Transports", ""),
    ("JETS", "Airlines", "Discretionary travel demand"),
    ("XOP", "Oil & gas E&P", ""),
    ("OIH", "Oil services", ""),
    ("XME", "Metals & mining", ""),
    ("GDX", "Gold miners", ""),
    ("GDXJ", "Junior gold miners", ""),
    ("COPX", "Copper miners", ""),
    ("TAN", "Solar", ""),
    ("ICLN", "Clean energy", ""),
    ("IBB", "Biotech (large)", ""),
    ("XBI", "Biotech (small)", "Risk appetite for duration"),
    ("IHI", "Medical devices", ""),
    ("ITA", "Aerospace & defense", "Re-armament cycle"),
    ("PAVE", "Infrastructure", ""),
    ("GRID", "Grid infrastructure", "Power demand from data centers"),
    ("KWEB", "China internet", ""),
    ("ARKK", "Speculative growth (ARKK)", "Froth gauge"),
    ("IPO", "Recent IPOs", "Risk appetite for new paper"),
    ("KIE", "Insurance", ""),
    ("IAI", "Brokers & exchanges", "Activity levels"),
    ("XTN", "Trucking & transport (eq wt)", ""),
    ("SOXX", "Semis (SOXX)", ""),
    ("CIBR", "Cybersecurity", ""),
    ("BOTZ", "Robotics & AI", ""),
    ("NLR", "Nuclear energy", ""),
    ("REMX", "Rare earths", "China supply chokepoint"),
]:
    add(t, n, "yf", t, "industries", 1, w)

# ---------------- Factors & Ratios ----------------
add("XLY_XLP", "Discretionary / staples", "ratio", "XLY/XLP", "factors", 1, "Consumer risk appetite")
add("XLI_XLU", "Industrials / utilities", "ratio", "XLI/XLU", "factors", 1, "Cyclical vs defensive")
add("SPHB_SPLV", "High beta / low vol", "ratio", "SPHB/SPLV", "factors", 1, "Pure risk appetite")
add("SMH_SPY", "Semis / S&P", "ratio", "SMH/SPY", "factors", 1, "AI leadership")
add("KRE_SPY", "Regional banks / S&P", "ratio", "KRE/SPY", "factors", 1, "Credit cycle")
add("IYT_SPY", "Transports / S&P", "ratio", "IYT/SPY", "factors", 1, "")
add("XHB_SPY", "Homebuilders / S&P", "ratio", "XHB/SPY", "factors", 1, "")
add("XRT_SPY", "Retail / S&P", "ratio", "XRT/SPY", "factors", 1, "")
add("IGV_SMH", "Software / semis", "ratio", "IGV/SMH", "factors", 0, "")
add("EEM_SPY", "Emerging / US", "ratio", "EEM/SPY", "factors", 0, "Dollar-driven rotation")
add("EFA_SPY", "Developed ex-US / US", "ratio", "EFA/SPY", "factors", 0, "")
add("GDX_GOLD", "Gold miners / gold", "ratio", "GDX/GLD", "factors", 0, "Miners confirm gold?")
add("IWF_IWD", "Growth / value", "ratio", "IWF/IWD", "factors", 0, "")
add("MTUM", "Momentum factor", "yf", "MTUM", "factors", 1, "")
add("QUAL", "Quality factor", "yf", "QUAL", "factors", 1, "")
add("USMV", "Min-vol factor", "yf", "USMV", "factors", 0, "")
add("VLUE", "Value factor", "yf", "VLUE", "factors", 1, "")
add("SPHB", "High beta", "yf", "SPHB", "factors", 1, "")
add("SPLV", "Low vol", "yf", "SPLV", "factors", 0, "")
add("IWF", "Russell growth", "yf", "IWF", "factors", 1, "")
add("IWD", "Russell value", "yf", "IWD", "factors", 1, "")
add("GLD", "Gold ETF", "yf", "GLD", "factors", 0, "")
add("EEM", "Emerging markets", "yf", "EEM", "factors", 1, "")
add("EFA", "Developed ex-US", "yf", "EFA", "factors", 1, "")

# ---------------- Global equities ----------------
for t, n, w in [
    ("^STOXX50E", "Euro Stoxx 50", ""), ("^GDAXI", "Germany DAX", "German fiscal bazooka"),
    ("^FTSE", "UK FTSE 100", ""), ("^FCHI", "France CAC 40", ""),
    ("^N225", "Japan Nikkei 225", "Corporate reform + yen"), ("^HSI", "Hang Seng", ""),
    ("000001.SS", "Shanghai Composite", ""), ("^KS11", "Korea KOSPI", "Memory/semis cycle"),
    ("^TWII", "Taiwan TAIEX", "TSMC & the AI supply chain"), ("^BSESN", "India Sensex", ""),
    ("^BVSP", "Brazil Bovespa", ""), ("^MXX", "Mexico IPC", "Nearshoring"),
    ("^AXJO", "Australia ASX 200", ""), ("^GSPTSE", "Canada TSX", ""),
    ("FXI", "China large caps (FXI)", ""), ("EWZ", "Brazil ETF", ""), ("INDA", "India ETF", ""),
    ("EWJ", "Japan ETF", ""), ("EWY", "Korea ETF", ""), ("EWT", "Taiwan ETF", ""),
    ("EWW", "Mexico ETF", ""), ("VNM", "Vietnam", ""), ("ARGT", "Argentina", "Milei reform trade"),
    ("EZA", "South Africa", ""), ("TUR", "Turkey", ""), ("EWG", "Germany ETF", ""),
    ("EWU", "UK ETF", ""), ("EWP", "Spain ETF", ""), ("EWI", "Italy ETF", ""), ("KSA", "Saudi Arabia", ""),
    ("EPOL", "Poland", ""), ("GREK", "Greece", ""),
]:
    add(t.replace("^", "").replace(".SS", "SS"), n, "yf", t, "global", 1, w)

# ---------------- Crypto ----------------
add("BTC", "Bitcoin", "yf", "BTC-USD", "crypto", 1, "Liquidity-sensitive risk asset")
add("ETH", "Ether", "yf", "ETH-USD", "crypto", 1, "")
add("SOL", "Solana", "yf", "SOL-USD", "crypto", 1, "")
add("IBIT", "Bitcoin ETF (IBIT)", "yf", "IBIT", "crypto", 1, "")
add("COIN", "Coinbase", "yf", "COIN", "crypto", 1, "")
add("MSTR", "Strategy (MSTR)", "yf", "MSTR", "crypto", 1, "")
add("ETH_BTC", "Ether / bitcoin", "ratio", "ETH/BTC", "crypto", 1, "Crypto risk appetite")

# ---------------- Bellwether stocks ----------------
for t, w in [
    ("NVDA", "AI capex bellwether"), ("MSFT", ""), ("AAPL", ""), ("AMZN", ""), ("GOOGL", ""), ("META", ""),
    ("TSLA", ""), ("AVGO", "Custom AI silicon"), ("TSM", "Foundry monopoly"), ("ASML", ""), ("AMD", ""),
    ("MU", "Memory cycle"), ("ORCL", "AI cloud debt build-out"), ("PLTR", "Retail/AI froth"),
    ("VST", "AI power demand"), ("CEG", "Nuclear power"), ("GEV", "Grid & turbines"), ("ETN", "Electrical equipment"),
    ("JPM", "Credit & the consumer"), ("GS", "Capital markets activity"), ("BX", "Private credit"),
    ("CAT", "Global capex"), ("DE", "Farm economy"), ("FDX", "Global shipping volumes"), ("UPS", ""),
    ("HD", "Housing turnover"), ("DHI", "New homes"), ("WMT", "Consumer trade-down"), ("COST", ""),
    ("TGT", "Middle-income consumer"), ("NKE", "Discretionary / China"), ("MCD", "Low-income consumer"),
    ("XOM", ""), ("CVX", ""), ("FCX", "Copper"), ("NEM", "Gold"), ("LLY", "GLP-1"), ("UNH", "Managed care"),
    ("NFLX", ""), ("BA", ""), ("LMT", ""), ("UBER", ""),
]:
    add(t, t, "yf", t, "stocks", 1, w)

