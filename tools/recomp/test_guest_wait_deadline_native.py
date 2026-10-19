"""Exercise production guest waits against controlled clocks and real Windows sleep."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

MOCK = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t DWORD; typedef int BOOL; typedef int BOOLEAN; typedef int NTSTATUS;
typedef uint64_t ULONGLONG; typedef struct {long long QuadPart;} LARGE_INTEGER;
#define TRUE 1
#define WAIT_IO_COMPLETION 192
#define STATUS_ALERTED 257
#define STATUS_SUCCESS 0
static long long us; static int fail_frequency, apc, sleeps, services, cost, max_slice;
static int merc_platform_query_performance_frequency(LARGE_INTEGER *v){v->QuadPart=1000000;return !fail_frequency;}
static int merc_platform_query_performance_counter(LARGE_INTEGER *v){v->QuadPart=us;return 1;}
static DWORD merc_platform_get_tick_count(void){return (DWORD)((us/16000)*16);}
static void service(void){services++;us+=cost;}
static void (*g_host_service_callback)(void)=service;
static DWORD merc_platform_sleep(DWORD ms, BOOL alertable){assert(ms>0 && ms<=16);us+=(long long)ms*1000;sleeps++;if((int)ms>max_slice)max_slice=ms;return alertable&&apc?WAIT_IO_COMPLETION:0;}
'''

HARNESS = r'''
static void reset(void){us=0;sleeps=services=cost=max_slice=fail_frequency=apc=0;g_host_service_callback=service;}
int main(void){
 for(int start=0;start<16000;start+=137){
  for(int duration=0;duration<=65;duration++){
   reset();us=start;
   assert(xbox_host_aware_sleep(duration,0)==STATUS_SUCCESS);
   assert(us-start==(long long)duration*1000);
   assert(services>=1 && max_slice<=16);
  }
 }
 reset();cost=20000;assert(xbox_host_aware_sleep(1,0)==STATUS_SUCCESS);assert(sleeps==0);
 reset();cost=400;assert(xbox_host_aware_sleep(17,0)==STATUS_SUCCESS);assert(us>=17000 && us<18800);
 reset();apc=1;assert(xbox_host_aware_sleep(100,1)==STATUS_ALERTED);assert(sleeps==1);
 reset();assert(xbox_host_aware_sleep(33,1)==STATUS_SUCCESS);assert(us==33000);
 reset();g_host_service_callback=0;assert(xbox_host_aware_sleep(1,0)==STATUS_SUCCESS);assert(us==1000);
 reset();fail_frequency=1;assert(xbox_host_aware_sleep(1,0)==STATUS_SUCCESS);assert(us==16000);
 puts("PASS: 7722 precise deadline/phase cases, callback cost, alertable APC, long waits and fallback");
}
'''

REAL = r'''
#define _WIN32_WINNT 0x0600
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
static ULONGLONG test_windows_tick64(void){
 typedef ULONGLONG (WINAPI *Fn)(void); static Fn fn;
 if(!fn) fn=(Fn)GetProcAddress(GetModuleHandleA("kernel32.dll"),"GetTickCount64");
 return fn();
}
typedef LONG NTSTATUS;
#define STATUS_SUCCESS 0
#define STATUS_ALERTED 257
static void (*g_host_service_callback)(void);
static BOOL merc_platform_query_performance_frequency(LARGE_INTEGER *v){return QueryPerformanceFrequency(v);}
static BOOL merc_platform_query_performance_counter(LARGE_INTEGER *v){return QueryPerformanceCounter(v);}
static DWORD merc_platform_get_tick_count(void){return (DWORD)test_windows_tick64();}
static DWORD merc_platform_sleep(DWORD ms, BOOL alertable){if(alertable)return SleepEx(ms,TRUE);Sleep(ms);return 0;}
'''

BENCH = r'''
static void old_wait(DWORD ms){ULONGLONG until=test_windows_tick64()+ms;while(test_windows_tick64()<until)Sleep(1);}
int main(void){
 LARGE_INTEGER f,a,b;QueryPerformanceFrequency(&f);timeBeginPeriod(1);
 QueryPerformanceCounter(&a);for(int i=0;i<128;i++)old_wait(1);QueryPerformanceCounter(&b);
 printf("old128x1ms=%.3fms\n",(b.QuadPart-a.QuadPart)*1000.0/f.QuadPart);
 QueryPerformanceCounter(&a);for(int i=0;i<128;i++)xbox_host_aware_sleep(1,0);QueryPerformanceCounter(&b);
 printf("precise128x1ms=%.3fms\n",(b.QuadPart-a.QuadPart)*1000.0/f.QuadPart);
 timeEndPeriod(1);return 0;
}
'''


def body():
    source = (ROOT / "src/kernel/kernel_thread.c").read_text(encoding="utf-8")
    start = source.index("static NTSTATUS xbox_host_aware_sleep(")
    return source[start:source.index("\n/* ===", start)]


def _gcc_like():
    for name in ("gcc", "clang"):
        found = shutil.which(name)
        if found:
            return found
    fallback = Path("C:/MinGW/bin/gcc.exe")
    return str(fallback) if fallback.is_file() else None


def _vcvars64():
    candidates = []
    pf86 = os.environ.get("ProgramFiles(x86)")
    if pf86:
        candidates.append(Path(pf86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe")
    candidates.append(Path("C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe"))

    for vswhere in candidates:
        if not vswhere.is_file():
            continue
        query = subprocess.run(
            [
                str(vswhere),
                "-latest",
                "-products", "*",
                "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property", "installationPath",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        install = query.stdout.strip()
        if query.returncode == 0 and install:
            vcvars = Path(install) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
            if vcvars.is_file():
                return vcvars
    return None


def _msvc_environment(vcvars: Path, workdir: Path):
    # Use a temporary .cmd instead of nesting a quoted batch-file path inside
    # cmd.exe /c. VS2019 Build Tools paths contain spaces and older cmd.exe
    # quoting rules can otherwise treat the quoted vcvars path as the command.
    activate = workdir / "activate-msvc.cmd"
    activate.write_text(
        '@echo off\r\n'
        f'call "{vcvars}" >nul\r\n'
        'if errorlevel 1 exit /b %errorlevel%\r\n'
        'set\r\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(activate)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)

    env = os.environ.copy()
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


def compile_c(source: Path, exe: Path, *, winmm=False):
    cc = _gcc_like()
    if cc:
        command = [cc, "-O2", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)]
        if winmm:
            command.append("-lwinmm")
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        return f"GCC/Clang: {cc}"

    vcvars = _vcvars64()
    if vcvars:
        env = _msvc_environment(vcvars, source.parent)
        cl = shutil.which("cl.exe", path=env.get("PATH"))
        if not cl:
            raise AssertionError(
                f"vcvars64.bat succeeded but cl.exe was not added to PATH: {vcvars}"
            )
        command = [cl, "/nologo", "/O2", "/W4", "/TC", str(source), f"/Fe:{exe}"]
        if winmm:
            command.append("winmm.lib")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
            cwd=source.parent,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        return f"MSVC via {vcvars}"

    raise AssertionError(
        "No C compiler found. Install/enable GCC, Clang, or Visual Studio C++ "
        "Build Tools. The verifier auto-detects MSVC through vswhere.exe."
    )


class WaitTests(unittest.TestCase):
    def test_production_deadlines(self):
        with tempfile.TemporaryDirectory(prefix="guest-wait-") as temp:
            source = Path(temp) / "test.c"
            exe = source.with_suffix(".exe")
            source.write_text(MOCK + body() + HARNESS, encoding="utf-8")
            compiler = compile_c(source, exe)
            result = subprocess.run(
                [str(exe)], check=True, capture_output=True, text=True, timeout=10
            )
            print(f"Compiler: {compiler}")
            print(result.stdout.strip())


def benchmark():
    with tempfile.TemporaryDirectory(prefix="guest-wait-real-") as temp:
        source = Path(temp) / "test.c"
        exe = source.with_suffix(".exe")
        source.write_text(REAL + body() + BENCH, encoding="utf-8")
        compiler = compile_c(source, exe, winmm=True)
        print(f"Compiler: {compiler}")
        subprocess.run([str(exe)], check=True, timeout=15)


if __name__ == "__main__":
    import sys
    if "--benchmark" in sys.argv:
        benchmark()
    else:
        unittest.main()
