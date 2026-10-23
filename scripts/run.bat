@echo off
rem Run with real repository URL and all parameters
python "%~dp0..\src\main.py" --package Newtonsoft.Json ^
    --repo https://api.nuget.org/v3/index.json ^
    --output graph.svg --ascii-tree --max-depth 2
