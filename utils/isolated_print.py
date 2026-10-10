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

import sys
import os
import warnings


# one null device for the whole process, never closed. (A new one opened at each print freed the previous one while another thread
# still wrote to it: the output of the parallel tasks, __multithread_process_data's reader. An access violation in python310.dll
# killed Blender: Orebro cell 30606161417041, step 5)
DEVNULL = open(os.devnull, 'w')


def isolated_print(*args, **kwargs):
    warnings.simplefilter("ignore", ResourceWarning, append=True)
    sys.stdout = sys.__stdout__
    print(*args, **kwargs)
    sys.stdout = DEVNULL
