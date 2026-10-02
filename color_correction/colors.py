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

# The colour correction of a texture. In linear light (the physics of the capture): the white balance (gains of the red, green
# and blue channels from the temperature and the tint, normalized so that the luminance of a grey stays the same), the haze
# (a veil of light added by the atmosphere, removed: (c - h) / (1 - h)) and the brightness (an exposure factor). Then in sRGB
# (as seen): the contrast around the middle grey and the saturation (around the luminance). Each pixel independently, float32.

import numpy as np

# settings (the COLOR_CORRECTION section of the project ini): factors (1 = unchanged) and offsets (0 = unchanged)
from constants import COLOR_CORRECTION_DEFAULTS

DEFAULTS = dict(COLOR_CORRECTION_DEFAULTS)
CORRECTION_ORDER = ("white balance", "haze", "brightness", "contrast", "saturation")
# the strength of the white balance at +-100 %: the red and blue gains (temperature), the green gain (tint)
TEMPERATURE_RANGE = 0.3
TINT_RANGE = 0.3
LUMINANCE = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def parameters_from_settings(settings) -> dict:
    return {name: float(getattr(settings, name, default)) for name, default in DEFAULTS.items()}


def is_neutral(parameters: dict) -> bool:
    return all(abs(float(parameters.get(name, default)) - default) < 1e-6 for name, default in DEFAULTS.items())


def white_balance_gains(temperature: float, tint: float) -> np.ndarray:
    """The gains of the red, green and blue channels: warmer (temperature > 0) = more red, less blue; tint > 0 = magenta (less
    green). Normalized so that a grey keeps its luminance."""
    gains = np.array([1.0 + TEMPERATURE_RANGE * temperature, 1.0 - TINT_RANGE * tint, 1.0 - TEMPERATURE_RANGE * temperature], dtype=np.float64)
    gains = np.maximum(gains, 0.05)
    return (gains / float(gains @ LUMINANCE.astype(np.float64))).astype(np.float32)


def srgb_to_linear(c):
    return np.where(c <= np.float32(0.04045), c / np.float32(12.92), ((c + np.float32(0.055)) / np.float32(1.055)) ** np.float32(2.4))


def linear_to_srgb(c):
    c = np.clip(c, np.float32(0.0), np.float32(1.0))
    return np.where(c <= np.float32(0.0031308), c * np.float32(12.92), np.float32(1.055) * c ** np.float32(1.0 / 2.4) - np.float32(0.055))


def correct(rgb8: np.ndarray, parameters: dict) -> np.ndarray:
    """A uint8 RGB(A) image corrected (alpha unchanged)."""
    if is_neutral(parameters):
        return rgb8
    p = {name: float(parameters.get(name, default)) for name, default in DEFAULTS.items()}
    gains = white_balance_gains(p["color_temperature"], p["color_tint"])
    haze = np.float32(min(max(p["color_haze"], 0.0), 0.9))
    brightness = np.float32(p["color_brightness"])
    contrast = np.float32(p["color_contrast"])
    saturation = np.float32(p["color_saturation"])
    out = rgb8.copy()
    color = rgb8[..., :3].astype(np.float32) / np.float32(255.0)
    # linear light: white balance, haze, brightness
    linear = srgb_to_linear(color) * gains
    linear = np.maximum(linear - haze, np.float32(0.0)) / (np.float32(1.0) - haze)
    linear *= brightness
    # sRGB: contrast, saturation
    color = linear_to_srgb(linear)
    color = (color - np.float32(0.5)) * contrast + np.float32(0.5)
    luminance = (color @ LUMINANCE)[..., None]
    color = luminance + (color - luminance) * saturation
    out[..., :3] = (np.clip(color, np.float32(0.0), np.float32(1.0)) * np.float32(255.0) + np.float32(0.5)).astype(np.uint8)
    return out
