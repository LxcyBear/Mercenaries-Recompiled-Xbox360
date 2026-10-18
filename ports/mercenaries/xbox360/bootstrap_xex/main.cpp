/*
 * Mercenaries Xbox 360 - Phase 1 XDK bootstrap.
 *
 * INTENTIONALLY DOES NOT START THE GAME.
 * Uses the locally installed Xbox 360 XDK and Visual Studio Xbox 360
 * game-title project. No copied proprietary headers or libraries.
 *
 * The display may remain black: graphics initialization is a separate phase.
 * This diagnostic terminates after 15 seconds or when A is pressed.
 */

#include <xtl.h>
#include <string.h>

static HANDLE s_logFile = INVALID_HANDLE_VALUE;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    /* Debug output for a connected debugger / Xbox 360 Neighborhood. */
    OutputDebugStringA("[Merc360] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, length, &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

VOID __cdecl main()
{
    DWORD started;
    DWORD nextHeartbeat;
    BOOL controllerSeen = FALSE;
    BOOL exitByA = FALSE;

    /*
     * 'game:' should normally resolve to the launched title's directory.
     * Failure is nonfatal: debug output remains the primary logging path.
     * No configuration, game data or dashboard files are modified.
     */
    s_logFile = CreateFileA(
        "game:\\merc360-bootstrap.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("MERCENARIES XBOX 360 BOOTSTRAP START");
    if (s_logFile == INVALID_HANDLE_VALUE)
        trace("WARNING: game: log unavailable; use debug output");

    trace("No game code, XBE, renderer or guest memory initialized");
    trace("Press controller A to exit, or automatic timeout at 15 seconds");
    started = GetTickCount();
    nextHeartbeat = 1000;

    for (;;)
    {
        const DWORD elapsed = GetTickCount() - started;
        XINPUT_STATE state;
        DWORD result;

        if (elapsed >= 15000)
        {
            trace("TIMEOUT: 15-second safety exit");
            break;
        }

        ZeroMemory(&state, sizeof(state));
        result = XInputGetState(0, &state);
        if (result == ERROR_SUCCESS)
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

        if (elapsed >= nextHeartbeat)
        {
            trace("HEARTBEAT: title running");
            nextHeartbeat += 1000;
        }
        Sleep(33);
    }

    if (!controllerSeen)
        trace("RESULT: no controller-0 connection observed");
    if (!exitByA)
        trace("RESULT: exited by safety timeout");
    trace("MERCENARIES XBOX 360 BOOTSTRAP END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}
