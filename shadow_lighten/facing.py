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

# Shadow lightening, part 1: the lighting by the facing of the surfaces (walls, roof slopes, tree crowns).
# Model: texture = material x (sky + sun x min(max(0, normal . sun), knee)): above the knee a surface is fully lit. The sun / sky
# ratio (per color channel) and the knee are fitted on the walls (surfaces facing sideways: similar materials whatever their
# direction), from the median color per band of normal . sun, leaving out the texels in a cast shadow.
# Correction: the lit side stays as it is, the shaded side is brightened up to its level, never darker (evening out both sides
# darkened the image and lost contrast): (1 + r x knee) / (1 + r x min(max(0, normal . sun), knee)). Its brightness (luminance)
# at most the gain cap, its colour (the shaded side is lit by the bluish sky only, the lit side by the warmer sun too) kept at
# the color share: capping each channel on its own made the gains of the three channels equal on the darkest sides, which then
# stayed blue. On vegetation (green texels, lumpy meshes: normals smoothed over the neighbouring cells) at a reduced strength.

import math

import numpy as np

WALL_MAX_UP = 0.3           # walls: normals within this of horizontal
LUMINANCE = np.array([0.2126, 0.7152, 0.0722])
FIT_SAMPLES = 80000
MIN_BAND_SAMPLES = 200


def fit_ratio(colors, facing):
    # per channel, the fit of the median color against the facing (normal . sun): color = base x (1 + ratio x min(facing, knee)),
    # the knee (where the walls are fully lit) common to the channels. Returns (ratios, knee), or (None, None) with too few walls
    bands = [(-1.01, 0.0)] + [(x, x + 0.1) for x in np.arange(0.0, 0.9, 0.1)]
    xs, ys, weights = [], [], []
    for low, high in bands:
        selected = (facing > low) & (facing <= high) if low >= 0 else facing <= 0.0
        count = int(selected.sum())
        if count < MIN_BAND_SAMPLES:
            continue
        xs.append(0.0 if low < 0 else float(np.mean(facing[selected])))
        ys.append(np.median(colors[selected], axis=0))
        weights.append(math.sqrt(count))
    if len(xs) < 2:
        return None, None
    xs, ys, weights = np.array(xs), np.array(ys), np.array(weights)
    best = None
    for knee in np.arange(0.2, 0.91, 0.05):
        design = np.column_stack([np.ones_like(xs), np.minimum(xs, knee)]) * weights[:, None]
        ratios, error = [], 0.0
        for channel in range(3):
            (base, slope), *_ = np.linalg.lstsq(design, ys[:, channel] * weights, rcond=None)
            ratios.append(slope / base)
            error += float(np.sum((design @ np.array([base, slope]) - ys[:, channel] * weights) ** 2)) / max(float(np.mean(ys[:, channel])), 1e-9) ** 2
        if best is None or error < best[0]:
            best = (error, np.array(ratios), float(knee))
    return best[1], best[2]


def vegetation(srgb_colors):
    # texels that look like vegetation (green dominant): their surfaces are lumpy, their normals unreliable
    r, g, b = srgb_colors[:, 0], srgb_colors[:, 1], srgb_colors[:, 2]
    return (g > r * 1.05) & (g > b * 1.15)


def correction(normals, sun, ratios, knee, weights, gain_cap, color=1.0):
    # the surfaces lit at least up to the knee stay as they are, the others are brightened up to that level (never darker): the
    # brightness of the gain at most the gain cap, its colour shift kept at color, to the power of the weight of each texel (in
    # place: these arrays have a row per texel of a LOD00 texture)
    facing = np.clip(normals @ sun, 0.0, knee)
    factor = (1.0 + ratios[None, :] * knee) / (1.0 + ratios[None, :] * facing[:, None])
    brightness = factor @ LUMINANCE
    if color == 1.0:
        # (uncapped: the factor exactly as it is)
        factor *= (np.minimum(brightness, gain_cap) / brightness)[:, None]
    else:
        factor /= brightness[:, None]
        np.power(factor, color, out=factor)
        factor *= np.minimum(brightness, gain_cap)[:, None]
    return factor ** weights[:, None]


def correct_facing(linear, srgb8, normal_map, smooth_map, covered, blocked, sun, ratios, knee, gain_cap, vegetation_strength, color=1.0):
    # part 1 on a texture (linear colors, srgb8: the 8 bits colors): vegetation with the smoothed normals at its strength, the texels
    # in a cast shadow left as they are (part 2)
    out = linear.copy()
    ys, xs = np.nonzero(covered)
    green = vegetation(srgb8[ys, xs].astype(np.float32) / 255.0)
    normals = np.where(green[:, None], smooth_map[ys, xs], normal_map[ys, xs]).astype(np.float64)
    weights = np.where(green, vegetation_strength, 1.0)
    weights[blocked[ys, xs]] = 0.0
    out[ys, xs] = linear[ys, xs] * correction(normals, sun, ratios, knee, weights, gain_cap, color)
    return out
