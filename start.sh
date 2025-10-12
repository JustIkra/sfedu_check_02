#!/bin/bash
set -euo pipefail

VPN_CONFIG_PATH="${VPN_CONFIG_PATH:-/app/client.ovpn}"
OPENVPN_PID_FILE="/tmp/openvpn.pid"

PROXY_HOST="${PROXY_HOST:-45.147.196.230}"
PROXY_PORT="${PROXY_PORT:-47448}"
PROXY_USER="${PROXY_USER:-proxy_user}"
PROXY_PASS="${PROXY_PASS:-jJZooP0vNdYbqdQ9}"

if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
  if [ -n "$PROXY_USER" ] && [ -n "$PROXY_PASS" ]; then
    proxy_auth="${PROXY_USER}:${PROXY_PASS}@"
  else
    proxy_auth=""
  fi
  proxy_url="socks5h://${proxy_auth}${PROXY_HOST}:${PROXY_PORT}"
  export http_proxy="$proxy_url"
  export https_proxy="$proxy_url"
  export HTTP_PROXY="$proxy_url"
  export HTTPS_PROXY="$proxy_url"
  echo "Используется SOCKS5 прокси ${PROXY_HOST}:${PROXY_PORT}"
fi

cleanup() {
  if [ -f "$OPENVPN_PID_FILE" ]; then
    kill "$(cat "$OPENVPN_PID_FILE")" 2>/dev/null || true
  fi
}

trap cleanup EXIT

if [ "${DISABLE_VPN:-}" = "true" ]; then
  echo "Переменная DISABLE_VPN=true — пропуск запуска OpenVPN"
else
  if [ ! -f "$VPN_CONFIG_PATH" ]; then
    echo "Не найден конфигурационный файл OpenVPN: $VPN_CONFIG_PATH" >&2
    exit 1
  fi

  echo "Запуск OpenVPN с конфигурацией $VPN_CONFIG_PATH"
  openvpn --config "$VPN_CONFIG_PATH" --daemon --writepid "$OPENVPN_PID_FILE"

  # Небольшая пауза для установления соединения
  sleep 5
fi

echo "Запуск веб-сервера"
exec gunicorn --bind 0.0.0.0:9003 --timeout "${GUNICORN_TIMEOUT:-600}" "wsgi:app"
