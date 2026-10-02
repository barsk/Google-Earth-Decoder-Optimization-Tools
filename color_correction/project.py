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

# The textures of a project corrected from their originals. Each corrected texture has a marker in the originals folder: the md5
# of the installed file and the settings used. A texture is up to date when it's the installed one (or step 2b's lightening of
# it) with the same settings; corrected again from its original when the settings changed; and taken as a new original when it
# changed otherwise (steps 2 and 4 rewrite the textures, new landmark objects). Step 4's backup gets the corrected textures too.

import hashlib
import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from .colors import DEFAULTS, correct, estimate, is_neutral

TEXTURE_EXTENSIONS = (".png", ".jpg", ".jpeg")
MARKER_EXTENSION = ".corrected"
SHADOW_MARKER_EXTENSION = ".installed"  # step 2b's markers (shadow_lighten.shadows.Originals)


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def signature(parameters):
    return json.dumps({name: round(float(parameters.get(name, default)), 4) for name, default in DEFAULTS.items()}, sort_keys=True)


def _read_marker(path):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def _save(image_array, path):
    image = Image.fromarray(image_array)
    if path.lower().endswith((".jpg", ".jpeg")):
        image.convert("RGB").save(path, quality=95)
    else:
        image.save(path)


def _is_ours(name, current_md5, marker, shadow_originals_folder):
    # the installed correction, or step 2b's lightening of it (2b's original is the installed correction)
    if marker is None:
        return False
    if current_md5 == marker.get("md5"):
        return True
    if shadow_originals_folder:
        shadow_marker = os.path.join(shadow_originals_folder, name + SHADOW_MARKER_EXTENSION)
        shadow_original = os.path.join(shadow_originals_folder, name)
        if os.path.isfile(shadow_marker) and os.path.isfile(shadow_original):
            with open(shadow_marker, encoding="utf-8") as file:
                if file.read().strip() == current_md5 and md5(shadow_original) == marker.get("md5"):
                    return True
    return False


def original_texture(texture_folder, originals_folder, name, shadow_originals_folder=None):
    """The downloaded texture of name: the original kept by step 2a when the installed one is its correction, else the one kept
    by step 2b when the installed one is its lightening, else the installed one."""
    current = os.path.join(texture_folder, name)
    current_md5 = md5(current)
    original = os.path.join(originals_folder, name)
    if os.path.isfile(original) and _is_ours(name, current_md5, _read_marker(original + MARKER_EXTENSION), shadow_originals_folder):
        return original
    if shadow_originals_folder:
        shadow_marker = os.path.join(shadow_originals_folder, name + SHADOW_MARKER_EXTENSION)
        shadow_original = os.path.join(shadow_originals_folder, name)
        if os.path.isfile(shadow_marker) and os.path.isfile(shadow_original):
            with open(shadow_marker, encoding="utf-8") as file:
                if file.read().strip() == current_md5:
                    return shadow_original
    return current


def measure_textures(texture_folder, originals_folder, shadow_originals_folder=None, prefixes=(), max_textures=300, pixels_per_texture=40000,
                     log=print):
    """Auto: the colour settings measured on the original textures (those of the tiles starting with one of prefixes, or all),
    see colors.estimate. A sample: at most max_textures textures, pixels_per_texture pixels of each."""
    names = sorted(name for name in os.listdir(texture_folder) if name.lower().endswith(TEXTURE_EXTENSIONS)
                   and (not prefixes or any(name.startswith(prefix) for prefix in prefixes)))
    if not names:
        raise ValueError("no textures to measure" + (" for the tiles %s" % ", ".join(prefixes) if prefixes else ""))
    random = np.random.default_rng(1)
    if len(names) > max_textures:
        names = sorted(random.choice(names, max_textures, replace=False))
    samples = []
    for name in names:
        with Image.open(original_texture(texture_folder, originals_folder, name, shadow_originals_folder)) as image:
            pixels = np.asarray(image.convert("RGB")).reshape(-1, 3)
        if len(pixels) > pixels_per_texture:
            pixels = pixels[random.choice(len(pixels), pixels_per_texture, replace=False)]
        samples.append(pixels)
    result = estimate(np.concatenate(samples))
    result["textures"] = len(names)
    s = result["settings"]
    log("auto colours, %d textures (%d grey pixels of %d): haze colour %g/%g/%g, temperature %+.0f %%, tint %+.0f %%; grey surfaces %s -> %s"
        % (len(names), result["grey_pixels"], result["pixels"], s["color_haze_red"], s["color_haze_green"], s["color_haze_blue"],
           100 * s["color_temperature"], 100 * s["color_tint"], result["grey_before"], result["grey_after"]))
    return result


def correct_textures(texture_folder, originals_folder, parameters, step4_texture_folder=None, shadow_originals_folder=None, threads=8,
                     log=print):
    """Corrects the textures of texture_folder. Returns {"corrected": n, "up to date": n, "new originals": n}."""
    os.makedirs(originals_folder, exist_ok=True)
    wanted = signature(parameters)
    neutral = is_neutral(parameters)
    names = sorted(name for name in os.listdir(texture_folder) if name.lower().endswith(TEXTURE_EXTENSIONS))
    counts = {"corrected": 0, "up to date": 0, "new originals": 0}
    lock = threading.Lock()

    def process(name):
        current = os.path.join(texture_folder, name)
        original = os.path.join(originals_folder, name)
        marker_path = original + MARKER_EXTENSION
        marker = _read_marker(marker_path)
        current_md5 = md5(current)
        if _is_ours(name, current_md5, marker, shadow_originals_folder) and os.path.isfile(original):
            if marker.get("settings") == wanted:
                with lock:
                    counts["up to date"] += 1
                return
        else:
            shutil.copy2(current, original)
            with lock:
                counts["new originals"] += 1
        with Image.open(original) as image:
            source = np.asarray(image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB"))
        result = source if neutral else correct(source, parameters)
        _save(result, current)
        if step4_texture_folder and os.path.isfile(os.path.join(step4_texture_folder, name)):
            shutil.copyfile(current, os.path.join(step4_texture_folder, name))
        with open(marker_path, "w", encoding="utf-8") as file:
            json.dump({"md5": md5(current), "settings": wanted}, file)
        with lock:
            counts["corrected"] += 1

    with ThreadPoolExecutor(max(1, threads)) as pool:
        for _ in pool.map(process, names):
            pass
    log("%d textures: %d corrected, %d up to date, %d new originals" % (len(names), counts["corrected"], counts["up to date"], counts["new originals"]))
    return counts
