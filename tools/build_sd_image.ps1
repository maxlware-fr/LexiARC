# build_sd_image.ps1
# Recree l'arborescence core/ dans sd_card.img, fichier par fichier,
# sans utiliser l'option -s (recursive) de mcopy qui echoue sur ce build.
#
# Usage : place ce script dans le meme dossier que core/ et sd_card.img,
# puis lance-le simplement :   .\build_sd_image.ps1

$mtools = "C:\Users\maxlw\Downloads\mtools"
$image  = "sd_card.img"
$source = "core"

if (-not (Test-Path $image)) {
    Write-Host "ERREUR: $image introuvable dans ce dossier." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $source)) {
    Write-Host "ERREUR: dossier $source introuvable dans ce dossier." -ForegroundColor Red
    exit 1
}

$sourceFull = (Resolve-Path $source).Path

Write-Host "=== Etape 1/2 : creation des dossiers ===" -ForegroundColor Cyan
$dirs = Get-ChildItem -Path $source -Recurse -Directory | Sort-Object FullName
$dirCount = $dirs.Count
$i = 0
foreach ($d in $dirs) {
    $i++
    $rel = $d.FullName.Substring($sourceFull.Length) -replace '\\','/'
    $target = "::$rel"
    & "$mtools\mmd.exe" -i $image $target 2>$null | Out-Null
    Write-Progress -Activity "Creation des dossiers" -Status "$i / $dirCount" -PercentComplete (100*$i/$dirCount)
}
Write-Host "Dossiers traites : $dirCount"

Write-Host "=== Etape 2/2 : copie des fichiers ===" -ForegroundColor Cyan
$files = Get-ChildItem -Path $source -Recurse -File
$fileCount = $files.Count
$i = 0
$errors = @()
foreach ($f in $files) {
    $i++
    $rel = $f.FullName.Substring($sourceFull.Length) -replace '\\','/'
    $target = "::$rel"
    $result = & "$mtools\mcopy.exe" -i $image -o $f.FullName $target 2>&1
    if ($LASTEXITCODE -ne 0) {
        $errors += "$rel -> $result"
    }
    if ($i % 25 -eq 0 -or $i -eq $fileCount) {
        Write-Progress -Activity "Copie des fichiers" -Status "$i / $fileCount" -PercentComplete (100*$i/$fileCount)
    }
}

Write-Host ""
Write-Host "=== Termine ===" -ForegroundColor Green
Write-Host "Fichiers copies : $($fileCount - $errors.Count) / $fileCount"
if ($errors.Count -gt 0) {
    Write-Host "Erreurs ($($errors.Count)) :" -ForegroundColor Yellow
    $errors | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    if ($errors.Count -gt 20) { Write-Host "  ... et $($errors.Count - 20) de plus" }
} else {
    Write-Host "Aucune erreur." -ForegroundColor Green
}