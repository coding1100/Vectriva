@echo off
echo Starting Redis container...
docker run -d --name vectriva-redis -p 6379:6379 redis:7-alpine
echo Redis started on port 6379
pause
