[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Path,
  [long]$BaselineTicks=60029403,
  [switch]$Details,
  [switch]$PixelsConfirmed
)
$ErrorActionPreference='Stop'
$lines=Get-Content -LiteralPath $Path
$ticks=[long]0;$reads=0;$display=0;$frame='00000000';$fault=0
$blocked=$false;$present=$false;$seen=@{}
function Show($key,$message) {
  if (!$seen.ContainsKey($key)) { $seen[$key]=$true; Write-Host "[MERC360] $message" }
}
function Field($line,$key) {
  $m=[regex]::Match($line,'(?:^|\s)'+[regex]::Escape($key)+'=([0-9A-Fa-f]+)')
  if($m.Success){return $m.Groups[1].Value}
  return $null
}
for($i=0;$i -lt $lines.Count;$i++){
  $line=$lines[$i]
  if($Details){Write-Host $line}
  if($line -match 'PHASE 6DQ XENOS DEVICE RESULT: PASS'){Show 'xenos' 'Xenos initialized; game pixels NOT proven'}
  if($line -match 'native D3D CreateDevice handoff'){Show 'd3d' 'Guest D3D CreateDevice reached'}
  if($line -match 'entered XACTENG frontier'){Show 'xact' 'XACT engine reached'}
  if($line -match 'entered DSOUND owner'){Show 'sound' 'DSOUND hardware initialization reached'}
  if($line -match 'K1-V6 APC DELIVER:'){Show 'apc' 'Translated APC callback reached'}
  if($line -match 'K1-V6b APC QUEUED:'){Show 'queue' 'Async stream completion queued'}
  if($line -match 'ASYNC STREAM READ:'){
    $v=Field $line 'successes';if($null -ne $v){$reads=[int]$v}
    Write-Host ('[STREAM] '+($line -replace '^.*?ASYNC STREAM READ:\s*',''))
  }
  if($line -match 'PRESENT PROXIMITY:|PIXEL CHASE:'){
    $v=Field $line 'display_calls';if($null -ne $v){$display=[int]$v}
    $v=Field $line 'framebuffer';if($null -ne $v){$frame=$v}
    if($line -match 'PRESENT PROXIMITY:'){Write-Host ('[VIDEO] '+($line -replace '^.*?PRESENT PROXIMITY:\s*',''))}
  }
  if($line -match 'guest (?:Swap|Present)|retail (?:Swap|Present)|D3DDevice_Swap.*(?:PASS|entered)'){$present=$true}
  if($line -match 'STORAGE IO UNSUPPORTED|P6DQ ROCKET HARD STOP|BOUNDARY:|PHASE4C_BOUNDARY_|GUEST FAULT'){
    $blocked=$true;Write-Host ('[BLOCKER] '+$line)
    if(!$Details){
      $start=[Math]::Max(0,$i-5)
      for($j=$start;$j -lt $i;$j++){Write-Host ('  '+$lines[$j])}
    }
  }
  if($line -match 'ticks=([0-9]+)'){
    $v=[long]$Matches[1];if($v -gt $ticks){$ticks=$v}
  }
  if($line -match '(?:fault|guest_faults)=([0-9]+)'){
    $v=[int]$Matches[1];if($v -gt $fault){$fault=$v}
  }
}
$delta=$ticks-$BaselineTicks
if($PixelsConfirmed){$grade='HOLY SHIT';$reason='Pixels visually confirmed'}
elseif($present -and $display -gt 0 -and $frame -ne '00000000'){$grade='A++';$reason='Guest presentation and framebuffer observed'}
elseif($delta -ge 20000000 -and !$blocked -and $fault -eq 0){$grade='A+';$reason='Major clean advancement'}
elseif($delta -ge 5000000 -and $fault -eq 0){$grade='A';$reason='Massive tick jump'}
elseif($delta -gt 0 -or ($reads -ge 7 -and $fault -eq 0)){$grade='B';$reason='Progress but further blocker remains'}
else{$grade='C';$reason='No confirmed improvement beyond baseline'}
Write-Host ""
Write-Host "STATUS $grade | $reason"
Write-Host "Ticks: $ticks | Baseline: $BaselineTicks | Delta: $delta"
Write-Host "Async reads: $reads | Faults: $fault | Display calls: $display | Framebuffer: $frame"
if($blocked){Write-Host 'A blocking boundary was recorded'}
if(!$PixelsConfirmed){Write-Host 'Pixels NOT visually confirmed'}
