#!/bin/bash

# Loop over all arguments passed to the script
for arg in "$@"; do
  # Check if the argument starts with --user=
  if [[ $arg == --user=* ]]; then
    # Extract the value after the '='
    user="${arg#--user=}"
    echo "User: $user"
  fi
done

# Check if the user variable is set
if [ -z "$user" ]; then
  echo "Error: User not specified."
  exit 1
fi

# Change the default target to multi-user
sudo -S systemctl set-default multi-user.target

# Create systemd directory if it doesn't exist
sudo -S mkdir -p /etc/systemd/system/

# Create the systemd service file with the correct user value
cat <<EOF | sudo tee /etc/systemd/system/synapse.service
[Unit]
Description=Synapse Runtime
After=network.target
StartLimitInterval=0

[Service]
User=$user
Type=simple
WorkingDirectory=/home/$user/Synapse/
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=1
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

# Set the correct permissions for the service file
sudo -S chmod 640 /etc/systemd/system/synapse.service

# Reload systemd to apply changes
sudo -S systemctl daemon-reload

# Enable the synapse service to start on boot
sudo -S systemctl enable synapse

echo "Synapse service has been set up and enabled."
