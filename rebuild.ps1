# Rebuild and restart the full stack
Write-Host "Stopping containers..." -ForegroundColor Yellow
docker-compose down

Write-Host "Rebuilding agent image..." -ForegroundColor Yellow
docker build -t claude-agent:latest ./agent

Write-Host "Rebuilding and starting stack..." -ForegroundColor Yellow
docker-compose up --build -d

Write-Host "Done! App running..." -ForegroundColor Green
docker-compose ps
