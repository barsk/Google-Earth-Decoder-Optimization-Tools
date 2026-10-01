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

# Blender task of the shadow lightening: the textures of all the LODs of a tile corrected and installed (shadow_lighten.lighten_tile),
# with the capture sun of the tile chosen among the candidates; the log of the tile written as json
# {"tile": ..., "azimuth": ..., "elevation": ..., "sun": <how it was chosen>, "log": [...]}

import argparse
import json
import os
import site
import sys
import time

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

from shadow_lighten import lighten_tile, choose_sun, parse_suns, tile_placements, DEFAULT_PARAMETERS
from shadow_lighten.shadows import Originals
from shadow_lighten.sun import sun_vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
parser = argparse.ArgumentParser(prog="shadow_lighten_tile.py")
parser.add_argument("--folder", required=True, help="the modelLib folder of the project")
parser.add_argument("--name", required=True, help="the tile")
parser.add_argument("--objects_xml", required=True, help="the scene definition file of the project")
parser.add_argument("--originals_folder", required=True, help="the folder of the original textures")
parser.add_argument("--work_folder", required=True, help="a folder for the corrected textures before they are installed")
parser.add_argument("--suns", required=True, help="the capture suns: azimuth/elevation, ...")
parser.add_argument("--project_sun", required=True, help="the sun of the tiles that fit none: azimuth/elevation")
parser.add_argument("--step4_texture_folder", default=str(), help="the textures of step 4's backup, corrected too")
parser.add_argument("--output", required=True, help="the json file of the log")
parser.add_argument("--context_tile", default=str(), help="for a model that isn't a tile (a landmark object): its tile")
for name, value in DEFAULT_PARAMETERS.items():
    parser.add_argument("--" + name, type=float, default=value)
args = parser.parse_args(argv)

start = time.time()
placements = tile_placements(args.objects_xml, args.folder)
originals = Originals(os.path.join(args.folder, "texture"), args.originals_folder)
project_sun = parse_suns(args.project_sun)[0]
azimuth, elevation, how = choose_sun(args.folder, args.name, placements, originals.path, parse_suns(args.suns), project_sun)
parameters = {name: getattr(args, name) for name in DEFAULT_PARAMETERS}
log = lighten_tile(args.folder, args.name, placements, sun_vector(azimuth, elevation), parameters, args.originals_folder, args.work_folder,
                   args.step4_texture_folder if args.step4_texture_folder and os.path.isdir(args.step4_texture_folder) else None,
                   args.context_tile or None)
with open(args.output, "w", encoding="utf-8") as f:
    json.dump({"tile": args.name, "azimuth": azimuth, "elevation": elevation, "sun": how, "seconds": round(time.time() - start), "log": log}, f)
