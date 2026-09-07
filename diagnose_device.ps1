# ============================================================================
# Wake-on-LAN Manager - Hostnamen-Diagnose
# ============================================================================
# Laeuft die Skript auf dem Rechner, auf dem ein Geraet falschlich als
# offline/unbekannt angezeigt wird, z. B.:
#   .\diagnose_device.ps1 blade-18
#   .\diagnose_device.ps1 blade-18.fritz.box
# Es prueft genau die Schritte, die die App intern ausfuehrt:
#   1. DNS-Aufloesung (welche IPv4-Adressen liefert der Nameserver?)
#   2. IPv4-Ping auf JEDE aufgeloeste Adresse (die App pingt, bis eine antwortet)
# ============================================================================

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$HostName
)

Write-Host ""
Write-Host "=== DNS-Suffix dieses Rechners ===" -ForegroundColor Cyan
ipconfig | Select-String -Pattern "DNS-Suffix", "DNS Suffix" | ForEach-Object { "  " + $_.Line.Trim() }
Write-Host "  (Hinweis: ein Kurzname wie 'blade-18' funktioniert nur, wenn hier 'fritz.box' steht.)"

Write-Host ""
Write-Host "=== 1) DNS-Aufloesung fuer '$HostName' ===" -ForegroundColor Cyan
$aRecords = @()
try {
    # IPv4-only: the app restricts its lookup to AF_INET as well
    $aRecords = @(Resolve-DnsName -Name $HostName -Type A -ErrorAction Stop |
        Where-Object { $_.IPAddress -match '^(\d{1,3}\.){3}\d{1,3}$' } |
        Select-Object -ExpandProperty IPAddress | Select-Object -Unique)
} catch {
    Write-Host "  FEHLER bei der DNS-Aufloesung: $($_.Exception.Message)" -ForegroundColor Red
}
if ($aRecords.Count -eq 0) {
    Write-Host "  Keine IPv4-Adresse gefunden -> die App zeigt 'unbekannt'." -ForegroundColor Red
} else {
    $aRecords | ForEach-Object { Write-Host "  A-Record: $_" -ForegroundColor Green }
}

Write-Host ""
Write-Host "=== 2) IPv4-Ping auf jede Adresse (wie die App) ===" -ForegroundColor Cyan
foreach ($ip in $aRecords) {
    $out = ping -4 -n 1 -w 2000 $ip 2>&1 | Out-String
    if ($out -match "(?i)\bttl[=:]\s*\d+") {
        Write-Host "  $ip : ANTWORTET (TTL vorhanden) -> online" -ForegroundColor Green
    } else {
        Write-Host "  $ip : keine echte Antwort ->" -ForegroundColor Yellow
        ($out -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 2) | ForEach-Object { "      " + $_.Trim() }
    }
}

Write-Host ""
Write-Host "=== 3) Vergleich: reiner Name vs. FQDN ===" -ForegroundColor Cyan
$bare = ($HostName -replace '\..*$')
foreach ($variant in (@($HostName, $bare, "$bare.fritz.box") | Where-Object { $_ } | Select-Object -Unique)) {
    try {
        $ips = @(Resolve-DnsName -Name $variant -Type A -ErrorAction Stop |
            Where-Object { $_.IPAddress -match '^(\d{1,3}\.){3}\d{1,3}$' } |
            Select-Object -ExpandProperty IPAddress | Select-Object -Unique)
        if ($ips.Count) {
            Write-Host "  $variant -> $($ips -join ', ')" -ForegroundColor Green
        } else {
            Write-Host "  $variant -> keine IPv4 (A) gefunden" -ForegroundColor Red
        }
    } catch {
        Write-Host "  $variant -> NICHT aufloesbar" -ForegroundColor Red
    }
}
Write-Host ""
