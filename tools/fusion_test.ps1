# fusion_test.ps1 - drive Kega Fusion for automated smoke tests.
#
# Dot-source it, then script a session:
#   . .\tools\fusion_test.ps1
#   $f = Start-Fusion "s2disasm-master\s2built.bin"
#   Wait-Frames 480; Press Start; Shot $f "C:\path\title.png"; Stop-Fusion $f
#
# Keys follow Fusion.ini Player1Keys (DirectInput scancodes):
#   Up/Down/Left/Right = arrow keys, A/B/C = A/S/D keys, Start = Enter.
# Input goes to the foreground window, so Fusion is brought to the front
# before every key event. Don't use the keyboard while a test is running.

Add-Type -AssemblyName System.Drawing
if (-not ("FusionTest.Native" -as [type])) {
Add-Type -Namespace FusionTest -Name Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
'@
}

$script:FusionExe = "C:\Users\derps\Documents\Fusion\Fusion.exe"
# name -> @(scancode, extended)
$script:FusionKeys = @{
    Up = @(0x48, $true); Down = @(0x50, $true); Left = @(0x4B, $true); Right = @(0x4D, $true)
    A = @(0x1E, $false); B = @(0x1F, $false); C = @(0x20, $false); Start = @(0x1C, $false)
}

function Start-Fusion([string]$rom) {
    $p = Start-Process -FilePath $script:FusionExe -ArgumentList "`"$((Resolve-Path $rom).Path)`"" `
        -WorkingDirectory (Split-Path $script:FusionExe) -PassThru
    for ($i = 0; $i -lt 50 -and $p.MainWindowHandle -eq 0; $i++) { Start-Sleep -Milliseconds 100; $p.Refresh() }
    $script:FusionProc = $p
    Focus-Fusion
    return $p
}

function Focus-Fusion { [FusionTest.Native]::SetForegroundWindow($script:FusionProc.MainWindowHandle) | Out-Null }

# Approximate: Fusion runs at 60 fps, so frames/60 seconds.
function Wait-Frames([int]$frames) { Start-Sleep -Milliseconds ([int]($frames * 1000 / 60)) }

function Key-Down([string]$k) {
    $s = $script:FusionKeys[$k]; $flags = 0x0008; if ($s[1]) { $flags = $flags -bor 0x0001 }
    [FusionTest.Native]::keybd_event(0, [byte]$s[0], $flags, [UIntPtr]::Zero)
}
function Key-Up([string]$k) {
    $s = $script:FusionKeys[$k]; $flags = 0x0008 -bor 0x0002; if ($s[1]) { $flags = $flags -bor 0x0001 }
    [FusionTest.Native]::keybd_event(0, [byte]$s[0], $flags, [UIntPtr]::Zero)
}

# Tap a key: held for $frames frames (default 6), then released, then 6 frames' pause.
function Press([string]$k, [int]$frames = 6) {
    Focus-Fusion; Key-Down $k; Wait-Frames $frames; Key-Up $k; Wait-Frames 6
}

# Hold one or more keys together for $frames frames.
function Hold([string[]]$keys, [int]$frames) {
    Focus-Fusion; foreach ($k in $keys) { Key-Down $k }; Wait-Frames $frames; foreach ($k in $keys) { Key-Up $k }
}

function Shot($p, [string]$file) {
    $p.Refresh(); Focus-Fusion; Start-Sleep -Milliseconds 150
    $r = New-Object FusionTest.Native+RECT
    [FusionTest.Native]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
    $b = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
    $g = [System.Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, $b.Size)
    $b.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $b.Dispose()
}

function Stop-Fusion($p) { if (-not $p.HasExited) { $p | Stop-Process -Force } }
