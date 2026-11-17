#!/bin/bash

# Crear y dar permisos a los directorios temporales de X11 para evitar el error de euid != 0
export XDG_RUNTIME_DIR=/tmp/runtime-user
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Limpiar bloqueos anteriores del servidor X
rm -f /tmp/.X99-lock

# 1. Iniciar servidor gráfico virtual Xvfb en el display :99
Xvfb :99 -screen 0 1280x800x24 &
sleep 2

# 2. Iniciar gestor de ventanas ligero Fluxbox
fluxbox &
sleep 1

# 3. Iniciar x11vnc en segundo plano con -nopw (sin pedir contraseña ni ficheros de autenticación)
x11vnc -display :99 -nopw -forever -shared -rfbport 5900 &
sleep 1

# 4. Iniciar servidor noVNC / websockify en el puerto 10000 requerido por Render
websockify --web=/usr/share/novnc/ 10000 localhost:5900 &
sleep 1

echo "Infraestructura gráfica lista. Iniciando bot de Telegram..."

# 5. Ejecutar Python en primer plano (exec) para que Render mantenga el contenedor vivo y muestre los logs del bot
exec python3 main.py
