@echo off
rem Coleta diaria do hub (agendada no Windows como "Hub vagas IA - coleta").
rem Roda no PC porque a micro1 bloqueia os servidores do GitHub. O push dispara a publicacao do site.
rem Usa o ambiente .venv (tem o tradutor ingles-portugues); sem ele, coleta em ingles mesmo.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
git pull -q --rebase >> coletas-saida.log 2>&1
%PY% -m hub coletar >> coletas-saida.log 2>&1
git add site/vagas.json coletas.log dados/traducoes.json >nul 2>&1
git commit -q -m "vagas: coleta automatica %date%" >nul 2>&1
git push -q >> coletas-saida.log 2>&1
exit /b 0
