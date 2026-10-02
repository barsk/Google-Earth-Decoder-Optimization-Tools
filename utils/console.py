#  #
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#  #
#
#  <pep8 compliant>

import os

import bpy
import ctypes
import msvcrt
import subprocess

from ctypes import wintypes, windll

from constants import CLEAR_CONSOLE_CMD, EOL, CEND
from utils.isolated_print import isolated_print

KERNEL32_LIB = "kernel32"
USER32_LIB = "user32"
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOW = 5
SW_RESTORE = 9
MAX_LINES = 9999
# the size of the console window in characters (the titles are 100 wide)
CONSOLE_COLUMNS = 120
CONSOLE_ROWS = 35
CONSOLE_CMD = "CONOUT$"
CONSOLE_TYPE = "CONSOLE"
TITLE_LENGTH = 100
TITLE_FILL_CHAR = "-"

kernel32 = ctypes.WinDLL(KERNEL32_LIB, use_last_error=True)
user32 = ctypes.WinDLL(USER32_LIB, use_last_error=True)
kernel32.GetConsoleWindow.restype = wintypes.HWND
kernel32.GetLargestConsoleWindowSize.restype = wintypes._COORD
kernel32.GetLargestConsoleWindowSize.argtypes = (wintypes.HANDLE,)
kernel32.SetConsoleScreenBufferSize.argtypes = (wintypes.HANDLE, wintypes._COORD)
kernel32.SetConsoleWindowInfo.argtypes = (wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(wintypes.SMALL_RECT))
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)


def open_console():
    # clear the system console
    os.system(CLEAR_CONSOLE_CMD)

    get_console_window = windll.kernel32.GetConsoleWindow
    show_window = windll.user32.ShowWindow
    switch_to_this_window = windll.user32.SwitchToThisWindow
    is_window_visible = windll.user32.IsWindowVisible
    hwnd = get_console_window()

    try:
        # force system console toggle to ensure the new console window will not be closable
        bpy.ops.wm.console_toggle()
    except:
        pass

    if is_window_visible(hwnd):
        show_window(hwnd, SW_HIDE)
        switch_to_this_window(hwnd, True)  # display on Top
    else:
        show_window(hwnd, SW_SHOW)
        switch_to_this_window(hwnd, True)  # display on Top

    size_console(CONSOLE_COLUMNS, CONSOLE_ROWS, MAX_LINES)


def size_console(columns=CONSOLE_COLUMNS, rows=CONSOLE_ROWS, lines=MAX_LINES):
    # a normal console window (columns x rows characters, not maximized) with a long scroll back (lines)
    hwnd = kernel32.GetConsoleWindow()
    if not hwnd:
        return
    # out of a maximized window (the earlier GEDOT maximized it), else the window can't get smaller than the screen
    user32.ShowWindow(hwnd, SW_RESTORE)
    fd = os.open(CONSOLE_CMD, os.O_RDWR)
    try:
        handle = msvcrt.get_osfhandle(fd)
        largest = kernel32.GetLargestConsoleWindowSize(handle)
        if largest.X == 0 and largest.Y == 0:
            raise ctypes.WinError(ctypes.get_last_error())
        columns, rows = min(columns, largest.X), min(rows, largest.Y)
        window = wintypes.SMALL_RECT(0, 0, columns - 1, rows - 1)
        # the window first made small (it must fit in the buffer), then the buffer, then the window again (now it fits)
        kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(wintypes.SMALL_RECT(0, 0, 0, 0)))
        kernel32.SetConsoleScreenBufferSize(handle, wintypes._COORD(columns, max(lines, rows)))
        kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(window))
    finally:
        os.close(fd)
    subprocess.check_call("mode.com con cp select=65001")
    user32.ShowWindow(hwnd, SW_SHOWNORMAL)


def print_title(title):
    isolated_print(CEND + TITLE_FILL_CHAR*TITLE_LENGTH)
    title = " " + title + " "
    isolated_print(title.upper().center(TITLE_LENGTH, TITLE_FILL_CHAR))
    isolated_print(TITLE_FILL_CHAR*TITLE_LENGTH, EOL)
