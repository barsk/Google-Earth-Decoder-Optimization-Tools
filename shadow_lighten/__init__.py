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

# Shadow lightening of the Google Earth textures (step 2b, after the optimization): the textures have the sun of their capture
# baked in, and MSFS lights the tiles again, so that the sides facing the capture sun get too bright and the shaded sides too
# dark. Per tile: the capture sun (from the cast shadows), then the shaded sides of the walls, roofs and trees are brightened up
# to their lit side (facing.py), and the cast shadows partly lifted (shadows.py). Runs in Blender (its mathutils for the ray
# casting), but without any scene: it reads the glTF and texture files of the tiles.
# Settings (project ini, SHADOW_LIGHTENING section): wall_gain_cap, vegetation_strength, shadow_strength, shadow_color,
# shadow_gain_cap, shadow_vegetation_strength, sun_candidates (empty: estimated from the tiles).

from .shadows import lighten_tile, DEFAULT_PARAMETERS, LODS
from .sun import estimate_tile_sun, choose_sun, capture_suns, good_fits, parse_suns, format_suns
from .textures import tile_placements
