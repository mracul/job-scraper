
@echo off
cd /d %~dp0
set "CONDA_EXE=C:/Users/a/miniconda3/Scripts/conda.exe"
if exist "%CONDA_EXE%" (
	"%CONDA_EXE%" run -p C:\Users\a\miniconda3 --no-capture-output streamlit run streamlit_app.py
) else (
	streamlit run streamlit_app.py
)
