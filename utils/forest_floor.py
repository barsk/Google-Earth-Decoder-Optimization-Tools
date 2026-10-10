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

# The ground under the excluded ground (forests, woods...) for the height data of step 5: the MSFS terrain shows there instead of the
# 3d data. Google's 3d data of a forest is the top of the trees: the ground shows only in the gaps (paths, clearings) and around the
# forest. The heights from the top of the trees (the former method: a median of the surface, 1 m above it) left the terrain a few
# meters over the floor (Karlstad tile 30606160516271535: +2.4 m over the lowest surface seen, at the edge -3.9 to +7 m off the
# Google ground). The floor is put together from:
# - the ground around the excluded area (a ring outside it): the lowest surface there,
# - the gaps inside: where the lowest surface comes down to the floor that the trees' height gives,
# - far from both: the top of the trees minus their height, measured along the edge of the area (a forested hill stays a hill).
# It is interpolated from the first two, blended into the third with the distance, never above the lowest surface seen.

import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

# the surface around a point of the grid: the samples within this share of the grid's cell size; its lowest: this percentile
SURFACE_RADIUS = 0.75
LOWEST_PERCENTILE = 20
# the ring of ground around the excluded area (m)
RING_WIDTH = 30.0
# the trees' height: measured on the points of the area within this distance of the ring, over a plane fitted to the ring's ground
# within RING_PLANE_RADIUS (the ground interpolated across the area made a hill's trees 18 m instead of 12, the nearest ground of the
# ring 16.5 m), kept within these bounds, else the default
EDGE_BAND = 12.0
RING_PLANE_RADIUS = 25.0
TREE_HEIGHT_RANGE = (3.0, 35.0)
DEFAULT_TREE_HEIGHT = 12.0
MIN_TREE_SAMPLES = 10
# a point under the trees: its top this much above the ground seeds (m)
TREE_MIN_HEIGHT = 2.0
# the top of the trees smoothed over this radius (m), a gap: its lowest surface within this of the floor the trees give (m)
CANOPY_RADIUS = 20.0
GAP_TOLERANCE = 2.0
# the interpolated floor trusted near the seeds, the floor from the trees beyond (m)
SEED_TRUST = (10.0, 30.0)
# a light smoothing of the result (cells)
SMOOTHING = 1.5


def surface_heights(points_xy, samples, radius, statistic):
    """The statistic of the heights of the samples within radius of each point (nan without)."""
    tree = cKDTree(samples[:, :2])
    result = np.full(len(points_xy), np.nan)
    for i, near in enumerate(tree.query_ball_point(points_xy, radius)):
        if near:
            result[i] = statistic(samples[near, 2])
    return result


def forest_floor(points_xy, inside, low_samples, high_samples, cell):
    """The floor heights of the inside points (nan elsewhere) and a report.
    points_xy: (n, 2) the points of the height data grid, inside: (n,) the points in the excluded area, low_samples and high_samples:
    (m, 3) the original tile's surface seen from below and from above (rays: the vertices also count the skirts of Google's nodes,
    metres under the ground, which put the floor 5 m too low), with the heights of the result, cell: the grid's cell size."""
    points_xy, inside = np.asarray(points_xy, dtype=float), np.asarray(inside, dtype=bool)
    floor = np.full(len(points_xy), np.nan)
    if not inside.any() or len(low_samples) < 10 or len(high_samples) < 10:
        return floor, "no area"
    # (a low percentile, not the lowest: one stray ray down a hole would pull a seed down)
    lowest = surface_heights(points_xy, low_samples, SURFACE_RADIUS * cell, lambda heights: np.percentile(heights, LOWEST_PERCENTILE))
    top = surface_heights(points_xy, high_samples, SURFACE_RADIUS * cell, lambda heights: np.percentile(heights, 90))

    # the ground around the area: the outside points within the ring, their lowest surface
    inside_tree = cKDTree(points_xy[inside])
    ring_distance, _ = inside_tree.query(points_xy, distance_upper_bound=RING_WIDTH)
    ring = ~inside & np.isfinite(ring_distance) & ~np.isnan(lowest)
    inside_idx = np.flatnonzero(inside)
    in_xy = points_xy[inside_idx]

    def interpolate(seed_idx):
        values = griddata(points_xy[seed_idx], lowest[seed_idx], in_xy, method="linear") if len(seed_idx) >= 3 else np.full(len(in_xy), np.nan)
        missing = np.isnan(values)
        if missing.any() and len(seed_idx):
            values[missing] = griddata(points_xy[seed_idx], lowest[seed_idx], in_xy[missing], method="nearest")
        return values

    ring_idx = np.flatnonzero(ring)

    # the trees' height: along the edge, the top of the trees over the ground of the ring
    canopy = np.full(len(in_xy), np.nan)
    top_tree = cKDTree(points_xy[~np.isnan(top)])
    top_values = top[~np.isnan(top)]
    for i, near in enumerate(top_tree.query_ball_point(in_xy, CANOPY_RADIUS)):
        if near:
            canopy[i] = np.median(top_values[near])
    # (the ground under an edge point: a plane fitted to the ring's ground around it, the slope cancelled)
    to_ring, heights = np.full(len(in_xy), np.inf), np.full(len(in_xy), np.nan)
    if len(ring_idx):
        ring_tree = cKDTree(points_xy[ring_idx])
        to_ring = ring_tree.query(in_xy)[0]
        for i in np.flatnonzero(to_ring <= EDGE_BAND):
            near = ring_idx[ring_tree.query_ball_point(in_xy[i], RING_PLANE_RADIUS)]
            if len(near) >= 6:
                a = np.column_stack([points_xy[near] - in_xy[i], np.ones(len(near))])
                ground = np.linalg.lstsq(a, lowest[near], rcond=None)[0][2]
                heights[i] = top[inside_idx[i]] - ground
    band = (to_ring <= EDGE_BAND) & (heights > TREE_MIN_HEIGHT)
    tree_height = float(np.median(heights[band])) if band.sum() >= MIN_TREE_SAMPLES else DEFAULT_TREE_HEIGHT
    tree_height = float(np.clip(tree_height, *TREE_HEIGHT_RANGE))
    canopy_floor = canopy - tree_height

    # the gaps: the lowest surface down at the floor the trees give
    gap = (lowest[inside_idx] <= canopy_floor + GAP_TOLERANCE) & ~np.isnan(lowest[inside_idx])
    seed_idx = np.concatenate([ring_idx, inside_idx[gap]])
    interpolated = interpolate(seed_idx) if len(seed_idx) else canopy_floor

    # near the seeds the interpolation, far from them the trees
    to_seed = cKDTree(points_xy[seed_idx]).query(in_xy)[0] if len(seed_idx) else np.full(len(in_xy), np.inf)
    weight = np.clip((to_seed - SEED_TRUST[0]) / (SEED_TRUST[1] - SEED_TRUST[0]), 0.0, 1.0)
    result = np.where(np.isnan(canopy_floor), interpolated, (1.0 - weight) * interpolated + weight * canopy_floor)
    result = np.where(np.isnan(result), lowest[inside_idx], result)

    # a light smoothing, never above the lowest surface seen
    smoothed = result.copy()
    for i, near in enumerate(inside_tree.query_ball_point(in_xy, SMOOTHING * cell)):
        values = result[near]
        values = values[~np.isnan(values)]
        if len(values):
            smoothed[i] = values.mean()
    smoothed = np.fmin(smoothed, lowest[inside_idx])
    floor[inside_idx] = smoothed
    report = "%d points, %d ring and %d gap seeds, trees %.1f m%s" % (len(inside_idx), len(ring_idx), int(gap.sum()), tree_height,
                                                                     "" if band.sum() >= MIN_TREE_SAMPLES else " (default)")
    return floor, report
