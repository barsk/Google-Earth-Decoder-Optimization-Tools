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

# The sun of the capture of the Google textures, from their cast shadows: for candidate sun directions, rays from texel samples
# towards the sun through the tile mesh (and its neighbours); the direction whose shadows match the dark texels best
# (point-biserial correlation of shadow and log luminance) is the sun of the capture. A scenery can come from several capture
# flights, which don't follow the tile or project borders: the capture suns are the groups of the good tile fits, and each tile
# takes the one that fits its own shadows best.

import math
import os
import statistics

import numpy as np
from mathutils import Vector
from PIL import Image

from .textures import load_triangles, load_occluders, srgb_to_linear, lum

GRID_AZIMUTHS = np.arange(0, 360, 10)
GRID_ELEVATIONS = np.arange(10, 61, 5)
GRID_SAMPLES = 12000
FINE_SAMPLES = 30000
CHOICE_SAMPLES = 12000
MIN_UP = 0.3                    # samples on surfaces facing up at least this much (ground, roofs)
RAY_OFFSET = 0.15               # meters off the surface, against self hits
RAY_LENGTH = 400.0
GOOD_FIT = 0.3                  # correlation of a good tile fit
GOOD_ELEVATIONS = (15, 55)      # a fit at the edge of the elevation range is a wrong fit (a cell gave 10 degrees next to 32)
CHOICE_MIN = 0.2                # the best candidate's correlation needed by a tile, else the project's sun
GROUP_AZIMUTH, GROUP_ELEVATION = 8.0, 5.0


def sun_vector(azimuth, elevation):
    # towards the sun, (east, north, up); azimuth clockwise from north
    a, el = math.radians(azimuth), math.radians(elevation)
    return np.array([math.sin(a) * math.cos(el), math.cos(a) * math.cos(el), math.sin(el)])


def sample_texels(triangles, uvs, normals_unused, images, owners, texture_path, count, rng):
    # random points of the textured surfaces facing up (triangles picked by their uv area): 3D point, face normal, log luminance
    e1, e2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    faces = np.cross(e1, e2)
    lengths = np.linalg.norm(faces, axis=1)
    valid = lengths > 1e-9
    faces[valid] /= lengths[valid, None]
    uv_area = 0.5 * np.abs((uvs[:, 1, 0] - uvs[:, 0, 0]) * (uvs[:, 2, 1] - uvs[:, 0, 1]) - (uvs[:, 2, 0] - uvs[:, 0, 0]) * (uvs[:, 1, 1] - uvs[:, 0, 1]))
    usable = valid & (faces[:, 2] >= MIN_UP) & (uv_area > 0) & (owners >= 0)
    index = np.flatnonzero(usable)
    if not len(index):
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0)
    chosen = rng.choice(index, size=count, p=uv_area[index] / uv_area[index].sum())
    r1, r2 = rng.random(count), rng.random(count)
    swap = r1 + r2 > 1
    r1[swap], r2[swap] = 1 - r1[swap], 1 - r2[swap]
    bary = np.column_stack([1 - r1 - r2, r1, r2])
    points = np.einsum("ij,ijk->ik", bary, triangles[chosen])
    uv = np.einsum("ij,ijk->ik", bary, uvs[chosen])
    luminance = np.zeros(count)
    for owner in np.unique(owners[chosen]):
        texture = load_texture(texture_path(images[owner]))
        height, width = texture.shape[:2]
        selected = owners[chosen] == owner
        px = np.clip((uv[selected, 0] % 1.0) * width, 0, width - 1).astype(int)
        py = np.clip((uv[selected, 1] % 1.0) * height, 0, height - 1).astype(int)
        luminance[selected] = lum(srgb_to_linear(texture[py, px]))
    return points, faces[chosen], np.log(np.maximum(luminance, 1e-4))


def load_texture(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def shadow_flags(bvh, points, normals, sun):
    facing_away = normals @ sun <= 0.0
    blocked = np.zeros(len(points), dtype=bool)
    direction = Vector(sun)
    origins = points + normals * RAY_OFFSET + sun * RAY_OFFSET
    for i in np.flatnonzero(~facing_away):
        if bvh.ray_cast(Vector(origins[i]), direction, RAY_LENGTH)[0] is not None:
            blocked[i] = True
    return blocked, facing_away


def correlation(shadow, luminance):
    # point-biserial correlation of being in shadow and being dark
    if not len(shadow):
        return 0.0
    fraction = shadow.mean()
    if fraction <= 0.01 or fraction >= 0.99 or luminance.std() <= 0:
        return 0.0
    return float((luminance[~shadow].mean() - luminance[shadow].mean()) * math.sqrt(fraction * (1 - fraction)) / luminance.std())


def tile_samples(model_lib_folder, tile, placements, texture_path, count, rng):
    triangles, uvs, normals, images, owners = load_triangles(os.path.join(model_lib_folder, tile + "_LOD00.gltf"))
    bvh = load_occluders(model_lib_folder, tile, placements, triangles)
    return bvh, sample_texels(triangles, uvs, normals, images, owners, texture_path, count, rng)


def estimate_tile_sun(model_lib_folder, tile, placements, texture_path):
    # the sun of a tile's capture: a coarse grid of directions, then a finer search around the best one with more samples.
    # Returns (azimuth, elevation, correlation)
    rng = np.random.default_rng(1)
    bvh, (points, normals, luminance) = tile_samples(model_lib_folder, tile, placements, texture_path, GRID_SAMPLES, rng)
    if not len(points):
        return 0.0, 0.0, 0.0
    best = (-2.0, 0.0, 0.0)
    for azimuth in GRID_AZIMUTHS:
        for elevation in GRID_ELEVATIONS:
            blocked, away = shadow_flags(bvh, points, normals, sun_vector(azimuth, elevation))
            best = max(best, (correlation(blocked | away, luminance), float(azimuth), float(elevation)))
    _, azimuth0, elevation0 = best
    points, normals, luminance = sample_texels(*load_triangles(os.path.join(model_lib_folder, tile + "_LOD00.gltf")), texture_path, FINE_SAMPLES, rng)
    fine = []
    for azimuth in np.arange(azimuth0 - 8, azimuth0 + 9, 2):
        for elevation in np.arange(max(elevation0 - 4, 3), elevation0 + 5, 1):
            blocked, away = shadow_flags(bvh, points, normals, sun_vector(azimuth, elevation))
            fine.append((correlation(blocked | away, luminance), float(azimuth % 360), float(elevation)))
    score, azimuth, elevation = max(fine)
    return azimuth, elevation, score


def choose_sun(model_lib_folder, tile, placements, texture_path, candidates, default_sun):
    # the capture sun of a tile among the candidates: the one whose shadows match the dark texels best, if its fit is clear
    # enough, else the default sun. Returns (azimuth, elevation, description)
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], "the only capture sun"
    bvh, (points, normals, luminance) = tile_samples(model_lib_folder, tile, placements, texture_path, CHOICE_SAMPLES, np.random.default_rng(2))
    scores = []
    for azimuth, elevation in candidates:
        blocked, away = shadow_flags(bvh, points, normals, sun_vector(azimuth, elevation))
        scores.append((correlation(blocked | away, luminance), azimuth, elevation))
    listing = ", ".join("%.0f/%.0f r %.2f" % (a, e, r) for r, a, e in scores)
    best = max(scores)
    if best[0] < CHOICE_MIN:
        return default_sun[0], default_sun[1], "the project's sun, no clear candidate: %s" % listing
    return best[1], best[2], "best candidate: %s" % listing


def good_fits(fits):
    # the fits correlated enough and not at the edge of the elevation range
    return [(a, e) for a, e, r in fits if r >= GOOD_FIT and GOOD_ELEVATIONS[0] <= e <= GOOD_ELEVATIONS[1]]


def capture_suns(fits):
    # the project's sun (median of the good fits) and the capture suns (the groups of at least 2 good fits, else the project's sun).
    # From the tile fits, not from medians: a project split between two flights has a median between them that isn't a capture
    good = good_fits(fits)
    if not good:
        return None, []
    median = lambda suns: (statistics.median(s[0] for s in suns), statistics.median(s[1] for s in suns))
    groups = []
    for sun in sorted(good):
        for group in groups:
            center = median(group)
            if angle_difference(center[0], sun[0]) <= GROUP_AZIMUTH and abs(center[1] - sun[1]) <= GROUP_ELEVATION:
                group.append(sun)
                break
        else:
            groups.append([sun])
    candidates = [median(g) for g in groups if len(g) >= 2]
    project_sun = median(good)
    return project_sun, candidates or [project_sun]


def angle_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


def parse_suns(text):
    # "azimuth/elevation, azimuth/elevation, ..." -> [(azimuth, elevation), ...]
    suns = []
    for item in str(text).replace(";", ",").split(","):
        if item.strip():
            azimuth, elevation = item.strip().split("/")
            suns.append((float(azimuth), float(elevation)))
    return suns


def format_suns(suns):
    return ", ".join("%.0f/%.0f" % sun for sun in suns)
