$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -B -m unittest -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
python make_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
$taskIcon = Join-Path $PSScriptRoot 'assets/focus.ico'
python -m PyInstaller --noconfirm --clean --onefile --windowed --name StillFocus --icon $taskIcon --add-data "$taskIcon;assets" --distpath release/StillFocus-Compact --workpath build/pyinstaller --specpath build --exclude-module numpy --exclude-module matplotlib --exclude-module IPython --exclude-module _hashlib app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Copy-Item -LiteralPath README.md -Destination release/StillFocus-Compact/README.md
Compress-Archive -Path release/StillFocus-Compact -DestinationPath release/StillFocus-Compact-Windows-x64.zip -Force
Write-Host 'Created release/StillFocus-Compact-Windows-x64.zip'
