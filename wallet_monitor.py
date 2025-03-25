import requests
import sqlite3
import json
import time
import logging
from datetime import datetime
import os
import configparser
import re
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("usg_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("usg_wallet_monitor")

class Config:
    """Configuration manager for the USG Wallet Monitor"""
    
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # Create default configuration if file doesn't exist
        if not os.path.exists(config_file):
            self._create_default_config()
        
        self.config.read(config_file)
    
    def _create_default_config(self):
        """Create a default configuration file"""
        self.config["API"] = {
            "base_url": "https://intel.arkm.com",
            "use_unofficial_api": "True"
        }
        
        self.config["MONITORING"] = {
            "polling_interval_hours": "24",
            "entity_id": "usg"
        }
        
        self.config["NOTIFICATION"] = {
            "discord_webhook": "",
            "enable_email": "False",
            "email_recipients": "",
            "smtp_server": "",
            "smtp_port": "587",
            "smtp_username": "",
            "smtp_password": ""
        }
        
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        
        logger.info(f"Created default configuration file: {self.config_file}")
    
    def get(self, section, key, fallback=None):
        """Get a configuration value"""
        return self.config.get(section, key, fallback=fallback)
    
    def getboolean(self, section, key, fallback=None):
        """Get a boolean configuration value"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def getint(self, section, key, fallback=None):
        """Get an integer configuration value"""
        return self.config.getint(section, key, fallback=fallback)


class Database:
    """Database manager for the USG Wallet Monitor"""
    
    def __init__(self, db_file="usg_wallets.db"):
        self.db_file = db_file
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_file}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.conn.cursor()
            
            # Table for storing wallet addresses
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                first_transaction TEXT,
                label TEXT,
                balance REAL,
                raw_data TEXT
            )
            ''')
            
            # Table for storing API responses
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            ''')
            
            self.conn.commit()
            logger.info("Database tables created/verified")
        except sqlite3.Error as e:
            logger.error(f"Database table creation error: {e}")
            raise
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def save_api_response(self, endpoint, response):
        """Save an API response to the database"""
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now().isoformat()
            
            cursor.execute(
                "INSERT INTO api_responses (endpoint, response, timestamp) VALUES (?, ?, ?)",
                (endpoint, json.dumps(response), timestamp)
            )
            
            self.conn.commit()
            logger.info(f"Saved API response for endpoint: {endpoint}")
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving API response: {e}")
            raise
    
    def get_latest_api_response(self, endpoint):
        """Get the latest API response for a specific endpoint"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(
                "SELECT response FROM api_responses WHERE endpoint = ? ORDER BY id DESC LIMIT 1",
                (endpoint,)
            )
            
            row = cursor.fetchone()
            if row:
                return json.loads(row['response'])
            return None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving API response: {e}")
            raise
    
    def get_known_wallet_addresses(self):
        """Get a list of all known wallet addresses"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT address FROM wallets")
            
            return [row['address'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving wallet addresses: {e}")
            raise
    
    def save_wallet(self, address, chain, first_seen, first_transaction=None, label=None, balance=None, raw_data=None):
        """Save a wallet to the database"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO wallets 
                (address, chain, first_seen, first_transaction, label, balance, raw_data) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (address, chain, first_seen, first_transaction, label, balance, 
                 json.dumps(raw_data) if raw_data else None)
            )
            
            self.conn.commit()
            logger.info(f"Saved wallet: {address}")
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving wallet: {e}")
            raise


class ArkhamAPI:
    """Interface for the Arkham Intelligence API using web scraping for unofficial access"""
    
    def __init__(self, config):
        self.config = config
        self.base_url = config.get("API", "base_url")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
    
    def get_entity_history(self, entity_id):
        """Get history for a specific entity using web scraping"""
        url = f"{self.base_url}/explorer/entity/{entity_id}"
        
        try:
            logger.info(f"Scraping entity history for: {entity_id}")
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract wallet data from the page
            wallets = self._extract_wallets_from_page(soup)
            
            # Create a structured response similar to what an API might return
            history_data = {
                "data": {
                    "entity_id": entity_id,
                    "wallets": wallets,
                    "source": "web_scraping"
                }
            }
            
            return history_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Web scraping error: {e}")
            return None
    
    def get_entity_portfolio(self, entity_id):
        """Get portfolio data for a specific entity using web scraping"""
        # For simplicity, we'll use the same data as history since we're scraping
        # In a real implementation, you might want to scrape a different page or section
        return self.get_entity_history(entity_id)
    
    def _extract_wallets_from_page(self, soup):
        """Extract wallet information from the BeautifulSoup object"""
        wallets = []
        
        # Look for wallet addresses in the page
        # This is a simplified approach - in production, you'd need more robust parsing
        wallet_elements = soup.find_all('a', href=re.compile(r'/explorer/address/'))
        
        for element in wallet_elements:
            address = element.get('href').split('/explorer/address/')[-1]
            
            # Get additional data if available
            parent_div = element.find_parent('div', class_=re.compile(r'.*card.*'))
            
            chain = "unknown"
            balance = 0
            label = "USG Wallet"
            
            # Try to extract chain information
            chain_element = None
            if parent_div:
                chain_element = parent_div.find(string=re.compile(r'(ETH|BTC|USDT|SOL)', re.IGNORECASE))
            
            if chain_element:
                chain_match = re.search(r'(ETH|BTC|USDT|SOL)', chain_element, re.IGNORECASE)
                if chain_match:
                    chain = chain_match.group(0).upper()
            
            # Try to extract balance information
            balance_element = None
            if parent_div:
                balance_element = parent_div.find(string=re.compile(r'\$[\d,.]+'))
            
            if balance_element:
                balance_match = re.search(r'\$([\d,.]+)', balance_element)
                if balance_match:
                    try:
                        balance = float(balance_match.group(1).replace(',', ''))
                    except ValueError:
                        balance = 0
            
            # Create wallet object
            wallet = {
                "address": address,
                "chain": chain,
                "balance": balance,
                "label": label,
                "first_seen": datetime.now().isoformat(),
                "first_transaction": None
            }
            
            wallets.append(wallet)
        
        # If no wallets found through direct parsing, try extracting from script tags
        if not wallets:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'wallets' in script.string:
                    # Try to extract wallet data from JavaScript
                    matches = re.findall(r'"address":"([^"]+)"', script.string)
                    for address in matches:
                        wallet = {
                            "address": address,
                            "chain": "unknown",
                            "balance": 0,
                            "label": "USG Wallet",
                            "first_seen": datetime.now().isoformat(),
                            "first_transaction": None
                        }
                        wallets.append(wallet)
        
        # Deduplicate wallets
        unique_wallets = []
        seen_addresses = set()
        for wallet in wallets:
            if wallet["address"] not in seen_addresses:
                seen_addresses.add(wallet["address"])
                unique_wallets.append(wallet)
        
        logger.info(f"Extracted {len(unique_wallets)} wallets from page")
        return unique_wallets


class WalletMonitor:
    """Main class for monitoring USG wallets"""
    
    def __init__(self):
        self.config = Config()
        self.db = Database()
        self.api = ArkhamAPI(self.config)
        self.entity_id = self.config.get("MONITORING", "entity_id")
    
    def run(self):
        """Run the monitoring process"""
        logger.info("Starting USG wallet monitoring process")
        
        # Get current data from API
        history_data = self.api.get_entity_history(self.entity_id)
        portfolio_data = self.api.get_entity_portfolio(self.entity_id)
        
        if not history_data and not portfolio_data:
            logger.error("Failed to retrieve data from web scraping")
            return []
        
        # Save API responses
        if history_data:
            self.db.save_api_response(f"/history/entity/{self.entity_id}", history_data)
        
        if portfolio_data and portfolio_data != history_data:
            self.db.save_api_response(f"/portfolio/entity/{self.entity_id}", portfolio_data)
        
        # Process the data to find new wallets
        new_wallets = self.process_data(history_data, portfolio_data)
        
        # Return the new wallets
        return new_wallets
    
    def process_data(self, history_data, portfolio_data):
        """Process API data to identify new wallets"""
        logger.info("Processing data to identify new wallets")
        
        # Get list of known wallet addresses
        known_addresses = set(self.db.get_known_wallet_addresses())
        new_wallets = []
        
        # Process wallets from history data
        if history_data and 'data' in history_data and 'wallets' in history_data['data']:
            for wallet in history_data['data']['wallets']:
                if 'address' in wallet and wallet['address'] not in known_addresses:
                    self._process_new_wallet(wallet, new_wallets, known_addresses)
        
        # Process wallets from portfolio data if different from history
        if portfolio_data and portfolio_data != history_data and 'data' in portfolio_data and 'wallets' in portfolio_data['data']:
            for wallet in portfolio_data['data']['wallets']:
                if 'address' in wallet and wallet['address'] not in known_addresses:
                    self._process_new_wallet(wallet, new_wallets, known_addresses)
        
        logger.info(f"Found {len(new_wallets)} new wallets")
        return new_wallets
    
    def _process_new_wallet(self, wallet, new_wallets, known_addresses):
        """Process a new wallet and add it to the database"""
        address = wallet['address']
        chain = wallet.get('chain', 'unknown')
        first_seen = wallet.get('first_seen', datetime.now().isoformat())
        first_transaction = wallet.get('first_transaction')
        label = wallet.get('label', 'USG Wallet')
        balance = wallet.get('balance', 0)
        
        logger.info(f"New wallet detected: {address} ({chain})")
        
        # Save to database
        self.db.save_wallet(
            address=address,
            chain=chain,
            first_seen=first_seen,
            first_transaction=first_transaction,
            label=label,
            balance=balance,
            raw_data=wallet
        )
        
        # Add to new wallets list and known addresses set
        new_wallets.append(wallet)
        known_addresses.add(address)


if __name__ == "__main__":
    monitor = WalletMonitor()
    new_wallets = monitor.run()
    
    if new_wallets:
        logger.info(f"Found {len(new_wallets)} new USG wallets")
        for wallet in new_wallets:
            logger.info(f"New wallet: {wallet['address']} ({wallet.get('chain', 'unknown')})")
    else:
        logger.info("No new USG wallets detected")
