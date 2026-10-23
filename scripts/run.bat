@echo off
rem Direct dependencies of a package from real NuGet repository
python "%~dp0..\src\main.py" --package Newtonsoft.Json ^
    --repo https://api.nuget.org/v3/index.json ^
    --output graph.svg --ascii-tree --max-depth 2
