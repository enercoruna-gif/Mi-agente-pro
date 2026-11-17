#!/bin/bash

# Limpiar bloqueos anteriores del servidor X
rm -f /tmp/.X99-lock

# Iniciar servidor gráfico virtual Xvfb en el display :99
Xvfb :99 -screen 0 1280x800x24 &
sleep 2

# Iniciar gestor de ventanas ligero Fluxbox
fluxbox &

# Iniciar x11vnc usando -auth guess para evitar errores de cookies de autenticación
x11vnc -display :99 -auth guess -forever -shared -rfbport 5900 &

# Iniciar servidor noVNC / websockify en el puerto 10000 requerido por Render
websockify --web=/usr/share/novnc/ 10000 localhost:5900 &

# Ejecutar el script principal de Python
python3 main.py
