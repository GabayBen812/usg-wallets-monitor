#!/usr/bin/env python3
import os
import time
import logging
import argparse
from datetime import datetime

# Import our modules
from wallet_monitor import WalletMonitor
from notification_system import NotificationSystem

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("usg_monitor_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("usg_monitor_service")

def run_monitor(config_file="config.ini", once=False, interval=None):
    """Run the USG wallet monitor service"""
    monitor = WalletMonitor()
    notification_system = NotificationSystem(config_file)
    
    # Get polling interval from config or command line
    if interval is None:
        from wallet_monitor import Config
        config = Config(config_file)
        interval = config.getint("MONITORING", "polling_interval_hours", fallback=24)
    
    logger.info(f"Starting USG wallet monitor service with polling interval of {interval} hours")
    
    while True:
        try:
            # Run the monitor
            logger.info("Running wallet monitor check")
            new_wallets = monitor.run()
            
            # Send notifications if new wallets were found
            if new_wallets:
                logger.info(f"Found {len(new_wallets)} new USG wallets, sending notifications")
                notification_success = notification_system.send_notification(new_wallets)
                
                if notification_success:
                    logger.info("Notifications sent successfully")
                else:
                    logger.warning("Failed to send notifications")
            else:
                logger.info("No new USG wallets detected")
            
            # Exit if running once
            if once:
                logger.info("Exiting after single run (--once flag specified)")
                break
            
            # Sleep until next check
            next_check = datetime.now().timestamp() + (interval * 3600)
            next_check_time = datetime.fromtimestamp(next_check).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Next check scheduled for {next_check_time} (in {interval} hours)")
            
            time.sleep(interval * 3600)
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, exiting")
            break
        except Exception as e:
            logger.error(f"Error in monitor service: {e}", exc_info=True)
            
            if once:
                break
                
            # Sleep for 5 minutes on error before retrying
            logger.info("Sleeping for 5 minutes before retrying")
            time.sleep(300)

def main():
    """Main entry point with command line argument parsing"""
    parser = argparse.ArgumentParser(description="USG Wallet Monitor Service")
    parser.add_argument("--config", default="config.ini", help="Path to configuration file")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, help="Polling interval in hours (overrides config)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Run the monitor
    run_monitor(config_file=args.config, once=args.once, interval=args.interval)

if __name__ == "__main__":
    main()
