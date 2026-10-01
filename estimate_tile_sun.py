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

# Blender task of the shadow lightening: the capture sun of a tile (shadow_lighten.estimate_tile_sun), written as json:
# {"tile": ..., "azimuth": ..., "elevation": ..., "correlation": ...}

import argparse
import json
import os
import site
import sys

import bpy

if bpy.context.space_data is not None:
    sources_path = os.path.dirname(bpy.context.space_data.text.filepath)
else:
    sources_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(sources_path)
sys.path.append(site.USER_SITE)
for folder in (sources_path, os.path.join(sources_path, "constants"), os.path.join(sources_path, "utils"), os.path.join(sources_path, "scripts")):
    if folder not in sys.path:
        sys.path.append(folder)

from shadow_lighten import estimate_tile_sun, tile_placements
from shadow_lighten.shadows import Originals

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
parser = argparse.ArgumentParser(prog="estimate_tile_sun.py")
parser.add_argument("--folder", required=True, help="the modelLib folder of the project")
parser.add_argument("--name", required=True, help="the tile")
parser.add_argument("--objects_xml", required=True, help="the scene definition file of the project")
parser.add_argument("--originals_folder", required=True, help="the folder of the original textures")
parser.add_argument("--output", required=True, help="the json file of the result")
args = parser.parse_args(argv)

originals = Originals(os.path.join(args.folder, "texture"), args.originals_folder)
placements = tile_placements(args.objects_xml, args.folder)
azimuth, elevation, correlation = estimate_tile_sun(args.folder, args.name, placements, originals.path)
with open(args.output, "w", encoding="utf-8") as f:
    json.dump({"tile": args.name, "azimuth": azimuth, "elevation": elevation, "correlation": correlation}, f)
