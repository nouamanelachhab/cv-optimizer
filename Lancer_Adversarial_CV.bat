@echo off
REM ============================================================
REM  ATS Red-Team CV Generator - lanceur en double-clic
REM  Outil de test interne : audit de votre propre moteur ATS.
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

echo Demarrage de ATS Red-Team CV Generator...
echo L'application va s'ouvrir dans ton navigateur (http://localhost:8502)
echo Pour l'arreter : ferme cette fenetre.
echo.

".venv\Scripts\python.exe" -m streamlit run "adversarial_app.py" --server.address 0.0.0.0 --server.port 8502

pause
