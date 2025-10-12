#!/bin/bash
set -euo pipefail

VPN_CONFIG_PATH="${VPN_CONFIG_PATH:-/app/client.ovpn}"
OPENVPN_PID_FILE="/tmp/openvpn.pid"

cleanup() {
  if [ -f "$OPENVPN_PID_FILE" ]; then
    kill "$(cat "$OPENVPN_PID_FILE")" 2>/dev/null || true
  fi
}

trap cleanup EXIT

if [ ! -f "$VPN_CONFIG_PATH" ]; then
  echo "Не найден конфигурационный файл OpenVPN: $VPN_CONFIG_PATH" >&2
  exit 1
fi

echo "Запуск OpenVPN с конфигурацией $VPN_CONFIG_PATH"
openvpn --config "$VPN_CONFIG_PATH" --daemon --writepid "$OPENVPN_PID_FILE"

# Небольшая пауза для установления соединения
sleep 5

echo "Запуск веб-сервера"
exec gunicorn --bind 0.0.0.0:9003 "wsgi:app"
