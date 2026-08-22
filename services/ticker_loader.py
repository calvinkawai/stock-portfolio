# services/ticker_loader.py
import urllib.request
from sqlmodel import Session, select
from models.ticker import Ticker
from db.session import engine

NASDAQ_URL = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
OTHER_URL = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"

def seed_tickers_if_empty():
    with Session(engine) as session:
        # Check if already seeded
        existing = session.exec(select(Ticker)).first()
        if existing:
            return  # Already cached in SQLite!

        print("Downloading and caching ticker list from NASDAQ FTP...")
        tickers_to_add = []

        # 1. Parse NASDAQ Listed
        try:
            req = urllib.request.urlopen(NASDAQ_URL)
            lines = req.read().decode('utf-8').splitlines()
            for line in lines[1:]:  # Skip header
                parts = line.split('|')
                if len(parts) >= 2 and not parts[0].startswith("File Creation"):
                    symbol, name = parts[0], parts[1]
                    # Filter out test symbols
                    if parts[6] == 'N':  # 'N' means Not Test Issue
                        tickers_to_add.append(Ticker(symbol=symbol, name=name))
        except Exception as e:
            print(f"Error downloading NASDAQ tickers: {e}")

        # 2. Parse Other Listed (NYSE, AMEX, etc.)
        try:
            req = urllib.request.urlopen(OTHER_URL)
            lines = req.read().decode('utf-8').splitlines()
            for line in lines[1:]:  # Skip header
                parts = line.split('|')
                if len(parts) >= 2 and not parts[0].startswith("File Creation"):
                    symbol, name = parts[0], parts[1]
                    if parts[4] == 'N':  # Not Test Issue
                        tickers_to_add.append(Ticker(symbol=symbol, name=name))
        except Exception as e:
            print(f"Error downloading Other tickers: {e}")

        # Bulk insert into SQLite
        session.add_all(tickers_to_add)
        session.commit()
        print(f"Successfully cached {len(tickers_to_add)} tickers into SQLite!")
