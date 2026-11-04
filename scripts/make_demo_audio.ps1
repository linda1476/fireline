<#
.SYNOPSIS
  Synthesise the Fireline scenario script lines to WAV with Windows SAPI (System.Speech).

.DESCRIPTION
  Reads data/scenario.json (or -Scenario) and writes one 16 kHz mono 16-bit WAV per script
  line to -OutDir (default data/audio): {index:02d}_{responder_id}.wav, index 1-based.
  Each responder gets its own installed English voice when several exist; with a single
  English voice (typical: "Microsoft Zira Desktop") responders are told apart by SSML
  prosody (pitch) and SAPI rate. The radio band-pass / compression pass is applied
  afterwards by scripts/make_demo_audio.py (ffmpeg); this script only produces clean speech.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_demo_audio.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_demo_audio.ps1 -OutDir out/tts -Force
#>
param(
    [string]$Scenario = "",
    [string]$OutDir = "",
    [int]$Rate = 1,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $Scenario) { $Scenario = Join-Path $root "data\scenario.json" }
if (-not $OutDir) { $OutDir = Join-Path $root "data\audio" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Add-Type -AssemblyName System.Speech
$json = Get-Content -Raw -Encoding UTF8 $Scenario | ConvertFrom-Json
$lines = @($json.script)
if ($lines.Count -eq 0) { throw "no script lines in $Scenario" }

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo })
$english = @($voices | Where-Object { $_.Culture.Name -like "en*" })
if ($english.Count -eq 0) { $english = @($voices | Select-Object -First 1) }
if ($english.Count -eq 0) { throw "no SAPI voices installed" }
Write-Host ("voices: " + (($english | ForEach-Object { $_.Name }) -join ", "))

# One (voice, pitch, rate) profile per responder, assigned in roster order.
$pitches = @("+0%", "-12%", "+10%", "-6%", "+16%", "-18%", "+4%")
$rates = @(0, 1, -1, 2, 0, 1, -1)
$profiles = @{}
$i = 0
foreach ($r in @($json.responders)) {
    $profiles[$r.id] = @{
        voice = $english[$i % $english.Count].Name
        pitch = $pitches[$i % $pitches.Count]
        rate  = $Rate + $rates[$i % $rates.Count]
    }
    $i++
}

function Escape-Xml([string]$s) {
    return $s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace('"', "&quot;")
}

function Speakable([string]$s) {
    # Radio shorthand the engine would otherwise mangle.
    $s = $s -replace "\bRIT\b", "R.I.T."
    $s = $s -replace "\bEMS\b", "E.M.S."
    $s = $s -replace "\bPAR\b", "P.A.R."
    $s = $s -replace "(\d)-(\d)", '$1 $2'      # "1-2" -> "1 2"
    $dash = [string][char]0x2014                 # em dash (built at runtime: keep this file ASCII-only)
    $s = $s -replace ("\s*" + [regex]::Escape($dash) + "\s*"), ". "
    return $s
}

$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$written = @()
$index = 0
foreach ($line in $lines) {
    $index++
    $rid = [string]$line.responder_id
    $path = Join-Path $OutDir ("{0:d2}_{1}.wav" -f $index, $rid)
    if ((Test-Path $path) -and -not $Force) {
        Write-Host ("skip   {0} (exists; use -Force)" -f (Split-Path -Leaf $path))
        $written += $path
        continue
    }
    $p = $profiles[$rid]
    if (-not $p) { $p = @{ voice = $english[0].Name; pitch = "+0%"; rate = $Rate } }
    $text = Escape-Xml (Speakable ([string]$line.text))
    $ssml = @"
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
  <voice name="$($p.voice)"><prosody pitch="$($p.pitch)">$text</prosody></voice>
</speak>
"@
    $synth.Rate = [int]$p.rate
    $synth.SetOutputToWaveFile($path, $fmt)
    try {
        $synth.SpeakSsml($ssml)
    } finally {
        $synth.SetOutputToNull()
    }
    Write-Host ("wrote  {0}  [{1} pitch {2} rate {3}]" -f (Split-Path -Leaf $path), $p.voice, $p.pitch, $p.rate)
    $written += $path
}
$synth.Dispose()
Write-Host ("{0} file(s) in {1}" -f $written.Count, $OutDir)
