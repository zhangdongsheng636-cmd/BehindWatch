$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python tools/prepare.py
if ($LASTEXITCODE -ne 0) { throw 'Asset preparation failed' }
python -m PyInstaller --noconfirm --clean BehindWatch.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Host '完成：dist\BehindWatch\BehindWatch.exe（请保留整个文件夹）'
