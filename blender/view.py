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
# the live colour correction (step 2a): a node group shared by the materials of the tiles shown, its settings in Value nodes inside it
COLOR_GROUP = "GEDOT colour correction"
COLOR_VALUES = ("haze_r", "haze_g", "haze_b", "gain_r", "gain_g", "gain_b", "brightness", "contrast", "saturation")
LUMINANCE = (0.2126, 0.7152, 0.0722)


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


def _import_copy(model_file, texture_folder, work_folder, originals_folder=None):
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
            if originals_folder and os.path.isfile(os.path.join(originals_folder, name)) and os.path.isfile(os.path.join(originals_folder, name + ".corrected")):
                # the live colours: the downloaded texture (the corrected one is in the texture folder)
                path = os.path.join(originals_folder, name)
            image["uri"] = path.replace("\\", "/")
    copy = os.path.join(work_folder, os.path.basename(model_file))
    with open(copy, "w", encoding="utf-8") as file:
        json.dump(gltf, file)
    return copy


class _Nodes:
    # node building helpers for the colour group (math on single values)
    def __init__(self, tree):
        self.tree = tree
        self.x = 0

    def math(self, operation, a, b=0.0, clamp=False):
        node = self.tree.nodes.new("ShaderNodeMath")
        node.operation = operation
        node.use_clamp = clamp
        node.location = (self.x, 0)
        self.x += 20
        for index, value in enumerate((a, b)):
            if isinstance(value, (int, float)):
                node.inputs[index].default_value = float(value)
            else:
                self.tree.links.new(value, node.inputs[index])
        return node.outputs[0]

    def srgb_to_linear(self, c):
        low = self.math("DIVIDE", c, 12.92)
        high = self.math("POWER", self.math("DIVIDE", self.math("ADD", c, 0.055), 1.055), 2.4)
        mask = self.math("LESS_THAN", c, 0.04045 + 1e-7)
        return self.math("ADD", high, self.math("MULTIPLY", self.math("SUBTRACT", low, high), mask))

    def linear_to_srgb(self, c):
        c = self.math("MINIMUM", self.math("MAXIMUM", c, 0.0), 1.0)
        low = self.math("MULTIPLY", c, 12.92)
        high = self.math("SUBTRACT", self.math("MULTIPLY", self.math("POWER", c, 1.0 / 2.4), 1.055), 0.055)
        mask = self.math("LESS_THAN", c, 0.0031308 + 1e-9)
        return self.math("ADD", high, self.math("MULTIPLY", self.math("SUBTRACT", low, high), mask))


def _color_group():
    # the colour correction of color_correction.colors in shader nodes: the input is the texture as stored (Non-Color: the sRGB
    # values), the output a linear colour for an emission shader (the Standard view transform shows the corrected sRGB values)
    group = bpy.data.node_groups.get(COLOR_GROUP)
    if group is not None and all(name in group.nodes for name in COLOR_VALUES):
        return group
    if group is not None:
        # the group of an older GEDOT (other settings): made again
        bpy.data.node_groups.remove(group)
    group = bpy.data.node_groups.new(COLOR_GROUP, "ShaderNodeTree")
    group.inputs.new("NodeSocketColor", "Color")
    group.outputs.new("NodeSocketColor", "Color")
    nodes = _Nodes(group)
    inputs = group.nodes.new("NodeGroupInput")
    outputs = group.nodes.new("NodeGroupOutput")
    values = {}
    for name in COLOR_VALUES:
        node = group.nodes.new("ShaderNodeValue")
        node.name = node.label = name
        node.outputs[0].default_value = 0.0 if name.startswith("haze") else 1.0
        values[name] = node.outputs[0]
    separate = group.nodes.new("ShaderNodeSeparateRGB")
    group.links.new(inputs.outputs["Color"], separate.inputs[0])
    channels = []
    for index, (haze, gain) in enumerate((("haze_r", "gain_r"), ("haze_g", "gain_g"), ("haze_b", "gain_b"))):
        linear = nodes.srgb_to_linear(separate.outputs[index])
        linear = nodes.math("DIVIDE", nodes.math("MAXIMUM", nodes.math("SUBTRACT", linear, values[haze]), 0.0), nodes.math("SUBTRACT", 1.0, values[haze]))
        linear = nodes.math("MULTIPLY", linear, values[gain])
        linear = nodes.math("MULTIPLY", linear, values["brightness"])
        srgb = nodes.linear_to_srgb(linear)
        channels.append(nodes.math("ADD", nodes.math("MULTIPLY", nodes.math("SUBTRACT", srgb, 0.5), values["contrast"]), 0.5))
    luminance = nodes.math("ADD", nodes.math("ADD", nodes.math("MULTIPLY", channels[0], LUMINANCE[0]), nodes.math("MULTIPLY", channels[1], LUMINANCE[1])),
                           nodes.math("MULTIPLY", channels[2], LUMINANCE[2]))
    combine = group.nodes.new("ShaderNodeCombineRGB")
    for index, channel in enumerate(channels):
        saturated = nodes.math("ADD", luminance, nodes.math("MULTIPLY", nodes.math("SUBTRACT", channel, luminance), values["saturation"]), clamp=True)
        group.links.new(nodes.srgb_to_linear(saturated), combine.inputs[index])
    group.links.new(combine.outputs[0], outputs.inputs["Color"])
    return group


def update_live_colors(settings):
    """The colour settings (a project's settings, COLOR_CORRECTION section) into the colour group of the tiles shown."""
    group = bpy.data.node_groups.get(COLOR_GROUP)
    if group is None:
        return
    from color_correction import haze_veil, parameters_from_settings, white_balance_gains
    parameters = parameters_from_settings(settings)
    gains = white_balance_gains(parameters["color_temperature"], parameters["color_tint"])
    veil = haze_veil(parameters)
    values = {"haze_r": float(veil[0]), "haze_g": float(veil[1]), "haze_b": float(veil[2]), "gain_r": float(gains[0]), "gain_g": float(gains[1]),
              "gain_b": float(gains[2]), "brightness": parameters["color_brightness"], "contrast": parameters["color_contrast"],
              "saturation": parameters["color_saturation"]}
    for name, value in values.items():
        group.nodes[name].outputs[0].default_value = value
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _live_material(material):
    # image -> colour group -> emission (unlit): the texture with the colour settings applied
    image_node = next((node for node in material.node_tree.nodes if node.type == "TEX_IMAGE" and node.image), None) if material.use_nodes else None
    if image_node is None:
        return
    image = image_node.image
    image.colorspace_settings.name = "Non-Color"
    tree = material.node_tree
    uv_links = [link.from_socket for link in tree.links if link.to_node == image_node]
    tree.nodes.clear()
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = image_node.interpolation if hasattr(image_node, "interpolation") else "Linear"
    group = tree.nodes.new("ShaderNodeGroup")
    group.node_tree = _color_group()
    emission = tree.nodes.new("ShaderNodeEmission")
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(texture.outputs["Color"], group.inputs["Color"])
    tree.links.new(group.outputs["Color"], emission.inputs["Color"])
    tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])


def _textured(obj):
    for slot in obj.material_slots:
        material = slot.material
        if material is not None and material.use_nodes and any(node.type == "TEX_IMAGE" and node.image for node in material.node_tree.nodes):
            return True
    return False


def _set_views(live=False):
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
                    # live colours: the materials (unlit emission) in Material Preview; else the textures in the solid view, flat light
                    space.shading.type = "MATERIAL" if live else "SOLID"
                    space.shading.light = "FLAT"
                    space.shading.color_type = "TEXTURE"
                    space.clip_end = 100000.0
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is not None:
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_all()


def display_tiles(model_lib_folder, objects_xml_path, lod_mode="finest", tile_filter="", log=print, live_colors=None, colors_originals_folder=None):
    """Imports the tiles (and the landmark objects) of a project into the scene. lod_mode: "finest" or "coarsest" LOD of each
    model; tile_filter: tile names or prefixes separated by commas or spaces (empty: all). live_colors: the project settings, to show
    the downloaded textures (colors_originals_folder: step 2a's originals) with their colour settings applied live (step 2a).
    Returns the number of models shown."""
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
            bpy.ops.import_scene.gltf(filepath=_import_copy(model_file, texture_folder, work_folder, colors_originals_folder if live_colors is not None else None),
                                      import_pack_images=False)
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
    if live_colors is not None:
        for material in {slot.material for obj in collection.all_objects if obj.type == "MESH" for slot in obj.material_slots if slot.material}:
            _live_material(material)
        update_live_colors(live_colors)
    bpy.ops.object.select_all(action="DESELECT")
    _set_views(live_colors is not None)
    return shown
