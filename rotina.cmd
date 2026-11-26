@echo off
rem Coleta diaria do hub (agendada no Windows como "Hub vagas IA - coleta").
rem Roda no PC porque a micro1 bloqueia os servidores do GitHub. O push dispara a publicacao do site.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
git pull -q --rebase >> coletas-saida.log 2>&1
python -m hub coletar >> coletas-saida.log 2>&1
git add site/vagas.json coletas.log >nul 2>&1
git commit -q -m "vagas: coleta automatica %date%" >nul 2>&1
git push -q >> coletas-saida.log 2>&1
exit /b 0
