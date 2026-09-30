# Identify which process holds a lock on a file, via Windows Restart Manager.
# No non-ASCII literals (PS 5.1 reads .ps1 as ANSI).

$root = Split-Path -Parent $PSScriptRoot
$target = Get-ChildItem -Path $root -Filter "*.pptx" -File |
          Sort-Object LastWriteTime | Select-Object -First 1
if (-not $target) { throw "no pptx found" }
Write-Output ("target: " + $target.FullName)

Add-Type -Language CSharp @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class FileLock
{
    [StructLayout(LayoutKind.Sequential)]
    struct RM_UNIQUE_PROCESS { public int dwProcessId; public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime; }

    const int RmRebootReasonNone = 0;
    const int CCH_RM_MAX_APP_NAME = 255;
    const int CCH_RM_MAX_SVC_NAME = 63;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct RM_PROCESS_INFO
    {
        public RM_UNIQUE_PROCESS Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_APP_NAME + 1)] public string strAppName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_SVC_NAME + 1)] public string strServiceShortName;
        public int ApplicationType;
        public uint AppStatus;
        public uint TSSessionId;
        [MarshalAs(UnmanagedType.Bool)] public bool bRestartable;
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    static extern int RmStartSession(out uint pSessionHandle, int dwSessionFlags, string strSessionKey);
    [DllImport("rstrtmgr.dll")]
    static extern int RmEndSession(uint pSessionHandle);
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    static extern int RmRegisterResources(uint pSessionHandle, uint nFiles, string[] rgsFilenames,
        uint nApplications, RM_UNIQUE_PROCESS[] rgApplications, uint nServices, string[] rgsServiceNames);
    [DllImport("rstrtmgr.dll")]
    static extern int RmGetList(uint dwSessionHandle, out uint pnProcInfoNeeded,
        ref uint pnProcInfo, [In, Out] RM_PROCESS_INFO[] rgAffectedApps, ref uint lpdwRebootReasons);

    public static List<string> Who(string path)
    {
        var result = new List<string>();
        uint handle; string key = Guid.NewGuid().ToString();
        if (RmStartSession(out handle, 0, key) != 0) return result;
        try
        {
            if (RmRegisterResources(handle, 1, new[] { path }, 0, null, 0, null) != 0) return result;
            uint pnProcInfoNeeded = 0, pnProcInfo = 0, reasons = 0;
            int res = RmGetList(handle, out pnProcInfoNeeded, ref pnProcInfo, null, ref reasons);
            if (res == 234 && pnProcInfoNeeded > 0)
            {
                var arr = new RM_PROCESS_INFO[pnProcInfoNeeded];
                pnProcInfo = pnProcInfoNeeded;
                if (RmGetList(handle, out pnProcInfoNeeded, ref pnProcInfo, arr, ref reasons) == 0)
                    for (int i = 0; i < pnProcInfo; i++)
                        result.Add(arr[i].Process.dwProcessId + " | " + arr[i].strAppName);
            }
        }
        finally { RmEndSession(handle); }
        return result;
    }
}
'@

$holders = [FileLock]::Who($target.FullName)
if ($holders.Count -eq 0) {
    Write-Output "no holder reported by Restart Manager"
} else {
    Write-Output "--- holders ---"
    $holders | ForEach-Object {
        $parts = $_ -split ' \| '
        $proc = Get-Process -Id $parts[0] -ErrorAction SilentlyContinue
        $exe = if ($proc) { $proc.Path } else { "(exited)" }
        Write-Output ("PID {0,-7} {1,-28} {2}" -f $parts[0], $parts[1], $exe)
    }
}
