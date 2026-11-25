# Makes the Senada shortcut: in the app folder, and (unless -HereOnly) on the Desktop and in the Start
# menu. It opens the app straight from pythonw.exe with the Senada icon and carries the app's taskbar
# id (paths.APP_ID), so a pinned taskbar button keeps the Senada icon and reopens the app instead of a
# bare Python. setup.cmd runs this; running it again just refreshes the shortcuts.
param([switch]$HereOnly)
$ErrorActionPreference = 'Stop'
$app = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $app '.venv\Scripts\pythonw.exe'
$icon = Join-Path $app 'senada.ico'
if (-not (Test-Path $pythonw)) { throw 'Senada belum dipasang. Jalankan setup.cmd dulu.' }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

public static class SenadaShortcut {
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellLinkW {
        void GetPath(IntPtr a, int b, IntPtr c, int d);
        void GetIDList(out IntPtr a);
        void SetIDList(IntPtr a);
        void GetDescription(IntPtr a, int b);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string a);
        void GetWorkingDirectory(IntPtr a, int b);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string a);
        void GetArguments(IntPtr a, int b);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string a);
        void GetHotkey(out short a);
        void SetHotkey(short a);
        void GetShowCmd(out int a);
        void SetShowCmd(int a);
        void GetIconLocation(IntPtr a, int b, out int c);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string a, int b);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string a, int b);
        void Resolve(IntPtr a, int b);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string a);
    }

    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        void GetCount(out uint a);
        void GetAt(uint a, out PropertyKey b);
        void GetValue(ref PropertyKey a, IntPtr b);
        void SetValue(ref PropertyKey a, ref PropVariant b);
        void Commit();
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PropertyKey { public Guid fmtid; public uint pid; }

    [StructLayout(LayoutKind.Sequential)]
    struct PropVariant { public ushort vt; public ushort r1, r2, r3; public IntPtr value; public IntPtr pad; }

    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink { }

    public static void Save(string lnk, string target, string args, string dir, string icon, string appId, string about) {
        var link = (IShellLinkW)new ShellLink();
        link.SetPath(target);
        link.SetArguments(args);
        link.SetWorkingDirectory(dir);
        link.SetIconLocation(icon, 0);
        link.SetDescription(about);
        var key = new PropertyKey { fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
        var value = new PropVariant { vt = 31, value = Marshal.StringToCoTaskMemUni(appId) };
        try {
            var store = (IPropertyStore)link;
            store.SetValue(ref key, ref value);
            store.Commit();
        } finally {
            Marshal.FreeCoTaskMem(value.value);
        }
        ((IPersistFile)link).Save(lnk, true);
        Marshal.ReleaseComObject(link);
    }
}
'@

$about = 'Senada: terjemahan teks dan suara langsung, semuanya di komputer ini'
$places = @($app)
if (-not $HereOnly) {
    $places += [Environment]::GetFolderPath('Desktop')
    $places += [Environment]::GetFolderPath('Programs')
}
foreach ($place in $places) {
    $lnk = Join-Path $place 'Senada.lnk'
    [SenadaShortcut]::Save($lnk, $pythonw, '-m senada', $app, $icon, 'Artaniel901.Senada', $about)
    Write-Output "Shortcut: $lnk"
}
