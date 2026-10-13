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
# Never brighter than the sunlit surfaces of its kind around (see shadows.facing_limits): where the mesh normals don't follow the
# photo (round tanks, lumpy roofs), texels in the sun were taken for the shaded side. The colour shift takes a blue cast away,
# down to grey, and never adds a warm one (a grey shaded side lit by the ground, hardly blue, turned yellow).

import math

import numpy as np

WALL_MAX_UP = 0.3           # walls: normals within this of horizontal
LUMINANCE = np.array([0.2126, 0.7152, 0.0722])
FIT_SAMPLES = 80000
MIN_BAND_SAMPLES = 200
# the colour shift goes at most to grey on the texels with a saturation (8 bits colour) up to the first value, fading out to none
# at the second (leaves, bricks: their colour shift as it is)
NEUTRAL_SATURATION = (0.15, 0.30)


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


def correction(normals, sun, ratios, knee, weights, gain_cap, color=1.0, limit=None, tint=None, neutral=None):
    # the surfaces lit at least up to the knee stay as they are, the others are brightened up to that level (never darker): the
    # brightness of the gain at most the gain cap, its colour shift kept at color, to the power of the weight of each texel (in
    # place: these arrays have a row per texel of a LOD00 texture). limit: per texel, the most its brightness may gain (see
    # shadows.facing_limits): the factor then brought towards 1, its colour shift with it. tint: per texel and channel, how far its
    # colour shift may go (to grey: the texel's brightness over the channel; NaN: no bound), neutral: how much of that bound applies
    facing = np.clip(normals @ sun, 0.0, knee)
    factor = (1.0 + ratios[None, :] * knee) / (1.0 + ratios[None, :] * facing[:, None])
    # (never darker, never undefined: a fit is checked before, see shadows.usable)
    factor = np.where(np.isfinite(factor), np.maximum(factor, 1.0), 1.0)
    brightness = factor @ LUMINANCE
    if color == 1.0:
        # (uncapped: the factor exactly as it is)
        factor *= (np.minimum(brightness, gain_cap) / brightness)[:, None]
    else:
        factor /= brightness[:, None]
        np.power(factor, color, out=factor)
        factor *= np.minimum(brightness, gain_cap)[:, None]
    if limit is not None:
        # over the limit: the brightness gain at the limit, the colour shift by the share of the gain left (a texel in the sun
        # taken for the shaded side was neutral: the warm shift of the sky lit side turned it yellow)
        brightness = factor @ LUMINANCE
        over = brightness > limit
        share = (limit[over] - 1.0) / (brightness[over] - 1.0)
        factor[over] = limit[over, None] * (factor[over] / brightness[over, None]) ** share[:, None]
    if tint is not None:
        # the colour shift of each channel between none and the one that makes the texel grey, on the near neutral texels (neutral:
        # 1, the bound in full; 0, saturated colours, e.g. leaves, the shift as it is: their blue channel is low against their
        # brightness, the bound kept the blue cast of the shaded leaves)
        bounded = ~np.isnan(tint[:, 0]) & (neutral > 0.0)
        brightness = factor[bounded] @ LUMINANCE
        shift = factor[bounded] / brightness[:, None]
        bound = tint[bounded].astype(np.float64)
        clipped = np.clip(shift, np.minimum(bound, 1.0), np.maximum(bound, 1.0))
        share = neutral[bounded][:, None]
        shift = clipped ** share * shift ** (1.0 - share)
        factor[bounded] = brightness[:, None] * shift / (shift @ LUMINANCE)[:, None]
    return factor ** weights[:, None]


def correct_facing(linear, srgb8, normal_map, smooth_map, covered, blocked, sun, ratios, knee, gain_cap, vegetation_strength, color=1.0, limit_map=None):
    # part 1 on a texture (linear colors, srgb8: the 8 bits colors): vegetation with the smoothed normals at its strength, the texels
    # in a cast shadow left as they are (part 2); limit_map: the most the brightness of each texel may gain (None: no limit). The
    # colour shift of each texel goes at most to grey
    out = linear.copy()
    # (only the texels it changes: the ones facing the sun up to the knee and those in a cast shadow keep their colour, a factor
    # of 1; the arrays of the others only, a LOD00 texture has ~22 million texels)
    ys, xs = np.nonzero(covered & ~blocked)
    green = vegetation(srgb8[ys, xs].astype(np.float32) / 255.0)
    normals = np.where(green[:, None], smooth_map[ys, xs], normal_map[ys, xs]).astype(np.float64)
    changed = normals @ sun < knee
    ys, xs, green, normals = ys[changed], xs[changed], green[changed], normals[changed]
    del changed
    weights = np.where(green, vegetation_strength, 1.0)
    limit = limit_map[ys, xs] if limit_map is not None else None
    own = linear[ys, xs]
    brightness = own @ LUMINANCE
    tint = np.where((brightness > 1e-4)[:, None], brightness[:, None] / np.maximum(own, 1e-6), np.nan)
    # the near neutral texels (saturation of the 8 bits colour below NEUTRAL_SATURATION): the bound to grey in full, fading out above
    srgb = srgb8[ys, xs].astype(np.float32)
    saturation = (srgb.max(axis=1) - srgb.min(axis=1)) / np.maximum(srgb.max(axis=1), 1.0)
    neutral = 1.0 - np.clip((saturation - NEUTRAL_SATURATION[0]) / (NEUTRAL_SATURATION[1] - NEUTRAL_SATURATION[0]), 0.0, 1.0)
    del own, brightness, srgb, saturation
    out[ys, xs] = linear[ys, xs] * correction(normals, sun, ratios, knee, weights, gain_cap, color, limit, tint, neutral)
    return out
