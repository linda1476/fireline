import subprocess
from _common import AUDIO
LINES = {
 "i_kimhaneul.wav": ("Microsoft Heami Desktop", "긴급탈출, 긴급탈출, 긴급탈출. 여기 한빛구조대 소방장 김하늘. 대원고립, 천장 붕괴로 퇴로 차단. 2층 동쪽 끝 창고 선반 옆. 공기잔량 절반 이하, 사다리와 공기용기 필요."),
 "ii_nuri.wav": ("Microsoft Heami Desktop", "상황실, 여기 누리구조대. 맨다운 발생, 맨다운 발생. 1층 후면 출입구 안쪽 3미터, 대원 1명 쓰러짐."),
}
for name, (voice, text) in LINES.items():
    p = AUDIO / name
    tf = AUDIO / (name + ".txt")
    tf.write_text(text, encoding="utf-8")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{voice}')
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile('{p}', $fmt)
$t = [System.IO.File]::ReadAllText('{tf}', [System.Text.Encoding]::UTF8)
$s.Speak($t)
$s.Dispose()
"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    print(name, r.returncode, r.stderr[:300], p.stat().st_size if p.exists() else None)
