@echo off
rem Dependency graph of a package from real NuGet repository
rem with Graphviz description, ASCII tree and SVG image
python "%~dp0..\src\main.py" --package Polly ^
    --repo https://api.nuget.org/v3/index.json ^
    --output polly.svg --ascii-tree --max-depth 3
