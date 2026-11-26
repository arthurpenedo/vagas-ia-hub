@echo off
rem Coleta diária de vagas do hub. Agendada no Windows como "Hub vagas IA - coleta".
rem Atualiza site\vagas.json, anota em coletas.log e faz um commit local (sem push).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -m hub coletar >> coletas-saida.log 2>&1
git add site/vagas.json coletas.log >nul 2>&1
git commit -m "vagas: coleta automatica %date%" >nul 2>&1
exit /b 0
