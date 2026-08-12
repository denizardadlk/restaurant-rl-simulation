@echo off
rem ===================================================================
rem Antigravity SPEV Otomatik Doğrulama Betiği
rem Dosya düzenlemelerinden sonra otomatik doğrulamayı tetikler.
rem Projeye özel test çalıştırma komutlarınızı buraya ekleyebilirsiniz.
rem ===================================================================

rem Örnek: Eğer projede test komutu varsa çalıştır:
rem if exist package.json (
rem   call npm test -- --silent
rem )

rem Hook kontratı gereği JSON objesi döndürülür:
echo {}
exit /b 0
