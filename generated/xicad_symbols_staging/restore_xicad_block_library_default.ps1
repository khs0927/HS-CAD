$cfg = 'C:\xicad\xiLib\xiConfig.cfg'
$lines = Get-Content -LiteralPath $cfg -Encoding Default
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i].Trim() -eq '/xiBlkLibrary' -and ($i + 1) -lt $lines.Count) {
    $parts = $lines[$i + 1] -split '\|'
    if ($parts.Count -ge 2) {
      $parts[1] = '<MAINPATH>\_????_??'
      $lines[$i + 1] = ($parts -join '|')
    }
  }
}
Set-Content -LiteralPath $cfg -Value $lines -Encoding Default
