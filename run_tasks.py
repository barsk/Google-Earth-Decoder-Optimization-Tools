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

# Runs several scripts in one Blender process (e.g. all the lods of a tile), so that Blender starts and loads the modules only
# once. The tasks file (json) lists the scripts and their parameters: [{"script": "cleanup_lod_3d_data.py", "params": [...]}, ...]

import json
import os
import runpy
import sys

import bpy


def clear_blender_data():
    # the objects, collections and unused data blocks of the previous script
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.context.scene.collection.children):
        bpy.context.scene.collection.children.unlink(collection)
    for _ in range(4):
        removed = 0
        for blocks in (bpy.data.collections, bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.images, bpy.data.node_groups, bpy.data.cameras, bpy.data.lights, bpy.data.curves):
            for block in list(blocks):
                if block.users == 0:
                    blocks.remove(block)
                    removed += 1
        if not removed:
            break


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if "--tasks_file" not in argv:
    raise SystemExit("run_tasks.py: --tasks_file argument not given, aborting.")

tasks_file_path = argv[argv.index("--tasks_file") + 1]
with open(tasks_file_path, "r") as file:
    tasks = json.load(file)

folder = os.path.dirname(os.path.abspath(__file__))
blender_argv = sys.argv[:sys.argv.index("--")]

for task in tasks:
    # each script reads its parameters after "--"
    sys.argv = blender_argv + ["--"] + task["params"]
    try:
        runpy.run_path(os.path.join(folder, task["script"]), run_name="__main__")
    except SystemExit:
        pass
    except Exception as ex:
        print("run_tasks.py:", task["script"], "failed:", ex)
    clear_blender_data()
