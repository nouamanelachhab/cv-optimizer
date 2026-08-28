@echo off
REM ============================================================
REM  CV ATS Optimizer - lanceur en double-clic
REM  Demarre l'application dans ton navigateur.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Erreur] Environnement introuvable.
    echo Ouvre PowerShell dans ce dossier et lance :
    echo     python -m venv .venv
    echo     .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Demarrage de CV ATS Optimizer...
echo L'application va s'ouvrir dans ton navigateur (http://localhost:8501)
echo Pour l'arreter : ferme cette fenetre.
echo.

".venv\Scripts\python.exe" -m streamlit run "app.py" --server.address 0.0.0.0 --server.port 8501

pause
