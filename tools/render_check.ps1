# Render the generated pptx to PNG via PowerPoint COM for visual verification.
# NOTE: no non-ASCII literals here on purpose (PS 5.1 reads .ps1 as ANSI and
# would mangle Korean paths). The deck is located by wildcard instead.

param([string]$Name = "")

$root = Split-Path -Parent $PSScriptRoot
if ($Name) {
  $deck = Get-ChildItem -Path $root -Filter *.pptx -File |
          Where-Object { $_.Name -like "*$Name*" } | Select-Object -First 1
} else {
  # most recently written deck (a locked older copy may still be sitting next to it)
  $deck = Get-ChildItem -Path $root -Filter *.pptx -File |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
if (-not $deck) { throw "no matching .pptx found in $root" }
Write-Output ("deck: " + $deck.FullName)

$work = Join-Path $env:TEMP ("pptcheck_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $work | Out-Null
$tmpPptx = Join-Path $work "deck.pptx"
Copy-Item -LiteralPath $deck.FullName -Destination $tmpPptx

$outDir = Join-Path $root "_render"
if (Test-Path -LiteralPath $outDir) { Remove-Item -Recurse -Force -LiteralPath $outDir }
New-Item -ItemType Directory -Path $outDir | Out-Null

$ppt = New-Object -ComObject PowerPoint.Application
try {
  $pres = $ppt.Presentations.Open($tmpPptx, $true, $false, $false)
  Write-Output ("slides: " + $pres.Slides.Count)
  for ($i = 1; $i -le $pres.Slides.Count; $i++) {
    $name = "slide{0}.png" -f $i
    $tmpPng = Join-Path $work $name
    $pres.Slides.Item($i).Export($tmpPng, "PNG", 1600, 900)
    Copy-Item -LiteralPath $tmpPng -Destination (Join-Path $outDir $name)
    Write-Output ("exported " + $name)
  }
  $pres.Close()
} finally {
  $ppt.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
  Remove-Item -Recurse -Force -LiteralPath $work -ErrorAction SilentlyContinue
}
Write-Output ("out: " + $outDir)
