/*
 * Mercenaries Xbox 360 - Phase 6A native Xenos surface proof.
 *
 * PURPOSE:
 *   Prove that our Xbox 360-native target can create the real Xbox 360 D3D
 *   device, clear the back buffer and present repeatable frames on hardware.
 *
 * THIS DOES NOT RUN MERCENARIES GAME CODE YET.
 * Phase 5 remains frozen as the runtime/ABI/storage/kernel baseline.
 *
 * Build with the locally installed Xbox 360 XDK. Do not commit XDK files.
 */

#include <xtl.h>
#include <d3d9.h>
#include <string.h>

static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static D3DDevice* s_device = NULL;

static void trace(const char* line)
{
    DWORD written = 0;
    const DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P6A] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, length, &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

static BOOL create_device()
{
    D3DPRESENT_PARAMETERS pp;
    HRESULT hr;

    ZeroMemory(&pp, sizeof(pp));

    /*
     * Conservative first-hardware-proof mode.
     * 640x480 matches the long-proven XDK sample baseline and avoids forcing
     * a display mode before we know our native presentation path is stable.
     */
    pp.BackBufferWidth = 640;
    pp.BackBufferHeight = 480;
    pp.BackBufferFormat = D3DFMT_A8R8G8B8;
    pp.BackBufferCount = 1;
    pp.MultiSampleType = D3DMULTISAMPLE_NONE;
    pp.MultiSampleQuality = 0;
    pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
    pp.hDeviceWindow = NULL;
    pp.Windowed = FALSE;

    /*
     * Depth is intentionally disabled in Phase 6A.
     * The first test proves display ownership + clear + present only.
     */
    pp.EnableAutoDepthStencil = FALSE;
    pp.AutoDepthStencilFormat = D3DFMT_UNKNOWN;
    pp.Flags = 0;
    pp.FullScreen_RefreshRateInHz = 0;
    pp.PresentationInterval = D3DPRESENT_INTERVAL_ONE;

    trace("CreateDevice: 640x480 A8R8G8B8, vsync, no depth");

    hr = Direct3D_CreateDevice(
        0,
        D3DDEVTYPE_HAL,
        NULL,
        D3DCREATE_HARDWARE_VERTEXPROCESSING,
        &pp,
        &s_device);

    if (FAILED(hr) || s_device == NULL)
    {
        trace("FAIL: Direct3D_CreateDevice");
        s_device = NULL;
        return FALSE;
    }

    trace("PASS: Direct3D_CreateDevice");
    return TRUE;
}

static BOOL clear_and_present(D3DCOLOR color)
{
    /*
     * Xbox 360 XDK D3D is C-style.  EDRAMClear=FALSE keeps this to the
     * ordinary render-target clear path for the first proof.
     */
    D3DDevice_Clear(
        s_device,
        0,
        NULL,
        D3DCLEAR_TARGET,
        color,
        1.0f,
        0,
        FALSE);

    D3DDevice_Present(s_device);
    return TRUE;
}

VOID __cdecl main()
{
    DWORD started;
    DWORD nextHeartbeat;
    DWORD frame = 0;
    BOOL controllerSeen = FALSE;
    BOOL exitByA = FALSE;

    s_logFile = CreateFileA(
        "game:\\merc360-phase6a.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 6A NATIVE XENOS SURFACE PROOF START");
    trace("BUILD TAG: P6A-XENOS-SURFACE-20261021-A");
    trace("Policy: native Xbox 360 D3D only; no guest renderer/game code");

    if (s_logFile == INVALID_HANDLE_VALUE)
        trace("WARNING: game: log unavailable; use xbWatson/debug output");

    if (!create_device())
    {
        trace("PHASE 6A RESULT: FAIL");
        goto shutdown;
    }

    /*
     * First visible proof:
     *   dark green -> blue -> red -> white, each held long enough to see.
     * We log only stage changes, not every frame.
     */
    trace("Present stage 0: dark green");
    clear_and_present(0xFF107C10);

    started = GetTickCount();
    nextHeartbeat = 1000;

    for (;;)
    {
        const DWORD elapsed = GetTickCount() - started;
        XINPUT_STATE state;
        DWORD inputResult;
        D3DCOLOR color;

        if (elapsed >= 15000)
        {
            trace("TIMEOUT: 15-second safety exit");
            break;
        }

        ZeroMemory(&state, sizeof(state));
        inputResult = XInputGetState(0, &state);
        if (inputResult == ERROR_SUCCESS)
        {
            if (!controllerSeen)
            {
                controllerSeen = TRUE;
                trace("Controller 0 detected");
            }

            if ((state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0)
            {
                exitByA = TRUE;
                trace("Controller A detected - exiting");
                break;
            }
        }

        if (elapsed < 3750)
        {
            color = 0xFF107C10;
        }
        else if (elapsed < 7500)
        {
            color = 0xFF0078D7;
            if (frame == 225)
                trace("Present stage 1: blue");
        }
        else if (elapsed < 11250)
        {
            color = 0xFFE81123;
            if (frame == 450)
                trace("Present stage 2: red");
        }
        else
        {
            color = 0xFFFFFFFF;
            if (frame == 675)
                trace("Present stage 3: white");
        }

        clear_and_present(color);
        ++frame;

        if (elapsed >= nextHeartbeat)
        {
            trace("HEARTBEAT: Xenos clear/present loop alive");
            nextHeartbeat += 1000;
        }
    }

    trace("PASS: native Xenos clear/present loop completed");
    trace("PHASE 6A RESULT: PASS");

shutdown:
    if (!controllerSeen)
        trace("RESULT: no controller-0 connection observed");
    if (!exitByA)
        trace("RESULT: exited by safety timeout or setup failure");

    trace("PHASE 6A NATIVE XENOS SURFACE PROOF END");

    /*
     * We intentionally do not experiment with manual device teardown in this
     * first proof. Process exit returns ownership to the dashboard and keeps
     * the test surface focused on CreateDevice/Clear/Present behavior.
     */
    s_device = NULL;

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}
