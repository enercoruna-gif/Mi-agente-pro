#!/bin/bash

# Configurar directorios temporales de X11 para el usuario actual
export XDG_RUNTIME_DIR=/tmp/runtime-user
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Limpiar bloqueos anteriores del servidor X
rm -f /tmp/.X99-lock

# 1. Iniciar servidor gráfico virtual Xvfb
Xvfb :99 -screen 0 1280x800x24 &
sleep 2

# 2. Iniciar gestor de ventanas Fluxbox
fluxbox &
sleep 1

# 3. Iniciar x11vnc en segundo plano con -nopw
x11vnc -display :99 -nopw -forever -shared -rfbport 5900 &
sleep 1

# 4. Iniciar servidor noVNC / websockify en el puerto 10000 requerido por Render
websockify --web=/usr/share/novnc/ 10000 localhost:5900 &
sleep 2

echo "Entorno gráfico listo. Arrancando el bot de Telegram..."

# 5. Ejecutar Python de forma normal (sin exec) para que el script se quede corriendo y escuche Telegram
python3 main.py
