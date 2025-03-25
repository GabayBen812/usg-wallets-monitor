#!/bin/bash

# Make monitor_service.py executable
chmod +x monitor_service.py

# Create a systemd service file
cat > usg_wallet_monitor.service << EOL
[Unit]
Description=USG Wallet Monitor Service
After=network.target

[Service]
Type=simple
User=\${USER}
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/monitor_service.py --config=$(pwd)/config.ini
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

echo "Created systemd service file: usg_wallet_monitor.service"
echo "To install as a system service, run:"
echo "sudo cp usg_wallet_monitor.service /etc/systemd/system/"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable usg_wallet_monitor.service"
echo "sudo systemctl start usg_wallet_monitor.service"
