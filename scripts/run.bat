@echo off
rem Dependency graph of a package from real NuGet repository
python "%~dp0..\src\main.py" --package Polly ^
    --repo https://api.nuget.org/v3/index.json ^
    --output graph.svg --ascii-tree --max-depth 3
