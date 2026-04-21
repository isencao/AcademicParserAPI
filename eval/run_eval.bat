@echo off
cd /d "%~dp0.."
title Academic Parser - Evaluation

echo.
echo  =========================================
echo   AcademicParserAPI - Evaluation Tool
echo  =========================================
echo.

:menu
echo  Bir PDF sec veya doc_id gir:
echo.
echo  [1] testpdf\test.pdf
echo  [2] testpdf\test1.pdf
echo  [3] Baska bir PDF yolu gir
echo  [4] Zaten yukledim, sadece tabloyu cek
echo  [5] Cikis
echo.
set /p choice= Secim (1-5):

if "%choice%"=="1" goto upload1
if "%choice%"=="2" goto upload2
if "%choice%"=="3" goto custom
if "%choice%"=="4" goto fetchonly
if "%choice%"=="5" goto end
echo Gecersiz secim.
goto menu

:upload1
echo.
set /p lang= Dil? (auto / en / tr) [varsayilan: auto]:
if "%lang%"=="" set lang=auto
echo.
python eval/run_eval.py testpdf/test.pdf --lang %lang%
goto done

:upload2
echo.
set /p lang= Dil? (auto / en / tr) [varsayilan: auto]:
if "%lang%"=="" set lang=auto
echo.
python eval/run_eval.py testpdf/test1.pdf --lang %lang%
goto done

:custom
echo.
set /p fpath= PDF yolu (ornek: C:\Users\...\makale.pdf):
set /p lang= Dil? (auto / en / tr) [varsayilan: auto]:
if "%lang%"=="" set lang=auto
echo.
python eval/run_eval.py "%fpath%" --lang %lang%
goto done

:fetchonly
echo.
set /p docid= doc_id gir (ornek: test.pdf):
echo.
python eval/run_eval.py --fetch-only "%docid%"
goto done

:done
echo.
echo  Rapor eval\results\ klasorune kaydedildi.
echo.
pause
goto menu

:end
