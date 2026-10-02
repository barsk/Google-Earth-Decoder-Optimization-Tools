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

# The colour correction of a texture. In linear light (the physics of the capture): the haze (the light the atmosphere adds to
# every pixel, bluish: its colour removed per channel, (c - h) / (1 - h)), the white balance (gains of the red, green and blue
# channels from the temperature and the tint, normalized so that the luminance of a grey stays the same) and the brightness (an
# exposure factor). Then in sRGB (as seen): the contrast around the middle grey and the saturation (around the luminance). Each
# pixel independently, float32.
#
# Auto (estimate): the haze colour is the black point of each channel (nothing in the scene is darker than the haze light it
# adds), then the white balance makes the grey surfaces (roads, roofs, concrete: the least saturated pixels of mid brightness)
# grey, which is the white point of sRGB (D65, 6500 K).

import numpy as np

# settings (the COLOR_CORRECTION section of the project ini): factors (1 = unchanged), offsets (0 = unchanged), the haze colour
from constants import COLOR_CORRECTION_DEFAULTS

DEFAULTS = dict(COLOR_CORRECTION_DEFAULTS)
CORRECTION_ORDER = ("haze", "white balance", "brightness", "contrast", "saturation")
HAZE_LEVELS = ("color_haze_red", "color_haze_green", "color_haze_blue")
# the strength of the white balance at +-100 %: the red and blue gains (temperature), the green gain (tint)
TEMPERATURE_RANGE = 0.3
TINT_RANGE = 0.3
LUMINANCE = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
# the most of a channel removed as haze (linear)
MAX_HAZE = 0.5
# auto: the black point percentile, the pixels of the atlas padding left out (no channel above this sRGB level), the grey surfaces
BLACK_POINT_PERCENTILE = 0.5
PADDING_LEVEL = 3
GREY_LUMINANCE = (0.03, 0.7)
GREY_SHARE = 25


def parameters_from_settings(settings) -> dict:
    return {name: float(getattr(settings, name, default)) for name, default in DEFAULTS.items()}


def white_balance_gains(temperature: float, tint: float) -> np.ndarray:
    """The gains of the red, green and blue channels: warmer (temperature > 0) = more red, less blue; tint > 0 = magenta (less
    green). Normalized so that a grey keeps its luminance."""
    gains = np.array([1.0 + TEMPERATURE_RANGE * temperature, 1.0 - TINT_RANGE * tint, 1.0 - TEMPERATURE_RANGE * temperature], dtype=np.float64)
    gains = np.maximum(gains, 0.05)
    return (gains / float(gains @ LUMINANCE.astype(np.float64))).astype(np.float32)


def temperature_tint(gains) -> tuple:
    """The temperature and the tint of white balance gains (the inverse of white_balance_gains, up to the normalization)."""
    red, green, blue = (float(g) for g in gains)
    r, b = red / green, blue / green
    temperature = (r / b - 1.0) / (TEMPERATURE_RANGE * (r / b + 1.0))
    tint = (1.0 - (1.0 + TEMPERATURE_RANGE * temperature) / r) / TINT_RANGE
    return float(np.clip(temperature, -1.0, 1.0)), float(np.clip(tint, -1.0, 1.0))


def srgb_to_linear(c):
    return np.where(c <= np.float32(0.04045), c / np.float32(12.92), ((c + np.float32(0.055)) / np.float32(1.055)) ** np.float32(2.4))


def linear_to_srgb(c):
    c = np.clip(c, np.float32(0.0), np.float32(1.0))
    return np.where(c <= np.float32(0.0031308), c * np.float32(12.92), np.float32(1.055) * c ** np.float32(1.0 / 2.4) - np.float32(0.055))


def haze_veil(parameters: dict) -> np.ndarray:
    """The linear light removed from each channel: the haze colour (sRGB levels) times the haze strength."""
    levels = np.array([float(parameters.get(name, 0.0)) for name in HAZE_LEVELS], dtype=np.float32)
    strength = max(float(parameters.get("color_haze", 0.0)), 0.0)
    veil = srgb_to_linear(np.clip(levels, 0.0, 255.0) / np.float32(255.0)) * np.float32(strength)
    return np.minimum(veil, np.float32(MAX_HAZE)).astype(np.float32)


def is_neutral(parameters: dict) -> bool:
    p = {name: float(parameters.get(name, default)) for name, default in DEFAULTS.items()}
    return (abs(p["color_temperature"]) < 1e-6 and abs(p["color_tint"]) < 1e-6 and not haze_veil(p).any()
            and all(abs(p[name] - 1.0) < 1e-6 for name in ("color_brightness", "color_contrast", "color_saturation")))


def correct(rgb8: np.ndarray, parameters: dict) -> np.ndarray:
    """A uint8 RGB(A) image corrected (alpha unchanged)."""
    if is_neutral(parameters):
        return rgb8
    p = {name: float(parameters.get(name, default)) for name, default in DEFAULTS.items()}
    veil = haze_veil(p)
    gains = white_balance_gains(p["color_temperature"], p["color_tint"])
    brightness = np.float32(p["color_brightness"])
    contrast = np.float32(p["color_contrast"])
    saturation = np.float32(p["color_saturation"])
    out = rgb8.copy()
    color = rgb8[..., :3].astype(np.float32) / np.float32(255.0)
    # linear light: haze, white balance, brightness
    linear = np.maximum(srgb_to_linear(color) - veil, np.float32(0.0)) / (np.float32(1.0) - veil)
    linear *= gains
    linear *= brightness
    # sRGB: contrast, saturation
    color = linear_to_srgb(linear)
    color = (color - np.float32(0.5)) * contrast + np.float32(0.5)
    luminance = (color @ LUMINANCE)[..., None]
    color = luminance + (color - luminance) * saturation
    out[..., :3] = (np.clip(color, np.float32(0.0), np.float32(1.0)) * np.float32(255.0) + np.float32(0.5)).astype(np.uint8)
    return out


def white_balance_from_grey(rgb8: np.ndarray, parameters: dict) -> dict:
    """The grey picker: the temperature and the tint that make the mean of rgb8 (uint8 RGB pixels of surfaces known to be grey,
    from the original textures) grey, after the haze removal of parameters. Brightness, contrast and saturation keep a grey grey.
    Returns {"temperature", "tint", "before", "after"} (before and after: the mean as sRGB levels, without and with the gains)."""
    linear = srgb_to_linear(rgb8.reshape(-1, 3).astype(np.float32) / np.float32(255.0))
    veil = haze_veil(parameters)
    mean = (np.maximum(linear - veil, np.float32(0.0)) / (np.float32(1.0) - veil)).mean(axis=0).astype(np.float64)
    if mean.min() < 1e-4:
        raise ValueError("too dark to measure (after the haze removal)")
    temperature, tint = temperature_tint(mean[1] / mean)
    after = mean * white_balance_gains(temperature, tint)
    return dict(temperature=temperature, tint=tint, before=np.round(linear_to_srgb(mean.astype(np.float32)) * 255).astype(int).tolist(),
                after=np.round(linear_to_srgb(after.astype(np.float32)) * 255).astype(int).tolist())


def estimate(rgb8: np.ndarray) -> dict:
    """Auto: the haze colour and the white balance of sampled pixels (uint8 RGB, N x 3, the original textures). Returns the
    settings (haze 100 %, its colour, temperature, tint) and what was measured ("grey pixels", "grey before", "grey after")."""
    rgb8 = rgb8.reshape(-1, 3)
    rgb8 = rgb8[rgb8.max(axis=1) > PADDING_LEVEL]
    if len(rgb8) < 1000:
        raise ValueError("too few texture pixels to measure the colours (%d)" % len(rgb8))
    linear = srgb_to_linear(rgb8.astype(np.float32) / np.float32(255.0))
    veil = np.minimum(np.percentile(linear, BLACK_POINT_PERCENTILE, axis=0).astype(np.float32), np.float32(MAX_HAZE))
    dehazed = np.maximum(linear - veil, np.float32(0.0)) / (np.float32(1.0) - veil)
    # the grey surfaces: the least saturated pixels of mid brightness (after the haze removal)
    luminance = dehazed @ LUMINANCE
    srgb = linear_to_srgb(dehazed)
    saturation = (srgb.max(axis=1) - srgb.min(axis=1)) / np.maximum(srgb.max(axis=1), np.float32(1e-3))
    candidates = (luminance > GREY_LUMINANCE[0]) & (luminance < GREY_LUMINANCE[1])
    if candidates.sum() < 100:
        raise ValueError("too few pixels of mid brightness to measure the white balance")
    grey = candidates & (saturation <= np.percentile(saturation[candidates], GREY_SHARE))
    mean = dehazed[grey].mean(axis=0).astype(np.float64)
    temperature, tint = temperature_tint(mean[1] / mean)
    levels = np.round(linear_to_srgb(veil) * 255.0, 1)
    settings = {"color_haze": 1.0, "color_haze_red": float(levels[0]), "color_haze_green": float(levels[1]), "color_haze_blue": float(levels[2]),
                "color_temperature": round(temperature, 3), "color_tint": round(tint, 3)}
    after = mean * white_balance_gains(temperature, tint)
    return dict(settings=settings, grey_pixels=int(grey.sum()), pixels=len(rgb8),
                grey_before=np.round(linear_to_srgb(linear[grey].mean(axis=0)) * 255).astype(int).tolist(),
                grey_after=np.round(linear_to_srgb(after.astype(np.float32)) * 255).astype(int).tolist())
