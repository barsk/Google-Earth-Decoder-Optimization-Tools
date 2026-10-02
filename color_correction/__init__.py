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

# Step 2a, colour correction of the Google Earth textures (downloaded as they are): haze (its colour measured by Auto), white
# balance (temperature, tint, set by Auto too), brightness, contrast, saturation. The textures of the project are corrected from
# their originals (kept in the backup folder), so that the step can be run again with other settings without stacking. Plain
# numpy (no Blender scene): the same formulas as the live preview of the viewer (shader nodes, see blender/view.py).

from .colors import (CORRECTION_ORDER, DEFAULTS, HAZE_LEVELS, correct, estimate, haze_veil, is_neutral, parameters_from_settings,
                     temperature_tint, white_balance_gains)
from .project import correct_textures, measure_textures, original_texture
