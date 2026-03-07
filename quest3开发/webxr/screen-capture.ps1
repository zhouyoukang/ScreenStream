# Quest 3 Screen Capture Daemon
# Captures the scrcpy Q3Mirror window using PrintWindow API
# Usage: powershell -File screen-capture.ps1 [-OutputPath path] [-IntervalMs ms]
param(
    [string]$OutputPath = "$env:TEMP\q3_frame.jpg",
    [string]$WindowTitle = "Q3Mirror",
    [int]$IntervalMs = 150
)

Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public class WindowCapture {
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left, Top, Right, Bottom;
    }

    public static bool Capture(string title, string outputPath) {
        IntPtr hwnd = FindWindow(null, title);
        if (hwnd == IntPtr.Zero) return false;

        RECT rc;
        GetWindowRect(hwnd, out rc);
        int w = rc.Right - rc.Left;
        int h = rc.Bottom - rc.Top;
        if (w <= 10 || h <= 10) return false;

        using (Bitmap bmp = new Bitmap(w, h, PixelFormat.Format24bppRgb)) {
            using (Graphics g = Graphics.FromImage(bmp)) {
                IntPtr hdc = g.GetHdc();
                PrintWindow(hwnd, hdc, 2); // PW_RENDERFULLCONTENT
                g.ReleaseHdc(hdc);
            }
            // Save with JPEG quality 75
            var encoder = GetEncoder(ImageFormat.Jpeg);
            var encoderParams = new EncoderParameters(1);
            encoderParams.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, 75L);
            bmp.Save(outputPath, encoder, encoderParams);
        }
        return true;
    }

    private static ImageCodecInfo GetEncoder(ImageFormat format) {
        foreach (ImageCodecInfo codec in ImageCodecInfo.GetImageDecoders()) {
            if (codec.FormatID == format.Guid) return codec;
        }
        return null;
    }
}
"@ -ReferencedAssemblies System.Drawing

Write-Host "[ScreenCapture] Started: window='$WindowTitle' output='$OutputPath' interval=${IntervalMs}ms"
$frameCount = 0
$startTime = Get-Date

while ($true) {
    try {
        $ok = [WindowCapture]::Capture($WindowTitle, $OutputPath)
        if ($ok) {
            $frameCount++
            if ($frameCount % 50 -eq 0) {
                $elapsed = ((Get-Date) - $startTime).TotalSeconds
                $fps = [math]::Round($frameCount / $elapsed, 1)
                Write-Host "[ScreenCapture] $frameCount frames, avg ${fps} fps"
            }
        }
    } catch {}
    Start-Sleep -Milliseconds $IntervalMs
}
