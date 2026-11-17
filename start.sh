#!/bin/bash

# Limpiar bloqueos anteriores del servidor X
rm -f /tmp/.X99-lock

# 1. Iniciar servidor gráfico virtual Xvfb
Xvfb :99 -screen 0 1280x800x24 &
sleep 2

# 2. Iniciar gestor de ventanas
fluxbox &
sleep 1

# 3. Iniciar x11vnc en segundo plano con -nopw
x11vnc -display :99 -nopw -forever -shared -rfbport 5900 &
sleep 1

# 4. Iniciar websockify (noVNC) en el puerto 10000 requerido por Render
websockify --web=/usr/share/novnc/ 10000 localhost:5900 &
sleep 1

echo "Infraestructura gráfica lista. Iniciando bot de Telegram..."

# 5. Ejecutar Python en primer plano para que Render mantenga vivo el servicio y muestre los logs del bot
exec python3 main.py
