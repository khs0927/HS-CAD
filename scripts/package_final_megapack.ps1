param(
  [string]$Out = "outputs\HS-CAD-final-megapack-code.zip"
)

New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null
Compress-Archive -Path config,docs,src,scripts -DestinationPath $Out -Force
Write-Host "Created $Out"
