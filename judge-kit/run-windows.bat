@echo off
setlocal
title Warrant
rem Warrant judge kit. Runs Warrant from GitHub through uv, with a small menu.
set "WARRANT=git+https://github.com/TheClazer/warrant"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 goto needuv
goto menu

:needuv
echo This needs uv, a small Python tool runner from astral.sh.
set "answer="
set /p "answer=Install it now? [y/N] "
if /i not "%answer%"=="y" (
  echo Nothing installed. See https://docs.astral.sh/uv/ or use the live demo: https://warrant-demo.onrender.com
  goto end
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

:menu
echo.
echo WARRANT: a permission slip for your AI agent
echo.
echo   1. See the difference        no AI, no key, about 5 seconds
echo   2. Guard a real command      no AI, no key
echo   3. The whole flow with AI    needs a Nebius Token Factory key
echo.
set "choice=1"
set /p "choice=Choose 1, 2 or 3 [1]: "
echo.
if "%choice%"=="2" goto guard
if "%choice%"=="3" goto flow
uvx --from "%WARRANT%" warrant prove
goto end

:guard
echo Allowed: example.com. This request should go through:
uvx --from "%WARRANT%" warrant guard --allow example.com -- curl -s -o NUL -w "HTTP %%{http_code}\n" https://example.com/
echo.
echo This one should be blocked (curl reports HTTP 000 because the connection was refused):
uvx --from "%WARRANT%" warrant guard --allow example.com -- curl -s -o NUL -w "HTTP %%{http_code}\n" https://www.iana.org/
goto end

:flow
uvx --from "%WARRANT%" warrant try

:end
echo.
pause
