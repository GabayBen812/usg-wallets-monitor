# USG Wallet Monitor - README

## Overview

This is a standalone monitoring system that detects new USG (U.S. Government) wallets on the Arkham Intelligence platform and sends notifications to your Discord channel via webhook.

## Features

- **Web Scraping**: Uses web scraping to detect new USG wallets without requiring official API keys
- **Discord Notifications**: Sends detailed alerts to your Discord channel when new wallets are detected
- **Customizable Settings**: Configure polling intervals, notification preferences, and more
- **Standalone Operation**: Can be run as a one-time check or as a continuous service
- **Easy Deployment**: Simple setup for running on your own VM

## Requirements

- Python 3.6+
- Required Python packages:
  - requests
  - beautifulsoup4
  - python-dateutil

## Installation

1. Clone or download this repository to your VM
2. Install required packages:
   ```
   pip install -r requirements.txt
   ```
3. Configure your Discord webhook URL in `config.ini`

## Configuration

Edit the `config.ini` file to customize your settings:

```ini
[API]
base_url = https://intel.arkm.com
use_unofficial_api = True

[MONITORING]
polling_interval_hours = 24
entity_id = usg

[NOTIFICATION]
discord_webhook = https://discord.com/api/webhooks/your/webhook/url
discord_enabled = True
enable_email = False
email_recipients = 
smtp_server = 
smtp_port = 587
smtp_username = 
smtp_password = 
```

## Usage

### Running Manually

To run the monitor once:

```
python monitor_service.py --once
```

To run continuously with the default polling interval:

```
python monitor_service.py
```

### Installing as a Service

To install as a systemd service for continuous operation:

```
chmod +x install_service.sh
./install_service.sh
```

Then follow the instructions displayed to complete the installation.

## How It Works

1. The system scrapes the Arkham Intelligence website to find USG wallet information
2. It compares the found wallets against a database of known wallets
3. When new wallets are detected, it sends a detailed notification to your Discord channel
4. The system continues monitoring at the configured interval

## Customization

- Adjust the polling interval in `config.ini` to check more or less frequently
- Modify the notification message format in `notification_system.py` if desired
- Add additional notification channels by extending the `NotificationSystem` class

## Troubleshooting

- Check the log files (`usg_monitor.log`, `notification.log`, and `usg_monitor_service.log`) for error messages
- Ensure your Discord webhook URL is correct and the webhook is properly configured in your Discord server
- If web scraping fails, the website structure may have changed - check for updates to this code

## License

This project is provided as-is with no warranty. Use at your own risk.
