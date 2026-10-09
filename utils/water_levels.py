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

# Sloped water (a stream down a hillside) or level water, for the water levels of steps 4 and 5. Google's water surface is noisy
# (Sundsta pond: its heights spread over 6 m around a level surface: reflections, boats, the trees over the shore), so the spread
# of the heights doesn't tell them apart: level water taken for a stream got noisy local levels (the Google water above the MSFS
# water, the beach above it). The typical height around each place (a low percentile of the heights within SLOPED_WATER_RADIUS:
# the noise averages out, the trees over the shore are left out) changes along a stream, not on level water.

import numpy as np
from scipy.spatial import cKDTree

from constants import SLOPED_WATER_RADIUS, SLOPED_WATER_SPREAD

# the typical height around a place: this percentile of the heights within the radius, from this many heights
LOCAL_PERCENTILE = 25
MIN_LOCAL_HEIGHTS = 5
# the places: one per square of this size
LOCAL_GRID = 10.0
MIN_HEIGHTS = 20


def local_spread(xy, heights, radius=SLOPED_WATER_RADIUS):
    """The spread (10th to 90th percentile) of the typical heights around the places of the water (0 with too few heights)."""
    xy, heights = np.asarray(xy, dtype=float).reshape(-1, 2), np.asarray(heights, dtype=float)
    if len(heights) < MIN_HEIGHTS:
        return 0.0
    tree = cKDTree(xy)
    centers = (np.unique(np.floor(xy / LOCAL_GRID).astype(np.int64), axis=0) + 0.5) * LOCAL_GRID
    typical = [np.percentile(heights[near], LOCAL_PERCENTILE) for near in tree.query_ball_point(centers, radius) if len(near) >= MIN_LOCAL_HEIGHTS]
    if len(typical) < 2:
        return 0.0
    return float(np.percentile(typical, 90) - np.percentile(typical, 10))


def is_sloped(xy, heights, radius=SLOPED_WATER_RADIUS):
    """The water slopes: its typical heights spread more than SLOPED_WATER_SPREAD."""
    return local_spread(xy, heights, radius) > SLOPED_WATER_SPREAD
