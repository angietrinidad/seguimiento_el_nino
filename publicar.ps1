<#
.SYNOPSIS
    Publica el repositorio Seguimiento El Niño: sube los cambios a GitHub y
    despliega el sitio Quarto en GitHub Pages.

.DESCRIPTION
    1. Verifica que Quarto y Git estén disponibles.
    2. Verifica la autenticación con GitHub (GitHub CLI si está instalado).
    3. Sube la rama main a origin.
    4. Renderiza y publica el sitio en la rama gh-pages (GitHub Pages).

.EXAMPLE
    .\publicar.ps1
    Sube cambios y publica el sitio.

.EXAMPLE
    .\publicar.ps1 -SoloPush
    Solo sube a GitHub, sin publicar el sitio.
#>

param(
    [switch]$SoloPush,      # Solo hace git push, sin publicar el sitio
    [switch]$SoloSitio      # Solo publica el sitio, sin git push
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Info($m)  { Write-Host "  $m" -ForegroundColor Cyan }
function Ok($m)    { Write-Host "OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "!   $m" -ForegroundColor Yellow }

# --- Localizar Quarto (puede no estar en el PATH) ---
$quarto = "quarto"
if (-not (Get-Command quarto -ErrorAction SilentlyContinue)) {
    $rutaQuarto = "$env:LOCALAPPDATA\Programs\Quarto\bin\quarto.exe"
    if (Test-Path $rutaQuarto) {
        $quarto = $rutaQuarto
        Info "Quarto no está en el PATH; usando: $quarto"
    } else {
        throw "No se encontró Quarto. Instalalo desde https://quarto.org/docs/get-started/"
    }
}

# --- Verificar autenticación con GitHub ---
if (-not $SoloSitio) {
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        $estado = gh auth status 2>&1 | Out-String
        if ($estado -match "Logged in") {
            Ok "Autenticado en GitHub (gh)."
        } else {
            Aviso "No estás autenticado. Ejecutá primero:  gh auth login"
            Aviso "(elegí GitHub.com -> HTTPS -> login por navegador)"
            throw "Autenticación de GitHub requerida."
        }
    } else {
        Aviso "GitHub CLI (gh) no detectado; el push usará el Credential Manager de Git."
    }
}

# --- 1) Subir a GitHub ---
if (-not $SoloSitio) {
    Info "Subiendo la rama main a origin..."
    git push -u origin main
    Ok "Cambios subidos a GitHub."
}

# --- 2) Publicar el sitio en GitHub Pages ---
if (-not $SoloPush) {
    Info "Publicando el sitio en GitHub Pages (rama gh-pages)..."
    & $quarto publish gh-pages --no-prompt
    Ok "Sitio publicado."
    Info "URL: https://angietrinidad.github.io/seguimiento_el_nino/"
    Info "(La primera publicación puede tardar 1-2 minutos en verse.)"
}

Write-Host ""
Ok "Listo."
