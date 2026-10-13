#!/usr/bin/env bash
set -euo pipefail

sudo tee /etc/systemd/system/lai-demo.service >/dev/null <<'SERVICE'
[Unit]
Description=LAI safe demonstration service

[Service]
Type=simple
ExecStart=/bin/sh -c 'while true; do sleep 60; done'
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE
sudo systemctl daemon-reload
sudo systemctl enable --now lai-demo.service
echo "Add lai-demo to ALLOWED_SERVICES before using it in the dashboard."
