#!/bin/bash

# Configurar directorios temporales de X11 para el usuario actual
export XDG_RUNTIME_DIR=/tmp/runtime-user
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Limpiar bloqueos anteriores del servidor X
rm -f /tmp/.X99-lock

# 1. Iniciar servidor gráfico virtual Xvfb en el display :99
Xvfb :99 -screen 0 1280x800x24 &
sleep 2

# 2. Iniciar x11vnc directamente (sin gestores de ventanas pesados que ensucien los logs)
x11vnc -display :99 -nopw -forever -shared -rfbport 5900 &
sleep 1

# 3. Iniciar servidor noVNC / websockify en el puerto 10000 requerido por Render
websockify --web=/usr/share/novnc/ 10000 localhost:5900 &
sleep 2

echo "Entorno gráfico y VNC listos. Arrancando el bot de Python..."

# 4. Ejecutar Python en primer plano para ver los logs en tiempo real
python3 main.py
