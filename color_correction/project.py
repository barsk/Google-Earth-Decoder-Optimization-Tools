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

from .colors import DEFAULTS, correct, is_neutral

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


def correct_textures(texture_folder, originals_folder, parameters, step4_texture_folder=None, shadow_originals_folder=None, threads=8,
                     log=print):
    """Corrects the textures of texture_folder. Returns {"corrected": n, "up to date": n, "new originals": n}."""
    os.makedirs(originals_folder, exist_ok=True)
    wanted = signature(parameters)
    neutral = is_neutral(parameters)
    names = sorted(name for name in os.listdir(texture_folder) if name.lower().endswith(TEXTURE_EXTENSIONS))
    counts = {"corrected": 0, "up to date": 0, "new originals": 0}
    lock = threading.Lock()

    def ours(name, current_md5, marker):
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

    def process(name):
        current = os.path.join(texture_folder, name)
        original = os.path.join(originals_folder, name)
        marker_path = original + MARKER_EXTENSION
        marker = _read_marker(marker_path)
        current_md5 = md5(current)
        if ours(name, current_md5, marker) and os.path.isfile(original):
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
