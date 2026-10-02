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

# The tiles of a project shown in Blender's scene, with their textures, e.g. to judge the colours of a download (step 2) or the
# shadow lightening (step 2b) before the package is built. The tiles go into a collection of their own (replaced at each display),
# placed by their scenery objects (objects.xml) around the first one, north up. The 3D views show the textures as they are: solid
# shading, flat light, texture colours, the Standard view transform (no Filmic tone mapping).

import json
import math
import os
import re
import shutil
import tempfile

import bpy

from .scene import msfs_import_hooks_disabled

VIEW_COLLECTION = "GEDOT tiles"
VIEW_ROOT = "GEDOT tiles (north up)"
LANDMARK_PREFIX = "landmark_"


def _model_lods(model_lib_folder, name):
    # the LOD numbers of a model's files (LOD00 is the most detailed)
    pattern = re.compile(re.escape(name) + r"_LOD(\d\d)\.gltf$")
    return sorted(int(m.group(1)) for m in (pattern.match(f) for f in os.listdir(model_lib_folder)) if m)


def _wanted(name, tokens):
    # the tile of a landmark object is the end of its name; a token selects the tiles starting with it (a tile, a block, a cell)
    tile = name.rsplit("_", 1)[-1]
    return not tokens or any(tile.startswith(token) for token in tokens)


def _remove_view():
    collection = bpy.data.collections.get(VIEW_COLLECTION)
    if collection is not None:
        for obj in list(collection.all_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)
    # the meshes, materials and images of the previous display
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def _import_copy(model_file, texture_folder, work_folder):
    # a copy of the model whose buffer and textures point to their files (the models name their textures without folder, MSFS
    # finds them in the texture folder): the importer then loads each texture itself, instead of a shared placeholder
    with open(model_file, encoding="utf-8") as file:
        gltf = json.load(file)
    folder = os.path.dirname(model_file)
    for buffer in gltf.get("buffers", []):
        if "uri" in buffer and not buffer["uri"].startswith("data:"):
            buffer["uri"] = os.path.join(folder, buffer["uri"]).replace("\\", "/")
    for image in gltf.get("images", []):
        if "uri" in image and not image["uri"].startswith("data:"):
            name = os.path.basename(image["uri"])
            path = os.path.join(texture_folder, name) if os.path.isfile(os.path.join(texture_folder, name)) else os.path.join(folder, image["uri"])
            image["uri"] = path.replace("\\", "/")
    copy = os.path.join(work_folder, os.path.basename(model_file))
    with open(copy, "w", encoding="utf-8") as file:
        json.dump(gltf, file)
    return copy


def _textured(obj):
    for slot in obj.material_slots:
        material = slot.material
        if material is not None and material.use_nodes and any(node.type == "TEX_IMAGE" and node.image for node in material.node_tree.nodes):
            return True
    return False


def _set_views():
    names = [item.identifier for item in bpy.context.scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    if "Standard" in names:
        bpy.context.scene.view_settings.view_transform = "Standard"
    bpy.context.scene.view_settings.look = "None"
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "SOLID"
                    space.shading.light = "FLAT"
                    space.shading.color_type = "TEXTURE"
                    space.clip_end = 100000.0
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is not None:
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_all()


def display_tiles(model_lib_folder, objects_xml_path, lod_mode="finest", tile_filter="", log=print):
    """Imports the tiles (and the landmark objects) of a project into the scene. lod_mode: "finest" or "coarsest" LOD of each
    model; tile_filter: tile names or prefixes separated by commas or spaces (empty: all). Returns the number of models shown."""
    from shadow_lighten.textures import tile_placements
    from utils.placement import wgs84_to_tile

    placements = tile_placements(objects_xml_path, model_lib_folder)
    tokens = [token for token in re.split(r"[,;\s]+", tile_filter or "") if token]
    names = sorted(name for name in placements if (name.isdigit() or name.startswith(LANDMARK_PREFIX)) and _wanted(name, tokens))
    _remove_view()
    if not names:
        log("no tiles to show")
        return 0

    collection = bpy.data.collections.new(VIEW_COLLECTION)
    bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # the glTF axes of the tiles are (-east, up, north): imported in Blender, (-east, -north, up); the root turns them north up
    root = bpy.data.objects.new(VIEW_ROOT, None)
    collection.objects.link(root)
    root.rotation_euler = (0.0, 0.0, math.pi)
    reference = placements[names[0]]
    texture_folder = os.path.join(model_lib_folder, "texture")
    work_folder = tempfile.mkdtemp(prefix="gedot_view_")
    shown = 0
    for name in names:
        lods = _model_lods(model_lib_folder, name)
        if not lods:
            continue
        lod = lods[0] if lod_mode == "finest" else lods[-1]
        model_file = os.path.join(model_lib_folder, "%s_LOD%02d.gltf" % (name, lod))
        bpy.ops.object.select_all(action="DESELECT")
        with msfs_import_hooks_disabled():
            # (the images are found after the import, in the texture folder: not packed)
            bpy.ops.import_scene.gltf(filepath=_import_copy(model_file, texture_folder, work_folder), import_pack_images=False)
        imported = list(bpy.context.selected_objects)
        for obj in imported:
            # into the collection of the display (the importer may link them elsewhere)
            for other in list(obj.users_collection):
                other.objects.unlink(obj)
            collection.objects.link(obj)
        east, north, up = wgs84_to_tile(*placements[name], *reference)
        anchor = bpy.data.objects.new(name, None)
        collection.objects.link(anchor)
        anchor.parent = root
        anchor.location = (-east, -north, up)
        for obj in imported:
            if obj.parent is None:
                obj.parent = anchor
        shown += 1
        log("%s: LOD%02d" % (name, lod))

    shutil.rmtree(work_folder, ignore_errors=True)
    # (older imports: the textures named without folder)
    for image in bpy.data.images:
        if image.source == "FILE" and image.filepath and not os.path.isfile(bpy.path.abspath(image.filepath)):
            candidate = os.path.join(texture_folder, os.path.basename(bpy.path.abspath(image.filepath)))
            if os.path.isfile(candidate):
                image.filepath = candidate
                image.reload()
    # the meshes without texture (the tiles' bounding boxes for MSFS) would hide the tiles in the solid view
    for obj in list(collection.all_objects):
        if obj.type == "MESH" and not _textured(obj):
            obj.hide_set(True)
            obj.hide_render = True
    bpy.ops.object.select_all(action="DESELECT")
    _set_views()
    return shown
