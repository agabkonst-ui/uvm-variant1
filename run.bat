@echo off
setlocal
if defined UVM_PYTHON goto configured

py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto launcher

for /f "delims=" %%I in ('where.exe python.exe 2^>nul') do (
    "%%I" -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 (
        set "UVM_PYTHON=%%I"
        goto configured
    )
)

echo Python 3.10 or newer is required. Set UVM_PYTHON to python.exe. 1>&2
exit /b 1

:configured
"%UVM_PYTHON%" -B "%~dp0src\assembler.py" %*
exit /b %errorlevel%

:launcher
py -3 -B "%~dp0src\assembler.py" %*
exit /b %errorlevel%
