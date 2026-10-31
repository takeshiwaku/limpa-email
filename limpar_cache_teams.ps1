# =============================================================
# limpar_cache_teams.ps1
# Fecha o Microsoft Edge e limpa cache + cookies (resolve login do Teams web)
# Uso: clique com o botao direito > "Executar com PowerShell"
#      ou rode:  powershell -ExecutionPolicy Bypass -File .\limpar_cache_teams.ps1
#
# ATENCAO: limpar cookies desloga voce de TODOS os sites no Edge,
#          nao so do Teams. O cache/historico de navegacao tambem sai.
# =============================================================

Write-Host "ATENCAO: isso vai limpar cookies e cache do Edge inteiro." -ForegroundColor Yellow
Write-Host "Voce sera deslogado de todos os sites (Teams, e-mail, etc.)." -ForegroundColor Yellow
$resp = Read-Host "Deseja continuar? (S/N)"
if ($resp -notin @("S", "s")) {
    Write-Host "Cancelado." -ForegroundColor DarkGray
    Read-Host "Pressione ENTER para sair"
    return
}

Write-Host "`n==> Fechando o Microsoft Edge..." -ForegroundColor Cyan
Get-Process -Name "msedge" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $_.Kill()
        Write-Host "    Encerrado: msedge (PID $($_.Id))" -ForegroundColor DarkGray
    } catch {
        Write-Host "    Nao foi possivel encerrar msedge: $_" -ForegroundColor Yellow
    }
}
Start-Sleep -Seconds 3

# -------------------------------------------------------------
# Funcao auxiliar: remove arquivo ou pasta se existir
# -------------------------------------------------------------
function Remover-Item-Seguro {
    param([string]$Caminho)

    if (Test-Path $Caminho) {
        try {
            Remove-Item -Path $Caminho -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "    Removido: $Caminho" -ForegroundColor Green
        } catch {
            Write-Host "    Erro ao remover $Caminho : $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "    (nao existe) $Caminho" -ForegroundColor DarkGray
    }
}

# -------------------------------------------------------------
# Pasta base do perfil do Edge
# (por padrao usa o perfil "Default"; se voce usa varios perfis,
#  o script tambem varre Profile 1, Profile 2, etc.)
# -------------------------------------------------------------
$baseEdge = "$env:LOCALAPPDATA\Microsoft\Edge\User Data"

if (-not (Test-Path $baseEdge)) {
    Write-Host "Perfil do Edge nao encontrado em: $baseEdge" -ForegroundColor Red
    Read-Host "Pressione ENTER para sair"
    return
}

# Descobre todos os perfis (Default, Profile 1, Profile 2, ...)
$perfis = Get-ChildItem -Path $baseEdge -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "Default" -or $_.Name -like "Profile *" }

# Itens a limpar dentro de cada perfil
$itensPerfil = @(
    "Cache",
    "Code Cache",
    "GPUCache",
    "Service Worker",
    "Network\Cookies",
    "Network\Cookies-journal",
    "Cookies",
    "Cookies-journal"
)

foreach ($perfil in $perfis) {
    Write-Host "`n==> Limpando perfil: $($perfil.Name)" -ForegroundColor Cyan
    foreach ($item in $itensPerfil) {
        Remover-Item-Seguro (Join-Path $perfil.FullName $item)
    }
}

Write-Host "`n==> Concluido!" -ForegroundColor Cyan
Write-Host "Abrindo o Teams no Edge..." -ForegroundColor White

Start-Sleep -Seconds 2
Start-Process "msedge.exe" "https://teams.microsoft.com"

Write-Host "Faca login com seu perfil." -ForegroundColor White
Read-Host "`nPressione ENTER para sair"
