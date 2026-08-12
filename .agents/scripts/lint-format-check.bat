@echo off
rem ===================================================================
rem Antigravity Deterministik Lint & Format Check Betiği
rem Bu betik PostToolUse hook'u tarafından tetiklenir.
rem Projeye özel linter veya formatlayıcı komutlarını buraya ekleyebilirsiniz.
rem ===================================================================

rem Örnek: Eğer projede npm lint varsa çalıştır:
rem if exist package.json (
rem   call npm run lint --quiet
rem )

rem Hook kontratı gereği JSON objesi döndürülür:
echo {}
exit /b 0
