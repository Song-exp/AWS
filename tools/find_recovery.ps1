# Search for any recoverable presentation artifacts (autosave / backup / temp copies).
# ASCII-only literals on purpose (PS 5.1 reads .ps1 as ANSI).

$cutoff = (Get-Date).AddHours(-6)
$exts = @('.pptx', '.ppt', '.show', '.asd', '.bak', '.wbk')
$roots = @(
  "$env:USERPROFILE\Desktop",
  "$env:USERPROFILE\Documents",
  "$env:USERPROFILE\Downloads",
  "$env:USERPROFILE\OneDrive",
  "$env:APPDATA",
  "$env:LOCALAPPDATA\Temp",
  "$env:LOCALAPPDATA\Microsoft\Office",
  "$env:LOCALAPPDATA\Packages"
)

$hits = @()
foreach ($r in $roots) {
  if (-not (Test-Path -LiteralPath $r)) { continue }
  try {
    $hits += Get-ChildItem -LiteralPath $r -Recurse -File -Force -ErrorAction SilentlyContinue |
      Where-Object { $exts -contains $_.Extension.ToLower() -and $_.LastWriteTime -gt $cutoff }
  } catch { }
}

Write-Output "=== candidates (last 6h) ==="
if ($hits.Count -eq 0) {
  Write-Output "none found"
} else {
  $hits | Sort-Object LastWriteTime |
    ForEach-Object { "{0,10}  {1}  {2}" -f $_.Length, $_.LastWriteTime.ToString('HH:mm:ss'), $_.FullName }
}

Write-Output ""
Write-Output "=== shadow copies (previous versions) ==="
$vss = vssadmin list shadows 2>&1
if ($LASTEXITCODE -ne 0 -or $vss -match 'denied|Administrator|관리자') {
  Write-Output "requires elevation - run 'vssadmin list shadows' in an admin terminal"
} else {
  $lines = $vss | Select-String -Pattern 'creation time|Shadow Copy Volume'
  if ($lines) { $lines | ForEach-Object { $_.Line.Trim() } } else { Write-Output "no shadow copies on this volume" }
}
