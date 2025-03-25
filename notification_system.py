import requests
import json
import logging
from datetime import datetime
import os
import configparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("notification.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("usg_notification_system")

class Config:
    """Configuration manager for the Notification System"""
    
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # Create default configuration if file doesn't exist
        if not os.path.exists(config_file):
            self._create_default_config()
        
        self.config.read(config_file)
    
    def _create_default_config(self):
        """Create a default configuration file"""
        self.config["NOTIFICATION"] = {
            "discord_webhook": "",
            "discord_enabled": "True",
            "enable_email": "False",
            "email_recipients": "",
            "email_sender": "",
            "smtp_server": "",
            "smtp_port": "587",
            "smtp_username": "",
            "smtp_password": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "telegram_enabled": "False"
        }
        
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        
        logger.info(f"Created default notification configuration file: {self.config_file}")
    
    def get(self, section, key, fallback=None):
        """Get a configuration value"""
        return self.config.get(section, key, fallback=fallback)
    
    def getboolean(self, section, key, fallback=None):
        """Get a boolean configuration value"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def getint(self, section, key, fallback=None):
        """Get an integer configuration value"""
        return self.config.getint(section, key, fallback=fallback)


class NotificationSystem:
    """Notification system for the USG Wallet Monitor"""
    
    def __init__(self, config_file="config.ini"):
        self.config = Config(config_file)
    
    def send_notification(self, wallets):
        """Send notifications about new wallets through configured channels"""
        if not wallets:
            logger.info("No new wallets to notify about")
            return
        
        # Create notification message
        message = self._create_message(wallets)
        
        # Send through each enabled channel
        success = False
        
        if self.config.getboolean("NOTIFICATION", "discord_enabled", fallback=True):
            discord_success = self._send_discord(message, wallets)
            success = success or discord_success
        
        if self.config.getboolean("NOTIFICATION", "enable_email", fallback=False):
            email_success = self._send_email(message, wallets)
            success = success or email_success
            
        if self.config.getboolean("NOTIFICATION", "telegram_enabled", fallback=False):
            telegram_success = self._send_telegram(message, wallets)
            success = success or telegram_success
        
        return success
    
    def _create_message(self, wallets):
        """Create a notification message for the new wallets"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = f"🚨 **NEW USG WALLET ALERT** 🚨\n\n"
        message += f"Detected {len(wallets)} new USG wallet(s) at {timestamp}\n\n"
        
        for i, wallet in enumerate(wallets, 1):
            message += f"**Wallet #{i}**\n"
            message += f"• Address: `{wallet['address']}`\n"
            message += f"• Chain: {wallet['chain']}\n"
            
            if wallet.get('first_transaction'):
                message += f"• First Transaction: {wallet['first_transaction']}\n"
            
            if wallet.get('label'):
                message += f"• Label: {wallet['label']}\n"
            
            if wallet.get('balance') is not None:
                message += f"• Balance: {wallet['balance']}\n"
            
            message += f"• Link: https://intel.arkm.com/explorer/address/{wallet['address']}\n\n"
        
        return message
    
    def _send_discord(self, message, wallets):
        """Send notification to Discord webhook"""
        webhook_url = self.config.get("NOTIFICATION", "discord_webhook")
        
        if not webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False
        
        try:
            payload = {
                "content": message,
                "username": "USG Wallet Monitor",
                "avatar_url": "https://cryptologos.cc/logos/usd-coin-usdc-logo.png"
            }
            
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
                return True
            else:
                logger.error(f"Failed to send Discord notification: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False
    
    def _send_email(self, message, wallets):
        """Send notification via email"""
        smtp_server = self.config.get("NOTIFICATION", "smtp_server")
        smtp_port = self.config.getint("NOTIFICATION", "smtp_port", fallback=587)
        smtp_username = self.config.get("NOTIFICATION", "smtp_username")
        smtp_password = self.config.get("NOTIFICATION", "smtp_password")
        sender = self.config.get("NOTIFICATION", "email_sender")
        recipients_str = self.config.get("NOTIFICATION", "email_recipients")
        
        if not all([smtp_server, smtp_username, smtp_password, sender, recipients_str]):
            logger.warning("Email configuration incomplete")
            return False
        
        recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
        
        if not recipients:
            logger.warning("No email recipients configured")
            return False
        
        try:
            # Create email
            msg = MIMEMultipart()
            msg['Subject'] = f"🚨 NEW USG WALLET ALERT - {len(wallets)} new wallet(s) detected"
            msg['From'] = sender
            msg['To'] = ", ".join(recipients)
            
            # Convert Discord-style message to HTML
            html_message = message.replace("\n", "<br>")
            html_message = html_message.replace("**", "<strong>", 1)
            html_message = html_message.replace("**", "</strong>", 1)
            html_message = html_message.replace("**", "<strong>")
            html_message = html_message.replace("**", "</strong>")
            html_message = html_message.replace("`", "<code>", 1)
            html_message = html_message.replace("`", "</code>", 1)
            html_message = html_message.replace("`", "<code>")
            html_message = html_message.replace("`", "</code>")
            
            # Attach HTML and plain text versions
            msg.attach(MIMEText(message, 'plain'))
            msg.attach(MIMEText(html_message, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def _send_telegram(self, message, wallets):
        """Send notification via Telegram"""
        bot_token = self.config.get("NOTIFICATION", "telegram_bot_token")
        chat_id = self.config.get("NOTIFICATION", "telegram_chat_id")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram configuration incomplete")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, data=payload)
            
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
                return True
            else:
                logger.error(f"Failed to send Telegram notification: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False


def main():
    """Test the notification system with sample data"""
    sample_wallets = [
        {
            "address": "bc1qwuferz7fax39tru66ykrxkn99msem53ph7g6t9",
            "chain": "BTC",
            "first_seen": "2025-03-25T23:00:00",
            "first_transaction": "2025-03-25T22:45:00",
            "label": "USG",
            "balance": 19.94
        }
    ]
    
    notification_system = NotificationSystem()
    success = notification_system.send_notification(sample_wallets)
    
    if success:
        logger.info("Notification test completed successfully")
    else:
        logger.error("Notification test failed")


if __name__ == "__main__":
    main()
