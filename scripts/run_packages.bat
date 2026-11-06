@echo off
set MAIN="%~dp0..\src\main.py"
set URL=https://api.nuget.org/v3/index.json

echo === Serilog (several dependencies) ===
python %MAIN% -p Serilog -r %URL%
echo.
echo === Polly (one dependency) ===
python %MAIN% -p Polly -r %URL%
echo.
echo === System.ValueTuple (no dependencies) ===
python %MAIN% -p System.ValueTuple -r %URL%
echo.
echo === package name in other letter case ===
python %MAIN% -p newtonsoft.json -r %URL%
