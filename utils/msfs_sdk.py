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

import subprocess

from constants import AUTO_MSFS_TARGET, MSFS_2020_TARGET, MSFS_2024_TARGET, MSFS_2024_SDK_PATH_HINT
from utils import ScriptError
from utils.install_lib import get_pref_value

MSFS_BUILD_EXE_FORCE_STEAM_OPTION = "-forcesteam"
MSFS_BUILD_EXE_OUTPUT_DIR_OPTION = "-outputdir"
MSFS_BUILD_EXE_OUTPUT_TO_SEPARATE_CONSOLE_OPTION = "-outputtoseparateconsole"
ERROR_MSG = "MSFS SDK tools not installed"


######################################################
# Microsoft Flight Simulator version the packages are built for
######################################################
def get_msfs_target():
    # set in the addon preferences, or deduced from the path of the package builder (MSFS 2024 if not set)
    msfs_target = get_pref_value("msfs_target", AUTO_MSFS_TARGET)
    if msfs_target != AUTO_MSFS_TARGET:
        return msfs_target

    msfs_build_exe_path = get_pref_value("msfs_build_exe_path", str())
    if msfs_build_exe_path and MSFS_2024_SDK_PATH_HINT not in msfs_build_exe_path:
        return MSFS_2020_TARGET

    return MSFS_2024_TARGET


def is_msfs_2024_target():
    return get_msfs_target() == MSFS_2024_TARGET


######################################################
# build scenery into new MSFS package
######################################################
def build_package(msfs_project):
    from UI.prefs import get_prefs
    prefs = get_prefs()
    msfs_build_exe_path = "\"" + prefs.msfs_build_exe_path + "\""

    if prefs.msfs_steam_version:
        msfs_build_exe_path += " " + MSFS_BUILD_EXE_FORCE_STEAM_OPTION

    try:
        print(msfs_build_exe_path + " " + MSFS_BUILD_EXE_OUTPUT_TO_SEPARATE_CONSOLE_OPTION + " \"" + msfs_project.project_definition_xml_path + "\" " + MSFS_BUILD_EXE_OUTPUT_DIR_OPTION + " \"" + msfs_project.project_folder + "\"")
        subprocess.run(msfs_build_exe_path + " " + MSFS_BUILD_EXE_OUTPUT_TO_SEPARATE_CONSOLE_OPTION + " \"" + msfs_project.project_definition_xml_path + "\" " + MSFS_BUILD_EXE_OUTPUT_DIR_OPTION + " \"" + msfs_project.project_folder + "\"", shell=True, check=False)
    except:
        raise ScriptError(ERROR_MSG)
