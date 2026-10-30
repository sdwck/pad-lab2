@echo off
title Cloudflare Tunnel - PAD Lab 2
cd /d "%~dp0"

echo ========================================================
echo    Launching Cloudflare Tunnel for PAD Lab 2
echo ========================================================

"C:\Users\sdwck\Desktop\Projects\pad-lab1\cloudflared.exe" tunnel run --token eyJhIjoiMjQ0MWI5MWFlZTA0YzZhMjk0N2I2YWM3NWY4ZjUwODQiLCJ0IjoiNDUwNDNjYjYtZDJkZC00ZDcwLWFmOWUtMjFiZjMxOTU3MDdjIiwicyI6Ik5UUXpPV1F3TWpVdFlUazJaUzAwTlRCbUxUZzRObVF0TmpKa04yTmpaRGs0T0dFNSJ9
pause
