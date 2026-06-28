@echo off
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Missing RIP venv Python: %ROOT%\.venv\Scripts\python.exe
  exit /b 1
)

if "%RIP_HOST%"=="" set "RIP_HOST=0.0.0.0"
if "%RIP_PORT%"=="" set "RIP_PORT=8000"
if "%GATEWAY_HOST%"=="" set "GATEWAY_HOST=0.0.0.0"
if "%GATEWAY_PORT%"=="" set "GATEWAY_PORT=8001"
if "%GATEWAY_POSTGRES_URL%"=="" set "GATEWAY_POSTGRES_URL=postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel?ssl=disable"
if "%GATEWAY_REDIS_URL%"=="" set "GATEWAY_REDIS_URL=redis://localhost:6379"
if "%GATEWAY_RIP_MCP_CWD%"=="" set "GATEWAY_RIP_MCP_CWD=%ROOT%"

set "PYTHONPATH=%ROOT%\gateway;%PYTHONPATH%"

echo Checking for running servers...
:: Stop processes on RIP port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%RIP_PORT%"') do (
  echo Stopping process %%a on port %RIP_PORT%
  taskkill /F /PID %%a >nul 2>&1
)
:: Stop processes on Gateway port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%GATEWAY_PORT%"') do (
  echo Stopping process %%a on port %GATEWAY_PORT%
  taskkill /F /PID %%a >nul 2>&1
)

timeout /t 1 /nobreak >nul

echo Checking Docker...
docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not responding. Trying to start Docker Desktop...
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  )
  if exist "%LocalAppData%\Docker\Docker Desktop.exe" (
    start "" "%LocalAppData%\Docker\Docker Desktop.exe"
  )

  for /L %%i in (1,1,60) do (
    timeout /t 2 /nobreak >nul
    docker info >nul 2>nul
    if not errorlevel 1 goto docker_ready
  )

  echo Docker did not become ready in time.
  exit /b 1
)

:docker_ready
echo Starting RIP Docker services...
docker compose -f "%ROOT%\docker-compose.yml" up -d neo4j qdrant postgres redis
if errorlevel 1 (
  echo Failed to start RIP Docker services.
  exit /b 1
)

echo Starting repo server on http://%RIP_HOST%:%RIP_PORT%
start "RIP repo serve" /D "%ROOT%" cmd /k ""%ROOT%\.venv\Scripts\python.exe" -m uvicorn server.app:app --host %RIP_HOST% --port %RIP_PORT%"

timeout /t 2 /nobreak >nul

echo Starting Context Gateway on http://%GATEWAY_HOST%:%GATEWAY_PORT%
start "Context Gateway" /D "%ROOT%" cmd /k ""%ROOT%\.venv\Scripts\python.exe" -m uvicorn gateway.server.main:app --host %GATEWAY_HOST% --port %GATEWAY_PORT%"

echo.
echo Started runtime windows:
echo   RIP repo serve:  http://%RIP_HOST%:%RIP_PORT%
echo   Gateway API:     http://%GATEWAY_HOST%:%GATEWAY_PORT%
echo   Docker services: Neo4j, Qdrant, Postgres, Redis
echo.
echo This script does not run uv sync, install packages, or migrations.

endlocal
