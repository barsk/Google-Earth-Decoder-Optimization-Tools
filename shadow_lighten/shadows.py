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

# Shadow lightening of a tile: part 1 (the facing, facing.py), then part 2, the cast shadows, on every texture of every LOD, each
# texture with its own triangles; the fits and the lit reference come from LOD00 (over all its textures) and serve every LOD, so
# that the LODs match.
# Part 2: shadow likelihood of each texel = share of jittered rays towards the sun that are blocked by the tile and its
# neighbours (the mesh is coarser than the photo: a soft edge); lit reference = mean color of the lit LOD00 texels around the
# texel in 3D (the texture atlas has no geographic layout), a larger cell where too few; weight = likelihood x darkness against
# the reference (a lightly blurred luminance, full size: sharp edges, no mottling); brightening = one lit / shadow ratio per tile,
# capped as a whole (a cap per channel left a blue cast), never above what brings a texel to its reference (no halo at the
# edges), to the power of the shadow strength, with part of its color shift. Parts 1 and 2 are applied as one gain per texel,
# padded into the texels around the pieces of the atlas (the sim filters across them: uncorrected borders were dark cracks).
# The originals: <originals folder>\<texture>, and <texture>.installed with the md5 of the corrected texture that was installed:
# a current texture with that md5 is ours (its original is in the backup), any other one is a new original (e.g. after a rerun
# of step 2). The corrected textures also replace those of step 4's backup, so that a rerun of step 4 keeps them.

import hashlib
import json
import math
import os
import shutil
import statistics

import numpy as np
from mathutils import Vector
from PIL import Image

from .textures import load_triangles, load_occluders, rasterize, smooth_normals, srgb_from_8bit, srgb_to_linear, linear_to_srgb, lum, \
    smoothstep, upsample_smooth, box_blur, pad_gain, reference_cells, cell_means
from .facing import fit_ratio, vegetation, correct_facing, WALL_MAX_UP, FIT_SAMPLES
from .sun import RAY_OFFSET, RAY_LENGTH
from constants import SHADOW_LIGHTENING_DEFAULTS

LODS = ("LOD00", "LOD01", "LOD02", "LOD03")
JITTER_RADIUS = 1.2         # meters around the texel (horizontally) for the shadow likelihood rays
JITTER = ((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7))
REFERENCE_CELL = 4.0        # meters: lit reference over the 3 x 3 x 3 cells around a texel
FALLBACK_CELL = 12.0        # the same over larger cells, where the small ones have too few lit texels
MIN_REFERENCE = 20          # lit texels needed around a texel for its reference
MIN_SHADOW_PAIRS = 200      # confident shadow texels needed to measure a tile's lit / shadow ratio
DARKNESS_RANGE = (0.55, 0.9)  # luminance against the lit reference: fully a shadow below, not at all above
DARKNESS_BLUR = 2           # the luminance for the darkness blurred over 5 x 5 texels
SMOOTH_CELL = 2.0           # vegetation normals: averaged over the 3 x 3 x 3 cells of this size around a vertex
# the work size of the likelihood and the reference per LOD (upsampled), so that their texels are ~0.8 m on every LOD
# by rank: the most detailed LOD of the tile, the next one, ...
LOW_SCALES = (4, 2, 1, 1)
FITS_FOLDER = "fits"

DEFAULT_PARAMETERS = dict(SHADOW_LIGHTENING_DEFAULTS)


class Originals:
    # the original textures of the project (see the header)
    def __init__(self, texture_folder, originals_folder, step4_texture_folder=None):
        self.texture_folder, self.folder, self.step4_folder = texture_folder, originals_folder, step4_texture_folder
        os.makedirs(originals_folder, exist_ok=True)

    def __marker(self, name):
        return os.path.join(self.folder, name + ".installed")

    def __is_ours(self, name):
        current, marker = os.path.join(self.texture_folder, name), self.__marker(name)
        if not (os.path.isfile(current) and os.path.isfile(marker) and os.path.isfile(os.path.join(self.folder, name))):
            return False
        with open(marker, encoding="utf-8") as f:
            return f.read().strip() == md5(current)

    def path(self, name):
        # the original texture
        return os.path.join(self.folder, name) if self.__is_ours(name) else os.path.join(self.texture_folder, name)

    def install(self, name, corrected_file):
        current = os.path.join(self.texture_folder, name)
        if not self.__is_ours(name):
            shutil.copy2(current, os.path.join(self.folder, name))
        shutil.copyfile(corrected_file, current)
        if self.step4_folder and os.path.isfile(os.path.join(self.step4_folder, name)):
            shutil.copyfile(corrected_file, os.path.join(self.step4_folder, name))
        with open(self.__marker(name), "w", encoding="utf-8") as f:
            f.write(md5(current))


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def shadow_likelihood(bvh, point_map, normal_map, sun):
    # share of the jittered rays towards the sun that are blocked, for the covered texels facing the sun (NaN elsewhere)
    likelihood = np.full(point_map.shape[:2], np.nan, dtype=np.float32)
    ys, xs = np.nonzero(~np.isnan(point_map[..., 0]))
    direction = Vector(sun)
    offsets = [np.array([dx, dy, 0.0]) * JITTER_RADIUS for dx, dy in JITTER]
    for y, x in zip(ys, xs):
        n = normal_map[y, x].astype(np.float64)
        if n @ sun <= 0:
            continue
        base = point_map[y, x].astype(np.float64) + n * RAY_OFFSET + sun * RAY_OFFSET
        hits = 0
        for offset in offsets:
            if bvh.ray_cast(Vector(base + offset), direction, RAY_LENGTH)[0] is not None:
                hits += 1
        likelihood[y, x] = hits / len(offsets)
    return likelihood


def prepare_texture(originals, image_name, triangles, uvs, normals, bvh, sun, scale):
    # the maps of one texture from its own triangles: the texels covered by the mesh, normals, smoothed normals, the shadow likelihood.
    # A LOD00 texture has ~22 million texels (each float map of it 0.5 GB per 64 bits channel): the colors are kept as 8 bits and
    # converted where used, the maps freed as soon as they are no longer needed
    srgb8 = np.asarray(Image.open(originals.path(image_name)).convert("RGB"))
    height, width = srgb8.shape[:2]
    smoothed = smooth_normals(triangles, normals, SMOOTH_CELL)
    point_map, (normal_map, smooth_map) = rasterize(triangles, uvs, [normals, smoothed], width, height)
    covered = ~np.isnan(point_map[..., 0])
    del point_map
    linear = np.empty((height, width, 3))
    for c in range(3):
        linear[..., c] = srgb_to_linear(srgb_from_8bit(srgb8[..., c]).astype(np.float64))
    sw, sh = max(width // scale, 1), max(height // scale, 1)
    small_points, (small_normals,) = rasterize(triangles, uvs, [normals], sw, sh)
    small_likelihood = shadow_likelihood(bvh, small_points, small_normals, sun)
    # only over the texels of the mesh: the empty space around the pieces of the atlas would lower the likelihood along their
    # edges (dark "cracks" along the triangle edges in the sim)
    likelihood = np.nan_to_num(upsample_smooth(small_likelihood, height, width, valid=~np.isnan(small_likelihood)), nan=0.0)
    return {"name": image_name, "srgb8": srgb8, "linear": linear, "normal_map": normal_map, "smooth_map": smooth_map, "small_points": small_points,
            "small_likelihood": small_likelihood, "likelihood": likelihood, "covered": covered, "blocked": likelihood >= 0.5, "size": (sw, sh)}


def stored_fits(fits_folder):
    # the median fits of the tiles already done (for the tiles with too few walls or shadows to fit)
    ratios, knees, shadow_ratios = [], [], []
    for name in os.listdir(fits_folder) if os.path.isdir(fits_folder) else []:
        try:
            with open(os.path.join(fits_folder, name), encoding="utf-8") as f:
                fit = json.load(f)
        except (OSError, ValueError):
            continue
        if fit.get("ratios") is not None:
            ratios.append(fit["ratios"])
            knees.append(fit["knee"])
        if fit.get("shadow_ratio_raw") is not None:
            shadow_ratios.append(fit["shadow_ratio_raw"])
    median = lambda rows: [statistics.median(column) for column in zip(*rows)]
    return {"ratios": median(ratios) if ratios else None, "knee": statistics.median(knees) if knees else None,
            "shadow_ratio_raw": median(shadow_ratios) if shadow_ratios else None}


def correct_lod(model_lib_folder, tile, lod, placements, sun, fit, parameters, originals, fits_folder, log, context=None, rank=0):
    # parts 1 and 2 on the textures of one LOD (each with its own triangles); fit: None for LOD00 (fitted here, over all its
    # textures, and returned), else the LOD00 parameters. Returns [(image name, corrected texture, 8 bits)], the fit
    triangles, uvs, normals, images, owners = load_triangles(os.path.join(model_lib_folder, "%s_%s.gltf" % (tile, lod)))
    if not len(triangles):
        return [], fit
    bvh = load_occluders(model_lib_folder, tile, placements, triangles, context=context)
    textures = [prepare_texture(originals, name, triangles[owners == k], uvs[owners == k], normals[owners == k], bvh, sun, LOW_SCALES[min(rank, len(LOW_SCALES) - 1)])
                for k, name in enumerate(images) if (owners == k).any()]
    if not textures:
        return [], fit

    # part 1, the facing (the fit on the LOD00 walls out of the cast shadows, over all its textures)
    if fit is None:
        colors, facings = [], []
        rng = np.random.default_rng(1)
        for t in textures:
            ys, xs = np.nonzero(t["covered"] & ~t["blocked"] & (np.abs(t["normal_map"][..., 2]) < WALL_MAX_UP))
            pick = rng.choice(len(ys), size=min(FIT_SAMPLES // len(textures) + 1, len(ys)), replace=False)
            colors.append(t["linear"][ys[pick], xs[pick]])
            facings.append(t["normal_map"][ys[pick], xs[pick]].astype(np.float64) @ sun)
        ratios, knee = fit_ratio(np.concatenate(colors), np.concatenate(facings))
        fit = {"ratios": ratios, "knee": knee, "fitted": ratios is not None}
        if ratios is None:
            # too few walls in the tile: the median fit of the tiles already done, else no facing correction
            stored = stored_fits(fits_folder)
            fit["ratios"] = np.array(stored["ratios"]) if stored["ratios"] is not None else np.zeros(3)
            fit["knee"] = stored["knee"] if stored["knee"] is not None else 0.4
            log.append("part 1: too few walls to fit, %s" % ("the median fit of the tiles done" if stored["ratios"] is not None else "no facing correction"))
    for t in textures:
        t["part1"] = correct_facing(t["linear"], t["srgb8"], t.pop("normal_map"), t.pop("smooth_map"), t["covered"], t["blocked"], sun,
                                    fit["ratios"], fit["knee"], parameters["wall_gain_cap"], parameters["vegetation_strength"])
        # the low resolution texels facing the sun: 3D point, color after part 1, likelihood
        sw, sh = t["size"]
        sys_, sxs = np.nonzero(~np.isnan(t["small_likelihood"]))
        part1_srgb8 = np.empty(t["part1"].shape, dtype=np.uint8)
        for c in range(3):
            part1_srgb8[..., c] = (linear_to_srgb(t["part1"][..., c]) * 255).astype(np.uint8)
        small_colors = srgb_to_linear(np.asarray(Image.fromarray(part1_srgb8).resize((sw, sh), Image.BOX), dtype=np.float64) / 255.0)
        del part1_srgb8
        t["low"] = (sys_, sxs, t["small_points"][sys_, sxs].astype(np.float64), small_colors[sys_, sxs], t["small_likelihood"][sys_, sxs])

    # part 2, the cast shadows: lit reference in 3D from the lit LOD00 texels (of all its textures) for every LOD
    if fit.get("reference") is None:
        points = np.concatenate([t["low"][2][t["low"][4] < 0.2] for t in textures])
        colors = np.concatenate([t["low"][3][t["low"][4] < 0.2] for t in textures])
        fit["reference"] = reference_cells(points, colors, REFERENCE_CELL)
        fit["fallback"] = reference_cells(points, colors, FALLBACK_CELL)
    for t in textures:
        sys_, sxs, points, colors, p = t["low"]
        reference, counts = cell_means(fit["reference"], points)
        # where the small cells have too few lit texels, the larger ones (a correction that stops abruptly gave jagged edges)
        fallback, fallback_counts = cell_means(fit["fallback"], points)
        near = counts >= MIN_REFERENCE
        reference = np.where(near[:, None], reference, fallback)
        sw, sh = t["size"]
        reference_map = np.full((sh, sw, 3), np.nan)
        reference_map[sys_, sxs] = np.where((near | (fallback_counts >= MIN_REFERENCE))[:, None], reference, np.nan)
        t["reference_map"], t["pairs"] = reference_map, (reference, counts)
    if fit.get("shadow_ratio") is None:
        found = []
        for t in textures:
            _, _, _, colors, p = t["low"]
            reference, counts = t["pairs"]
            confident = (p >= 0.8) & (counts >= MIN_REFERENCE)
            darkness = lum(colors[confident]) / np.maximum(lum(reference[confident]), 1e-6)
            pairs = confident.nonzero()[0][darkness < 0.6]
            found.append(reference[pairs] / np.maximum(colors[pairs], 1e-5))
        found = np.concatenate(found)
        if len(found) >= MIN_SHADOW_PAIRS:
            ratio = np.median(found, axis=0)
            fit["shadow_fitted"] = True
        else:
            # too few shadows to measure (water, open ground): the median ratio of the tiles already done, else no brightening
            stored = stored_fits(fits_folder)
            ratio = np.array(stored["shadow_ratio_raw"]) if stored["shadow_ratio_raw"] is not None else np.ones(3) * 1.0001
            fit["shadow_fitted"] = False
            log.append("part 2: %d shadow texels only, %s" % (len(found), "the median ratio of the tiles done" if stored["shadow_ratio_raw"] is not None else "no brightening"))
        fit["shadow_ratio_raw"] = ratio
        fit["shadow_ratio"] = ratio * min(1.0, parameters["shadow_gain_cap"] / max(ratio.max(), 1e-6))
        fit["shadow_pairs"] = len(found)

    # the shadow weight at full size, the brightening, per texture (its maps freed as soon as they are no longer needed)
    results = []
    while textures:
        t = textures.pop(0)
        linear, part1, covered = t.pop("linear"), t.pop("part1"), t["covered"]
        height, width = linear.shape[:2]
        ref_big = upsample_smooth(t["reference_map"], height, width, valid=~np.isnan(t["reference_map"][..., 0]))
        ys, xs = np.nonzero(covered & ~np.isnan(ref_big[..., 0]))
        ref_lum = lum(ref_big[ys, xs])
        del ref_big
        blurred = box_blur(lum(part1), covered, DARKNESS_BLUR)
        q = blurred[ys, xs] / np.maximum(ref_lum, 1e-6)
        del blurred, ref_lum
        weight = smoothstep(t["likelihood"][ys, xs], 0.3, 0.7) * (1.0 - smoothstep(q, *DARKNESS_RANGE))
        weight *= np.where(vegetation(srgb_from_8bit(t["srgb8"][ys, xs])), parameters["shadow_vegetation_strength"], 1.0)
        ratio = fit["shadow_ratio"]
        ratio_lum = max(float(lum(ratio)), 1.0001)
        gain = 1.0 + weight * (np.clip(np.minimum(ratio_lum, 1.0 / np.maximum(q, 1e-6)), 1.0, None) - 1.0)
        exponent = parameters["shadow_strength"] * np.log(gain) / math.log(ratio_lum)
        tinted = ratio_lum * (ratio / ratio_lum) ** parameters["shadow_color"]
        brightness_before, brightness_part1 = lum(linear[covered]).mean(), lum(part1[covered]).mean()
        # parts 1 and 2 as one gain per texel (the part 2 texels: the part 1 color brightened, over the original color), padded
        # into the texels around the mesh pieces, applied to the whole texture
        gain_map = np.full(linear.shape, np.nan)
        gain_map[covered] = part1[covered] / np.maximum(linear[covered], 1e-6)
        gain_map[ys, xs] = (part1[ys, xs] * tinted[None, :] ** exponent[:, None]) / np.maximum(linear[ys, xs], 1e-6)
        del part1
        result = pad_gain(gain_map)
        del gain_map
        result *= linear
        del linear
        for c in range(3):
            result[..., c] = linear_to_srgb(result[..., c])
        log.append("%s %s: %dx%d, predicted shadow %.0f%%, brightened as shadow %.0f%%, mean brightness %.4f -> %.4f -> %.4f" % (
            lod, t["name"], width, height, 100 * (t["likelihood"][covered] >= 0.5).mean(), 100 * (weight > 0.5).sum() / max(covered.sum(), 1),
            brightness_before, brightness_part1, lum(srgb_to_linear(result[covered])).mean()))
        result8 = np.empty(result.shape, dtype=np.uint8)
        for c in range(3):
            result8[..., c] = (result[..., c] * 255 + 0.5).astype(np.uint8)
        results.append((t["name"], result8))
        del t, result
    return results, fit


def lighten_tile(model_lib_folder, tile, placements, sun, parameters, originals_folder, work_folder, step4_texture_folder=None,
                 context_tile=None):
    # parts 1 and 2 on every texture of every LOD of a tile, installed (the originals kept). Returns the log lines. context_tile:
    # for a model that isn't a tile (a landmark object), its tile (the geometry around it)
    parameters = dict(DEFAULT_PARAMETERS, **(parameters or {}))
    originals = Originals(os.path.join(model_lib_folder, "texture"), originals_folder, step4_texture_folder)
    fits_folder = os.path.join(originals_folder, FITS_FOLDER)
    os.makedirs(fits_folder, exist_ok=True)
    os.makedirs(work_folder, exist_ok=True)
    log, fit, corrected = [], None, []
    rank = 0  # the LODs present, from the most detailed (it may be LOD01, see finest_lod)
    for lod in LODS:
        if not os.path.isfile(os.path.join(model_lib_folder, "%s_%s.gltf" % (tile, lod))):
            continue
        results, fit = correct_lod(model_lib_folder, tile, lod, placements, sun, fit, parameters, originals, fits_folder, log, context_tile, rank)
        rank += 1
        for name, result8 in results:
            path = os.path.join(work_folder, name)
            Image.fromarray(result8).save(path)
            corrected.append((name, path))
        del results
    for name, path in corrected:
        originals.install(name, path)
        os.remove(path)
    if fit is not None:
        log.insert(0, "part 1: fully lit from facing %.2f, sun/sky ratio R %.2f G %.2f B %.2f; part 2: lit/shadow ratio R %.2f G %.2f B %.2f (measured %.2f %.2f %.2f) from %d texels" % (
            fit["knee"], *fit["ratios"], *fit["shadow_ratio"], *fit["shadow_ratio_raw"], fit["shadow_pairs"]))
        # the fits of the tile, for the tiles with too few walls or shadows (only the measured ones)
        with open(os.path.join(fits_folder, tile + ".json"), "w", encoding="utf-8") as f:
            json.dump({"ratios": [float(v) for v in fit["ratios"]] if fit.get("fitted") else None, "knee": fit["knee"] if fit.get("fitted") else None,
                       "shadow_ratio_raw": [float(v) for v in fit["shadow_ratio_raw"]] if fit.get("shadow_fitted") else None}, f)
    return log
