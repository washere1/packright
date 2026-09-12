$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimePath = [IO.Path]::GetFullPath((Join-Path $ProjectRoot "runtime-data"))
$ExpectedRoot = [IO.Path]::GetFullPath($ProjectRoot)
if (-not $RuntimePath.StartsWith($ExpectedRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to remove a path outside the project runtime directory." }
if ((Split-Path -Parent $RuntimePath) -ne $ExpectedRoot) { throw "Refusing to remove an unexpected runtime path." }
if (Test-Path -LiteralPath $RuntimePath) { Remove-Item -LiteralPath $RuntimePath -Recurse -Force }
Write-Host "Removed local runtime data at $RuntimePath. This does not affect source files or demo fixtures."
