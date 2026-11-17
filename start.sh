#!/bin/bash
Xvfb :99 -screen 0 1280x800x24 &
sleep 2
fluxbox &
x11vnc -display :99 -nopw -listen localhost -xkb -forever -shared &
websockify --web=/usr/share/novnc/ 7860 localhost:5900 &
python3 main.py
