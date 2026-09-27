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

import os
import shutil
from math import floor, cos, radians
import json

from mathutils.bvhtree import BVHTree
from collections import defaultdict
from pathlib import Path
from utils.install_lib import install_python_lib
from utils.geo_pandas import create_latlon_gdf_from_meter_data
import warnings

warnings.simplefilter(action="ignore", category=UserWarning, append=True)
warnings.simplefilter(action="ignore", category=FutureWarning, append=True)
warnings.simplefilter(action="ignore", category=DeprecationWarning, append=True)
warnings.simplefilter(action="ignore", category=RuntimeWarning, append=True)

with warnings.catch_warnings():
    warnings.simplefilter(action="ignore", category=UserWarning, append=True)
    warnings.simplefilter(action="ignore", category=FutureWarning, append=True)
    warnings.simplefilter(action="ignore", category=DeprecationWarning, append=True)
    warnings.simplefilter(action="ignore", category=RuntimeWarning, append=True)

from constants import NUMPY_LIB, NUMPY_LIB_VERSION, PYGEODESY_LIB, SCIPY_LIB, SHAPELY_LIB

try:
    import numpy as np
except ModuleNotFoundError:
    install_python_lib(NUMPY_LIB, version=NUMPY_LIB_VERSION)
    import numpy as np

try:
    import pygeodesy
except ModuleNotFoundError:
    install_python_lib(PYGEODESY_LIB)
    import pygeodesy

try:
    import scipy
except ModuleNotFoundError:
    install_python_lib(SCIPY_LIB)
    import scipy

try:
    import shapely
except ModuleNotFoundError:
    install_python_lib(SHAPELY_LIB)
    import shapely

from scipy.interpolate import griddata
from scipy import ndimage

from pygeodesy.ellipsoidalKarney import LatLon
from scipy.spatial import cKDTree
from shapely import geometry

import bmesh
import bpy
import mathutils
from blender.blender_gis import import_osm_file, OSM_MATERIAL_NAME
from blender.image import get_image_node, fix_texture_size_for_package_compilation, pack_textures, list_image_nodes
from blender.memory import remove_mesh_from_memory
from blender.material import set_msfs_material, add_new_obj_material, get_material_output
from constants import EOL, GEOIDS_DATASET_FOLDER, EGM2008_5_DATASET, OBJ_FILE_EXT, BOUNDING_BOX_OSM_KEY, LESS_DETAILED_LODS_LIMIT, JPG_FILE_EXT, WATERLINE_SAMPLE_DISTANCE, GROUND_FILTER_MARGIN, HEIGHT_MAP_EDGE_BLEND_DISTANCE, HEIGHT_MAP_EDGE_CLEARANCE, HIGH_PRECISION_HEIGHT_OFFSET
from msfs_project.gltf import MsfsGltf
from utils import ScriptError, isolated_print
from utils.progress_bar import ProgressBar

SELECT_ACTION = "SELECT"
DESELECT_ACTION = "DESELECT"
ACTIVE_OBJ = "active_object"
SELECTED_OBJ = "selected_objects"
SELECTED_EDITABLE_OBJ = "selected_editable_objects"
MESH_OBJECT_TYPE = "MESH"
CURSOR_ORIGIN = "ORIGIN_CURSOR"
GEOMETRY_ORIGIN = "ORIGIN_GEOMETRY"
MEDIAN_POS = "MEDIAN"
BOUNDS_POS = "BOUNDS"
GLTF_SEPARATE_EXPORT_FORMAT = "GLTF_SEPARATE"
COPY_COLLECTION_NAME = "CopyCollection"
SUB_TILES_RANGE = "[0-7]"
TILE_LOD_SUFFIX = "_LOD0"
OBJECT_NAME_SEP = "_"
GEOID_HEIGHT_ORIGIN_MARGIN = 5.0
FACES_ONLY_DELETE_CONTEXT = "FACES_ONLY"
FACES_DELETE_CONTEXT = "FACES"
EDGES_FACES_DELETE_CONTEXT = "EDGES_FACES"
VERTICES_DELETE_CONTEXT = "VERTS"
GRIDS_COLLECTION_NAME = "grids"
HEIGHT_GRID_MATERIAL_NAME = "height_grid_material"
BOOLEAN_MODIFIER = "BOOLEAN"
DECIMATE_MODIFIER = "DECIMATE"
WEIGHTED_NORMAL_MODIFIER = "WEIGHTED_NORMAL"
REMESH_MODIFIER = "REMESH"
SUBSURFACE_MODIFIER = "SUBSURF"
COLLAPSE_DECIMATE_TYPE = "COLLAPSE"
SHARP_REMESH_MODE = "SHARP"
VOXEL_REMESH_MODE = "VOXEL"
SIMPLE_SUBSURFACE_DIVISION_TYPE = "SIMPLE"
EXACT_BOOLEAN_SOLVER = "EXACT"
GRID_FACTOR = 5


class BOOLEAN_MODIFIER_OPERATION:
    DIFFERENCE = "DIFFERENCE"
    INTERSECT = "INTERSECT"


class EXCLUSION_TYPE:
    GROUND = "GROUND"
    ROCKS = "ROCKS"
    WATER = "WATER"
    BUILDING = "BUILDING"


def keep_objects(objects_to_keep):
    if len(objects_to_keep) > 0:
        for obj_to_keep in objects_to_keep:
            obj_to_keep.select_set(False)


def clean_scene(objects_to_keep=[], keep_materials=False):
    if not bpy.data:
        return

    bpy.ops.object.select_all(action=SELECT_ACTION)

    keep_objects(objects_to_keep)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    if not keep_materials:
        for block in bpy.data.materials:
            if block.users == 0:
                bpy.data.materials.remove(block)

    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)

    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)

    bpy.ops.object.delete()

    # Now cycles through the dangling datablocks and remove them.
    for me in bpy.data.meshes:
        if not remove_mesh_from_memory(me.name):
            print("Unable to remove [%s]." % me.name)

    print(EOL)
    print("3d scene cleaned", EOL)


##################################################################
# Import the gltf files located in a specific folder
##################################################################
def import_model_files(model_files, clean=True, objects_to_keep=[]):
    if clean:
        clean_scene(objects_to_keep=objects_to_keep)

    for model_file in model_files:
        try:
            print("import ", model_file)
            bpy.ops.import_scene.gltf(filepath=str(model_file))
        except:
            continue

    if not objects_to_keep:
        # clean non mesh data
        objs = bpy.context.selected_objects
        bpy.ops.object.select_all(action=DESELECT_ACTION)

        for obj in objs:
            if obj.type != MESH_OBJECT_TYPE:
                obj.select_set(True)
                bpy.ops.object.delete()

        bpy.ops.object.select_all(action=SELECT_ACTION)


##############################################################################
# Export and optimize the tile in a new gltf file, with bin file and textures
##############################################################################
def export_to_optimized_gltf_files(file, texture_folder, use_selection=False, export_extras=True, apply_modifiers=False):
    isolated_print("export to", file, "with associated textures", EOL)

    bpy.ops.export_scene.gltf(export_format=GLTF_SEPARATE_EXPORT_FORMAT, export_extras=export_extras, export_keep_originals=True, filepath=file, export_texture_dir=texture_folder, use_selection=use_selection, use_mesh_edges=False, export_apply=apply_modifiers)
    model_file = MsfsGltf(file)
    model_file.clean_empty_meshes()
    model_file.fix_gltf_nodes()
    model_file.add_asobo_extensions()
    model_file.add_optimization_tag()
    model_file.dump()


##############################################################################
# Convert an obj file to a gltf file
##############################################################################
def convert_obj_file_to_gltf_file(file, output_folder, texture_folder, depth):
    file_name = os.path.basename(file).replace(OBJ_FILE_EXT, str())
    file_path = os.path.dirname(file)
    current_depth = depth
    while current_depth > 0:
        clean_scene()
        name_filter = file_name
        for i in range(0, current_depth - 1):
            name_filter = name_filter + SUB_TILES_RANGE
        for lod_file in Path(file_path).glob(name_filter + OBJ_FILE_EXT):
            lod_file_name = os.path.basename(lod_file).replace(OBJ_FILE_EXT, str())
            prior_objects = [obj for obj in bpy.context.scene.objects]
            bpy.ops.import_scene.obj(filepath=str(lod_file), axis_up='Z', axis_forward='-X')
            new_current_objects = [obj for obj in bpy.context.scene.objects]
            new_objects = set(new_current_objects) - set(prior_objects)
            for i, obj in enumerate(new_objects):
                obj.name = lod_file_name + "_" + str(i)

        set_msfs_material()
        # fix tile optimization placement by applying rotation on the imported tile
        bpy.ops.object.select_all(action=SELECT_ACTION)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        current_name = file_name + TILE_LOD_SUFFIX + str(depth - current_depth)
        bpy.ops.export_scene.gltf(export_format=GLTF_SEPARATE_EXPORT_FORMAT, filepath=output_folder + os.path.sep + current_name, export_texture_dir=texture_folder)
        current_depth -= 1
        clean_scene()


##################################################################
# Bake the tile texture files
##################################################################
def bake_texture_files(folder, file_name):
    error = False

    if not bpy.context.scene: return False

    # cleanup nodes with no materials
    objs = [obj for obj in bpy.context.scene.objects if not obj.material_slots]
    bpy.ops.object.delete({SELECTED_OBJ: objs})

    objects = bpy.context.scene.objects

    source_image_nodes = []
    for obj in list(bpy.context.scene.objects):
        image_node = get_image_node(obj)
        if image_node is not None and image_node.image is not None:
            source_image_nodes.append(image_node)
        else:
            bpy.data.objects.remove(obj, do_unlink=True)

    for node in source_image_nodes:
        if node.image is None:
            error = True

    if error is True:
        return False

    # pack the textures of the tile lod into a single texture, and remap the uvs to it
    packed_image = pack_textures(list(objects))
    if packed_image is None:
        return False

    # fix texture final size for package compilation
    fix_texture_size_for_package_compilation(packed_image)

    # save the pixels as is (save_render would apply the view transform of the scene)
    packed_image.filepath_raw = os.path.join(folder, file_name)
    packed_image.file_format = "JPEG" if file_name.lower().endswith(JPG_FILE_EXT) else "PNG"
    packed_image.save()

    # link the tile materials to the new packed texture
    link_materials_to_packed_texture(objects, folder, file_name)
    bpy.data.images.remove(packed_image)

    return True


##################################################################
# Repack the textures of a model, keeping only the part used by each object
##################################################################
def repack_model_textures(model_file_path, texture_folder, file_name):
    # e.g. for the 3d data isolated from a tile (a landmark), which only uses small parts of the tile packed texture.
    # The objects without texture (e.g. the bounding box of the tile) are kept as is
    import_model_files([model_file_path])

    # the models reference their textures by name, but they are in the texture folder
    for image in bpy.data.images:
        if image.source == "FILE" and not image.has_data:
            texture_file_path = os.path.join(os.path.dirname(model_file_path), texture_folder, os.path.basename(bpy.path.abspath(image.filepath)))
            if os.path.isfile(texture_file_path):
                image.filepath = texture_file_path
                image.reload()

    textured_objects = []
    for obj in bpy.context.scene.objects:
        if obj.type != MESH_OBJECT_TYPE or not obj.material_slots or obj.material_slots[0].material is None or obj.material_slots[0].material.node_tree is None:
            continue
        image_nodes = list_image_nodes(get_material_output(obj.material_slots[0].material))
        if image_nodes and image_nodes[0][0].image is not None:
            textured_objects.append(obj)

    packed_image = pack_textures(textured_objects, crop_per_object=True)
    if packed_image is None:
        return False

    fix_texture_size_for_package_compilation(packed_image)
    texture_file_path = os.path.join(os.path.dirname(model_file_path), texture_folder, file_name)
    packed_image.filepath_raw = texture_file_path
    packed_image.file_format = "JPEG" if file_name.lower().endswith(JPG_FILE_EXT) else "PNG"
    packed_image.save()
    bpy.data.images.remove(packed_image)

    image = bpy.data.images.load(texture_file_path)
    for obj in textured_objects:
        get_image_node(obj).image = image

    # keep the model files until the export succeeds (a failed export can remove them)
    model_files = [model_file_path] + [os.path.join(os.path.dirname(model_file_path), binary) for binary in MsfsGltf(model_file_path).get_buffers()]
    for file_path in model_files:
        shutil.copyfile(file_path, file_path + ".bak")
    try:
        # no extras: the MSFS materials of the imported models have image properties, which can't be exported as extras
        export_to_optimized_gltf_files(model_file_path, texture_folder, export_extras=False)
    except Exception:
        for file_path in model_files:
            shutil.move(file_path + ".bak", file_path)
        os.remove(texture_file_path)
        raise
    for file_path in model_files:
        os.remove(file_path + ".bak")
    return True


##################################################################
# link the tile materials to the new packed texture
##################################################################
def link_materials_to_packed_texture(objects, folder, file_name):
    img = bpy.data.images.load(os.path.join(folder, file_name))

    pbar = ProgressBar(bpy.context.scene.objects)
    for obj in pbar.iterable:
        material = obj.material_slots[0].material

        try:
            material.msfs_show_road_material = True
            material.msfs_show_collision_material = True
            material.msfs_show_day_night_cycle = True
            material.msfs_road_material = True
            material.msfs_collision_material = True
            material.msfs_day_night_cycle = True
        except AttributeError:
            pass

        source_image_nodes = [get_image_node(obj) for obj in objects]
        pbar.update("link packed texture to %s" % obj.name)
        # Update image in materials
        for node in source_image_nodes:
            node.image = img
            node.image.name = file_name


##################################################################
# Fix the tile bounding box
##################################################################
def fix_object_bounding_box(resize_box=True):
    if not bpy.context.scene: return

    create_collection = bpy.data.collections.new(name=COPY_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(create_collection)
    assert (create_collection is not bpy.context.scene.collection)

    # copy objects
    copy_objects(bpy.context.scene.collection, create_collection, False)

    obs = []
    for obj in create_collection.objects:
        if obj.type == MESH_OBJECT_TYPE:
            obs.append(obj)

    ctx = bpy.context.copy()

    if len(obs) < 1:
        return None

    ctx[ACTIVE_OBJ] = obs[0]

    ctx[SELECTED_OBJ] = obs

    # In Blender 2.8x this needs to be the following instead:
    ctx[SELECTED_EDITABLE_OBJ] = obs

    # join copied objects
    bpy.ops.object.join(ctx)

    bpy.ops.object.select_all(action=SELECT_ACTION)

    objects = bpy.context.scene.objects

    # fix objects origin: this also fixes the bounding box for the whole tile
    pbar = ProgressBar(objects)
    for obj in objects:
        center_origin(obj)
        pbar.update("bounded box updated for %s" % obj.name)

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    # remove joined copied objects
    for obj in create_collection.objects:
        obj.select_set(True)
        bpy.ops.object.delete()

    bpy.ops.object.select_all(action=SELECT_ACTION)

    for c in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.unlink(c)

    if resize_box:
        # resize objects to fix spacing between tiles
        bpy.ops.transform.resize(value=(1.0045, 1.0045, 1))


######################################################
# Fix meshes placement method
######################################################
def center_origin(obj):
    # Get active object
    act_obj = obj

    # Get cursor
    cursor = bpy.context.scene.cursor

    # Get original cursor location
    original_cursor_location = (cursor.location[0], cursor.location[1], cursor.location[2])

    # Make sure origin is set to geometry for cursor z move
    bpy.ops.object.origin_set(type=GEOMETRY_ORIGIN, center=BOUNDS_POS)

    print("act_obj.location:", act_obj.location)

    # Set cursor location to object location
    cursor.location = act_obj.location

    cursor.location[2] = original_cursor_location[2]

    # Get cursor x move
    half_act_obj_x_dim = act_obj.dimensions[0] / 2
    cursor_x_move = cursor.location[0] + half_act_obj_x_dim
    cursor.location[0] = cursor_x_move

    # Get cursor y move
    half_act_obj_y_dim = act_obj.dimensions[1] / 2
    cursor_y_move = cursor.location[1] + half_act_obj_y_dim
    cursor.location[1] = cursor_y_move

    # Set origin to cursor
    bpy.ops.object.origin_set(type=CURSOR_ORIGIN, center=MEDIAN_POS)

    # Reset cursor back to original location
    cursor.location = original_cursor_location

    # Assuming you're wanting object center to grid
    bpy.ops.object.location_clear(clear_delta=False)


def align_model_with_mask(model_file_path, positioning_file_path, mask_file_path, objects_to_keep=None):
    # not a mutable default argument: the positioning object is appended to the list, which must not survive the call
    objects_to_keep = [] if objects_to_keep is None else objects_to_keep
    if not bpy.context.scene:
        return False

    import_model_files([model_file_path], objects_to_keep=objects_to_keep)
    bpy.ops.object.select_all(action=SELECT_ACTION)
    objs = bpy.context.selected_objects
    bpy.ops.object.select_all(action=DESELECT_ACTION)
    mesh = None

    for obj in objs:
        if obj.type != MESH_OBJECT_TYPE:
            obj.select_set(True)
            bpy.ops.object.delete()
        else:
            mesh = obj

    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.select_all(action=SELECT_ACTION)
    keep_objects(objects_to_keep)

    bpy.ops.object.join()
    rot_z = 0.0

    import_osm_file(positioning_file_path)
    bpy.ops.transform.resize(value=(1.0045, 1.0045, 1))

    for obj in bpy.context.selected_objects:
        obj.name = "Ways"
        coords = [v.co for v in obj.data.vertices]
        p1 = coords[0]
        p2 = coords[1]
        Vector1 = (p1 - p2).normalized()
        proj_coords = [corner for corner in obj.bound_box]
        b2 = mathutils.Vector((proj_coords[2][0], proj_coords[2][1], proj_coords[2][2]))
        b4 = mathutils.Vector((proj_coords[6][0], proj_coords[6][1], proj_coords[6][2]))
        Vector2 = (b4 - b2).normalized()
        rot_z = Vector1.rotation_difference(Vector2).to_euler()
        obj.select_set(True)
        obj.rotation_euler = rot_z

    bpy.ops.object.align(bb_quality=True, align_mode='OPT_3', relative_to='OPT_2', align_axis={'X', 'Y'})

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    src = bpy.context.scene.objects.get("Ways")

    transform_x = src.matrix_world.translation[0]
    transform_y = src.matrix_world.translation[1]
    transform_z = src.matrix_world.translation[2]

    objects_to_keep.append(src)

    clean_scene(objects_to_keep=objects_to_keep)

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    import_osm_file(mask_file_path)
    for obj in bpy.context.selected_objects:
        obj.name = "Areas"
    target = bpy.context.scene.objects.get("Areas")
    bpy.ops.object.select_all(action=SELECT_ACTION)
    keep_objects(objects_to_keep)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.join()

    src.select_set(True)
    bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_2', align_axis={'Z'})
    apply_transform(target, use_location=True, use_rotation=False, use_scale=False)

    bpy.ops.transform.mirror(constraint_axis=(True, True, False), orient_type='GLOBAL')
    for obj in bpy.context.selected_objects:
        obj_loc_x = obj.location.x
        obj.location.x = obj_loc_x * -1

    target.rotation_euler = rot_z
    target.location[0] = transform_x
    target.location[1] = transform_y
    target.location[2] = transform_z

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    src.select_set(True)
    bpy.ops.object.delete()


def align_models_with_masks(model_files, positionings, mask):
    if not bpy.context.scene:
        return False

    objects_to_keep = []
    obj = None

    for i, model_file_path in enumerate(model_files):
        positioning = positionings[i]
        target = None
        mesh = None

        import_model_files([model_file_path], objects_to_keep=objects_to_keep)

        for obj in bpy.context.selected_objects:
            if obj.type != MESH_OBJECT_TYPE:
                obj.select_set(True)
                bpy.ops.object.delete()
            else:
                mesh = obj
                mesh.select_set(True)

        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.join()
        bpy.ops.transform.mirror(constraint_axis=(True, True, False), orient_type='GLOBAL')

        for obj in bpy.context.selected_objects:
            mesh = obj

        bpy.ops.object.select_all(action=DESELECT_ACTION)
        import_osm_file(positioning)
        for obj in bpy.context.selected_objects:
            obj.name = "Ways"
            target = obj

        mesh.select_set(True)
        target.select_set(True)
        bpy.context.view_layer.objects.active = target

        bpy.ops.object.align(bb_quality=True, align_mode='OPT_3', relative_to='OPT_4', align_axis={'X', 'Y'})

        bpy.ops.object.select_all(action=DESELECT_ACTION)
        target.select_set(True)
        bpy.ops.object.delete()

        bpy.ops.object.select_all(action=SELECT_ACTION)

        for obj in bpy.context.selected_objects:
            objects_to_keep.append(obj)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    import_osm_file(mask)

    for obj in bpy.context.selected_objects:
        obj.name = "Areas"

    bpy.ops.object.select_all(action=SELECT_ACTION)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_4', align_axis={'Z'})


def reduce_number_of_vertices(model_file_path):
    import_model_files([model_file_path], clean=False)
    objects = bpy.context.scene.objects

    for obj in objects:
        if add_decimate_modifier(obj, COLLAPSE_DECIMATE_TYPE, 0.75):
            for modifier in obj.modifiers:
                bpy.ops.object.modifier_apply(modifier=modifier.name)

    for obj in objects:
        bpy.context.view_layer.objects.active = obj
        weighted_normal = obj.modifiers.new(name="weighty", type=WEIGHTED_NORMAL_MODIFIER)

        if not weighted_normal:
            continue

        weighted_normal.weight = 50
        weighted_normal.thresh = 0.0
        weighted_normal.keep_sharp = True
        weighted_normal.use_face_influence = True
        for modifier in obj.modifiers:
            bpy.ops.object.modifier_apply(modifier=modifier.name)

    bpy.ops.object.select_all(action=SELECT_ACTION)


def get_mask_footprint(mask_name="Areas"):
    # the horizontal footprint of the (aligned, extruded) mask object
    from shapely.ops import unary_union

    mask = bpy.context.scene.objects.get(mask_name)
    if mask is None:
        return None

    mask_matrix = mask.matrix_world
    footprints = []
    for polygon in mask.data.polygons:
        if abs((mask_matrix.to_3x3() @ polygon.normal).z) < 0.5:
            continue
        points = [(mask_matrix @ mask.data.vertices[i].co).xy for i in polygon.vertices]
        if len(points) >= 3:
            footprint = geometry.Polygon(points).buffer(0)
            if not footprint.is_empty:
                footprints.append(footprint)

    return unary_union(footprints) if footprints else None


def get_loop_normals(obj):
    # the normals of the faces corners (the custom normals imported from the glTF files), in object space
    mesh = obj.data
    if hasattr(mesh, "calc_normals_split"):
        mesh.calc_normals_split()
    return [loop.normal.copy() for loop in mesh.loops]


def set_loop_normals(obj, normals, vertex_normals=None):
    # set the normals of the faces corners, those of the vertices in vertex_normals ({vertex index: (normal, weight)}) blended to the given normal
    mesh = obj.data
    if vertex_normals:
        normals = list(normals)
        for i, loop in enumerate(mesh.loops):
            if loop.vertex_index in vertex_normals:
                normal, weight = vertex_normals[loop.vertex_index]
                normals[i] = (normals[i] * (1.0 - weight) + normal * weight).normalized()
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
    mesh.normals_split_custom_set(normals)
    mesh.update()


def get_mesh_objects(excluded_names=("Areas", "Ways")):
    return [obj for obj in bpy.context.scene.objects if obj.type == MESH_OBJECT_TYPE and obj.name not in excluded_names and BOUNDING_BOX_OSM_KEY not in obj.name]


def remove_overlapping_octant_faces(tolerance=0.25):
    # the Google Earth tiles are octree nodes, whose children 0-3 are the lower half of the node, and 4-7 the upper half (same area).
    # Where the ground is near the split, both halves contain it: the faces of the upper part lying on the lower part (their center and
    # all their vertices closer than tolerance) are removed. The faces only partly covered are kept (no holes)
    from mathutils.bvhtree import BVHTree

    parts = []
    for obj in get_mesh_objects():
        name = obj.name.split("_")[0]
        if not name.isdigit() or not len(obj.data.vertices):
            continue
        matrix = obj.matrix_world
        coords = [matrix @ v.co for v in obj.data.vertices]
        xs, ys = [c.x for c in coords], [c.y for c in coords]
        parts.append((obj, name, coords, (min(xs), min(ys), max(xs), max(ys))))

    def is_upper_copy(upper, lower):
        if len(upper) != len(lower):
            return False
        for a, b in zip(upper, lower):
            if a != b:
                return int(a) == int(b) + 4
        return False

    def overlap(b1, b2):
        return b1[0] <= b2[2] and b2[0] <= b1[2] and b1[1] <= b2[3] and b2[1] <= b1[3]

    trees = {}
    nb_removed = 0
    for obj, name, coords, bbox in parts:
        lowers = [lower for lower in parts if lower[0] is not obj and is_upper_copy(name, lower[1]) and overlap(bbox, lower[3])]
        if not lowers:
            continue
        for lower in lowers:
            if lower[1] not in trees:
                trees[lower[1]] = BVHTree.FromPolygons([tuple(c) for c in lower[2]], [tuple(p.vertices) for p in lower[0].data.polygons])
        bvhs = [trees[lower[1]] for lower in lowers]

        def covered(point):
            for bvh in bvhs:
                hit = bvh.find_nearest(point, tolerance)
                if hit[0] is not None:
                    return True
            return False

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        matrix = obj.matrix_world
        faces = []
        for face in bm.faces:
            points = [matrix @ face.calc_center_median()] + [coords[v.index] for v in face.verts]
            if all(covered(p) for p in points):
                faces.append(face)
        if faces:
            bmesh.ops.delete(bm, geom=faces, context="FACES")
            bm.to_mesh(obj.data)
            obj.data.update()
            nb_removed += len(faces)
        bm.free()

    return nb_removed


def smooth_in_mask(radius=4.0, ramp_distance=2.0, mask_name="Areas"):
    # smooth the heights of the vertices inside the (aligned) mask: the mean of the local medians within radius (the spikes, then
    # the facets are removed), progressively from the border of the mask over ramp_distance, so that it joins its surroundings
    from shapely.prepared import prep

    footprint = get_mask_footprint(mask_name)
    if footprint is None:
        return None

    area = prep(footprint)
    minx, miny, maxx, maxy = footprint.bounds
    # the border of the mask, without its borders clipped by the tile
    border = footprint.boundary.difference(geometry.box(minx, miny, maxx, maxy).boundary.buffer(0.5))

    objects_data = []
    for obj in get_mesh_objects((mask_name, "Ways")):
        coords = np.array([(obj.matrix_world @ v.co)[:] for v in obj.data.vertices]) if len(obj.data.vertices) else np.zeros((0, 3))
        inside = np.array([area.contains(geometry.Point(x, y)) for x, y in coords[:, :2]], dtype=bool)
        if inside.any():
            objects_data.append((obj, coords, np.where(inside)[0]))

    if not objects_data:
        return None

    points = np.concatenate([coords[indexes] for _, coords, indexes in objects_data])
    tree = cKDTree(points[:, :2])
    neighbours = tree.query_ball_point(points[:, :2], r=radius)
    medians = np.array([np.median(points[n, 2]) for n in neighbours])
    smoothed = np.array([np.mean(medians[n]) for n in neighbours])

    nb_smoothed = 0
    offset = 0
    for obj, coords, indexes in objects_data:
        # the normals are kept (they turn with the faces when the vertices are moved), and set up on the smoothed surface
        normals = get_loop_normals(obj)
        inverted_matrix = obj.matrix_world.inverted()
        up = (inverted_matrix.to_3x3() @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
        vertex_normals = {}
        for j, i in enumerate(indexes):
            x, y, z = coords[i]
            weight = 1.0
            if ramp_distance > 0.0 and not border.is_empty:
                weight = min(1.0, border.distance(geometry.Point(x, y)) / ramp_distance)
            obj.data.vertices[int(i)].co = inverted_matrix @ mathutils.Vector((x, y, z + weight * (smoothed[offset + j] - z)))
            vertex_normals[int(i)] = (up, weight)
        set_loop_normals(obj, normals, vertex_normals)
        offset += len(indexes)
        nb_smoothed += len(indexes)

    return nb_smoothed


def push_down_water_in_mask(depth=1.5, shore_distance=6.0, ramp_distance=3.0, mask_name="Areas", positioning_name="Ways"):
    # push the vertices of the tile inside the (aligned) water mask under the water level, instead of cutting them:
    # the faces crossing the shore slope down into the water, without holes in the 3d data.
    # The water level of the tile: its water surface (75th percentile), at least its waterline (5th percentile of the ground
    # within shore_distance of the water), at most the median ground of the shore, as the water level of the height data.
    # The level of the height data is calculated for whole water bodies and can be lower (large rivers): the vertices are pushed
    # under the lower quarter of the water surface too, and progressively over ramp_distance from the shore
    from shapely.ops import unary_union
    from shapely.prepared import prep

    footprint = get_mask_footprint(mask_name)
    if footprint is None:
        return None

    water_area = prep(footprint)
    shore_area = prep(footprint.buffer(shore_distance))

    objects_data = []
    for obj in bpy.context.scene.objects:
        if obj.type != MESH_OBJECT_TYPE or obj.name in (mask_name, positioning_name) or BOUNDING_BOX_OSM_KEY in obj.name:
            continue
        coords = np.array([(obj.matrix_world @ v.co)[:] for v in obj.data.vertices]) if len(obj.data.vertices) else np.zeros((0, 3))
        in_water = np.array([water_area.contains(geometry.Point(x, y)) for x, y in coords[:, :2]], dtype=bool)
        on_shore = np.array([(not w) and shore_area.contains(geometry.Point(x, y)) for (x, y), w in zip(coords[:, :2], in_water)], dtype=bool)
        objects_data.append((obj, coords, in_water, on_shore))

    water_heights = np.concatenate([coords[in_water, 2] for _, coords, in_water, _ in objects_data]) if objects_data else np.zeros(0)
    shore_heights = np.concatenate([coords[on_shore, 2] for _, coords, _, on_shore in objects_data]) if objects_data else np.zeros(0)

    if len(water_heights) >= 20 and len(shore_heights) >= 20:
        level = min(max(np.percentile(water_heights, 75), np.percentile(shore_heights, 5)), np.median(shore_heights))
    elif len(water_heights):
        level = np.median(water_heights)
    elif len(shore_heights):
        level = np.percentile(shore_heights, 5)
    else:
        return None

    if len(water_heights):
        level = min(level, np.percentile(water_heights, 25))
    target = float(level) - depth

    # the shore: the outline of the mask, without its borders clipped by the tile
    minx, miny, maxx, maxy = footprint.bounds
    shore = footprint.boundary.difference(geometry.box(minx, miny, maxx, maxy).boundary.buffer(0.5))
    nb_pushed = 0
    for obj, coords, in_water, _ in objects_data:
        indexes = np.where(in_water & (coords[:, 2] > target))[0]
        if not len(indexes):
            continue
        # the normals are kept (they turn with the faces when the vertices are moved)
        normals = get_loop_normals(obj)
        inverted_matrix = obj.matrix_world.inverted()
        for i in indexes:
            weight = 1.0
            if ramp_distance > 0.0 and not shore.is_empty:
                weight = min(1.0, shore.distance(geometry.Point(coords[i, 0], coords[i, 1])) / ramp_distance)
            z = coords[i, 2] - weight * (coords[i, 2] - target)
            obj.data.vertices[int(i)].co = inverted_matrix @ mathutils.Vector((coords[i, 0], coords[i, 1], z))
        set_loop_normals(obj, normals)
        nb_pushed += len(indexes)

    return float(level), nb_pushed


def process_3d_data(model_file_path=None, intersect=False, no_bounding_box=False, keep_mask=False):
    if model_file_path is not None:
        import_model_files([model_file_path], clean=False)

    objects = bpy.context.scene.objects
    bboxes = []

    mask = bpy.context.scene.objects.get("Areas")
    grid = bpy.context.scene.objects.get("grid")
    height_grid = bpy.context.scene.objects.get("height_grid")

    new_collection = bpy.data.collections.new(name="inclusion_points")
    assert (new_collection is not bpy.context.scene.collection)
    bpy.context.scene.collection.children.link(new_collection)

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    updated_objects = []

    if mask:
        for obj in objects:
            if obj == mask or obj == grid or obj == height_grid or BOUNDING_BOX_OSM_KEY in obj.name:
                continue

            bboxes.append(create_bounding_box(obj, "bbox_"))

            # only cleanup objects contained in the mask, or touched by the mask
            if object_touches_mask(obj, mask) or intersect:
                bpy.context.view_layer.objects.active = obj
                add_new_obj_material(obj, OSM_MATERIAL_NAME)

                if not add_boolean_modifier(obj, mask, BOOLEAN_MODIFIER_OPERATION.INTERSECT if intersect else BOOLEAN_MODIFIER_OPERATION.DIFFERENCE):
                    continue

                for modifier in obj.modifiers:
                    bpy.ops.object.modifier_apply(modifier=modifier.name)

                updated_objects.append(obj)

    for obj in updated_objects:
        if obj in bboxes or obj == mask or obj == grid or obj == height_grid or BOUNDING_BOX_OSM_KEY in obj.name:
            continue

        if obj.type != MESH_OBJECT_TYPE:
            continue

        # flat faces to prevent wrong cleaning on less detailed object lods
        if retrieve_tile_object_lod(obj) <= LESS_DETAILED_LODS_LIMIT:
            flat_cutted_faces(obj)

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    for bbox in bboxes:
        bbox.select_set(True)
        bpy.context.view_layer.objects.active = bbox

    bpy.ops.object.join()
    bbox = bpy.context.active_object
    final_bbox = create_bounding_box(bbox, "final_")
    add_new_obj_material(final_bbox, OSM_MATERIAL_NAME)

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    bbox.select_set(True)
    if not keep_mask:
        mask.select_set(True)
    if no_bounding_box:
        final_bbox.select_set(True)
    bpy.ops.object.delete()
    bpy.ops.object.select_all(action=SELECT_ACTION)

    # cleanup the cutted faces
    cleanup_cutted_faces(updated_objects)

    clean_scene(objects_to_keep=bpy.context.scene.objects)
    bpy.ops.object.select_all(action=SELECT_ACTION)

    # Fix 3d normals
    for obj in updated_objects:
        if BOUNDING_BOX_OSM_KEY not in obj.name and obj.type == MESH_OBJECT_TYPE:
            bpy.context.view_layer.objects.active = obj

            if not add_weighted_normal_modifier(obj):
                continue

            for modifier in obj.modifiers:
                bpy.ops.object.modifier_apply(modifier=modifier.name)

    bpy.ops.object.select_all(action=SELECT_ACTION)


def generate_model_height_data(model_file_path, lat, lon, altitude, height_adjustment, positioning_file_path=str(), water_mask_file_path=str(), ground_mask_file_path=str(), rocks_mask_file_path=str(), building_mask_file_path=str(), high_precision=False, ground_filter_size=0.0, outer_edges=str(), water_areas_file_path=str(), waterline_file_path=str(), debug=False):
    if not bpy.context.scene:
        return False

    tile = get_tile_for_ray_cast(model_file_path)
    coords, width, grid, grid_dimension, height_grid_coords, height_grid = prepare_ray_cast(tile)

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    # ensure to select the tile
    tile.select_set(False)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    hmatrix = calculate_height_map_from_coords_from_bottom(tile, grid_dimension, coords, depsgraph, lat, lon, altitude, height_adjustment)

    if high_precision:
        hmatrix = calculate_height_map_from_coords_from_top(tile, coords, depsgraph, lat, lon, altitude, hmatrix)

    # fix wrong height data for buildings
    if os.path.exists(positioning_file_path) and os.path.exists(building_mask_file_path):
        align_model_with_mask(model_file_path, positioning_file_path, building_mask_file_path, objects_to_keep=[grid, height_grid])
        process_3d_data(model_file_path=model_file_path, intersect=True, no_bounding_box=True)
        tile = get_tile_for_ray_cast(model_file_path, imported=False, objects_to_keep=[grid, height_grid])
        hmatrix = fix_height_data_on_buildings(tile, depsgraph, lat, lon, altitude, hmatrix)

    # fix wrong height data for ground tiles
    if os.path.exists(positioning_file_path) and os.path.exists(ground_mask_file_path):
        align_model_with_mask(model_file_path, positioning_file_path, ground_mask_file_path, objects_to_keep=[grid, height_grid])
        process_3d_data(model_file_path=model_file_path, intersect=True, no_bounding_box=True)
        tile = get_tile_for_ray_cast(model_file_path, imported=False, objects_to_keep=[grid, height_grid])
        hmatrix = adjust_height_data_on_ground_exclusion(tile, depsgraph, lat, lon, altitude, hmatrix)

    # fix wrong height data for rock parts of the tiles
    if os.path.exists(positioning_file_path) and os.path.exists(rocks_mask_file_path):
        align_model_with_mask(model_file_path, positioning_file_path, rocks_mask_file_path, objects_to_keep=[grid, height_grid])
        process_3d_data(model_file_path=model_file_path, intersect=False, no_bounding_box=True)
        tile = get_tile_for_ray_cast(model_file_path, imported=False, objects_to_keep=[grid, height_grid])
        hmatrix = adjust_height_data_on_rocks_exclusion(tile, depsgraph, lat, lon, altitude, hmatrix)

    # fix wrong height data for bridges on water
    if os.path.exists(positioning_file_path) and os.path.exists(water_mask_file_path):
        align_model_with_mask(model_file_path, positioning_file_path, water_mask_file_path, objects_to_keep=[grid, height_grid])
        process_3d_data(model_file_path=model_file_path, intersect=True, no_bounding_box=True)
        tile = get_tile_for_ray_cast(model_file_path, imported=False, objects_to_keep=[grid, height_grid])
        hmatrix = fix_bridge_height_data_on_water(tile, depsgraph, lat, lon, altitude, hmatrix)

    # the water keeps its height data, the ground filter would lower it, and the shores with it
    water_keys = set()
    if os.path.exists(positioning_file_path) and os.path.exists(water_areas_file_path):
        water_keys, shore_keys, to_lon_lat = find_height_data_on_water(hmatrix, positioning_file_path, water_areas_file_path, WATERLINE_SAMPLE_DISTANCE)

        # samples of the tiles surface on the water and its shore, used to find the level of the water bodies of the whole project
        if waterline_file_path and water_keys:
            calculation_offset = HIGH_PRECISION_HEIGHT_OFFSET if high_precision else height_adjustment
            samples = {name: [to_lon_lat(y, x) + (hmatrix[y][x] - calculation_offset,) for y, x in keys] for name, keys in (("water", water_keys), ("shore", shore_keys))}
            with open(waterline_file_path, "w") as waterline_file:
                json.dump(samples, waterline_file)

    if ground_filter_size > 0.0:
        hmatrix = filter_ground_height_data(hmatrix, ground_filter_size, height_adjustment=height_adjustment, high_precision=high_precision, outer_edges=outer_edges, water_keys=water_keys)

    inverted_hmatrix = defaultdict(dict)

    for y, heights in hmatrix.items():
        for x, height in heights.items():
            inverted_hmatrix[x][y] = height

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    grid.select_set(True)
    bpy.ops.object.delete()
    tile.select_set(True)
    bpy.ops.object.select_all(action=SELECT_ACTION)

    if not debug:
        clean_scene()
    else:
        bpy.ops.object.select_all(action=DESELECT_ACTION)
        tile.select_set(True)
        bpy.ops.object.delete()

        new_collection = bpy.data.collections.new(name="coords")
        assert (new_collection is not bpy.context.scene.collection)
        bpy.context.scene.collection.children.link(new_collection)

        debug_height_data(new_collection, hmatrix, height_grid, height_grid_coords, model_file_path)

        bpy.ops.object.select_all(action=SELECT_ACTION)

    return hmatrix, inverted_hmatrix, width, altitude


def read_osm_polygons(osm_file_path):
    import xml.etree.ElementTree as ET
    from shapely.ops import unary_union

    root = ET.parse(osm_file_path).getroot()
    nodes = {node.get("id"): (float(node.get("lon")), float(node.get("lat"))) for node in root.iter("node")}
    polygons = []

    for way in root.iter("way"):
        points = [nodes[nd.get("ref")] for nd in way.iter("nd") if nd.get("ref") in nodes]
        if len(points) >= 4 and points[0] == points[-1]:
            polygon = geometry.Polygon(points).buffer(0)
            if not polygon.is_empty:
                polygons.append(polygon)

    return unary_union(polygons) if polygons else None


def find_height_data_on_water(hmatrix, positioning_file_path, areas_file_path, shore_distance):
    # height data points (y, x) inside the water areas of a GeoJSON file, and on their shore (closer than shore_distance meters).
    # The tiles are imported with their south west corner (the minimum of the positioning bounding box) at the origin,
    # the north is -Y and the east is -X. Returns the water points, the shore points and a (y, x) -> (lon, lat) function
    import geopandas as gpd
    from shapely import affinity
    from shapely.prepared import prep

    bbox = read_osm_polygons(positioning_file_path)
    areas_gdf = gpd.read_file(areas_file_path)
    if bbox is None or areas_gdf.empty:
        return set(), set(), None

    west, south = bbox.bounds[0], bbox.bounds[1]
    meters_per_lat_degree = 111320.0
    meters_per_lon_degree = meters_per_lat_degree * cos(radians(south))
    to_lon_lat = lambda y, x: (west - x / meters_per_lon_degree, south - y / meters_per_lat_degree)

    # the water areas in the coordinates of the tile, in meters
    areas = affinity.affine_transform(areas_gdf.to_crs("EPSG:4326").unary_union, [-meters_per_lon_degree, 0.0, 0.0, -meters_per_lat_degree, meters_per_lon_degree * west, meters_per_lat_degree * south])
    prepared_areas = prep(areas)
    prepared_shores = prep(areas.buffer(shore_distance))
    water_keys, shore_keys = set(), set()

    for y, heights in hmatrix.items():
        for x in heights:
            point = geometry.Point(x, y)
            if prepared_areas.contains(point):
                water_keys.add((y, x))
            elif prepared_shores.contains(point):
                shore_keys.add((y, x))

    return water_keys, shore_keys, to_lon_lat


def filter_ground_height_data(hmatrix, filter_size, height_adjustment=0.0, high_precision=False, outer_edges=str(), water_keys=frozenset()):
    # the rays hit the top of the buildings and trees, as the Google Earth tiles have no ground under them.
    # A morphological opening (minimum, then maximum over the filter window) removes everything narrower than the window,
    # then the result is smoothed and kept under the tile surface, so that the MSFS terrain does not go through the tiles.
    # On the outer edges of the scenery (N, S, E, W letters), the ground is raised up to the tiles ground, to avoid a step
    # between the border of the tiles and the MSFS terrain.
    # The water points (water_keys) keep the height data of the water calculation, and the shores are raised like the outer edges
    ys = sorted(hmatrix.keys())
    xs = sorted({x for heights in hmatrix.values() for x in heights})
    if len(xs) < 3 or len(ys) < 3:
        return hmatrix

    heights = np.full((len(ys), len(xs)), np.nan)
    x_index = {x: i for i, x in enumerate(xs)}
    for j, y in enumerate(ys):
        for x, h in hmatrix[y].items():
            heights[j, x_index[x]] = h

    known = ~np.isnan(heights)
    if not known.any():
        return hmatrix

    water = np.zeros(heights.shape, dtype=bool)
    y_index = {y: j for j, y in enumerate(ys)}
    for y, x in water_keys:
        if y in y_index and x in x_index:
            water[y_index[y], x_index[x]] = True

    cell_size = float(np.median(np.diff(xs)))
    window = max(3, int(round(filter_size / cell_size)) | 1)

    filled = np.where(known & ~water, heights, np.nanmax(heights))
    # the rays cast from the bottom on the outer ring of the grid can hit the skirts of the tiles, several meters under the ground
    filled[0, :], filled[-1, :] = filled[1, :], filled[-2, :]
    filled[:, 0], filled[:, -1] = filled[:, 1], filled[:, -2]
    surface = ndimage.grey_opening(filled, size=(window, window), mode="nearest")
    surface = ndimage.gaussian_filter(surface, sigma=1.0, mode="nearest")
    surface = np.minimum(surface, filled)

    # the height data calculated from the bottom includes the height adjustment, the one calculated from the top is 1 meter above the tiles
    tiles_ground = surface - (HIGH_PRECISION_HEIGHT_OFFSET if high_precision else height_adjustment)
    ground = tiles_ground + height_adjustment - GROUND_FILTER_MARGIN

    # distance (in meters) to the outer edges of the scenery and to the water, where the ground is raised up to the tiles ground
    blend_distances = []

    edges = {edge.strip().upper() for edge in outer_edges.split(",") if edge.strip()}
    if edges:
        # the tiles are imported with their south west corner at the origin: the north is -Y and the east is -X
        grid_y = np.array(ys)[:, None] * np.ones((1, len(xs)))
        grid_x = np.ones((len(ys), 1)) * np.array(xs)[None, :]
        distances = {"N": grid_y - ys[0], "S": ys[-1] - grid_y, "E": grid_x - xs[0], "W": xs[-1] - grid_x}
        blend_distances.append(np.min([distances[edge] for edge in edges if edge in distances], axis=0))

    if water.any():
        # the MSFS water does not follow the osm water exactly: a lowered shore shows as shallow water
        blend_distances.append(ndimage.distance_transform_edt(~water, sampling=(float(np.median(np.abs(np.diff(ys)))), cell_size)))

    if blend_distances:
        weight = np.clip(1.0 - np.min(blend_distances, axis=0) / HEIGHT_MAP_EDGE_BLEND_DISTANCE, 0.0, 1.0)
        weight = weight * weight * (3.0 - 2.0 * weight)
        edge_ground = tiles_ground - HEIGHT_MAP_EDGE_CLEARANCE
        ground = ground + weight * np.maximum(edge_ground - ground, 0.0)

    ground = np.where(water, heights, ground)

    results = defaultdict(dict)
    for j, y in enumerate(ys):
        for x in hmatrix[y]:
            results[y][x] = float(ground[j, x_index[x]])

    return results


def debug_height_data(new_collection, hmatrix, height_grid, height_grid_coords, model_file_path):
    n = 0

    bpy.app.debug = True
    not_updated_coords = height_grid_coords.copy()

    # debug height data
    j = 0
    for y, heights in sorted(hmatrix.items()):
        if j % 2 == 0:
            i = 0

            for x, h in sorted(heights.items()):
                if i % 2 == 0:
                    # debug display of the cloud of points
                    p = point_cloud("p" + str(n), [(x, y, h)])
                    new_collection.objects.link(p)
                    n = n + 1
                i = i + 1

        j = j + 1

    # debug height data with a grid
    for y, heights in sorted(hmatrix.items()):
        for x, h in heights.items():
            for p in sorted(height_grid_coords):
                if round_decimals_down(p[0], 1) == x and round_decimals_down(p[1], 1) == y:
                    for nup in not_updated_coords:
                        if round_decimals_down(p[0], 1) == round_decimals_down(nup[0], 1) and round_decimals_down(p[1], 1) == round_decimals_down(nup[1], 1):
                            not_updated_coords.remove(nup)

                    p[2] = h

    for p in not_updated_coords:
        p[0] = 0
        p[1] = 0
        p[2] = 0

    delete_origin_points(height_grid)
    display_final_height_grid(height_grid)

    debug_objects = [obj for obj in new_collection.objects]
    debug_objects.append(height_grid)

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    import_model_files([model_file_path], clean=False, objects_to_keep=debug_objects)
    objs = bpy.context.selected_objects
    bpy.ops.object.select_all(action=DESELECT_ACTION)

    for obj in objs:
        if BOUNDING_BOX_OSM_KEY in obj.name:
            obj.select_set(True)
            bpy.ops.object.delete()

    bpy.ops.object.select_all(action=SELECT_ACTION)

    for obj in debug_objects:
        obj.select_set(False)

    bpy.ops.object.join()
    objs = bpy.context.selected_objects

    height_grid.select_set(True)
    bpy.context.view_layer.objects.active = height_grid

    bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_4', align_axis={'X', 'Y'})
    bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_4', align_axis={'Z'})

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    for obj in new_collection.objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    bpy.ops.object.join()

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    for obj in new_collection.objects:
        obj.hide_set(True)

    for obj in objs:
        obj.location[2] = obj.location[2] - 100.0
        apply_transform(obj, use_location=True)


def display_final_height_grid(height_grid):
    bpy.data.materials.new(name=HEIGHT_GRID_MATERIAL_NAME)
    add_new_obj_material(height_grid, HEIGHT_GRID_MATERIAL_NAME)
    mat = height_grid.active_material
    mat.use_nodes = False
    mat.diffuse_color = (1.0, 0.5, 0.0, 0.5)
    mat.metallic = 0.75
    mat.specular_intensity = 0.75
    mat.roughness = 0.2
    mat.use_backface_culling = True
    mat.blend_method = "BLEND"
    mat.show_transparent_back = True
    height_grid.show_transparent = True
    grid_collection = bpy.data.collections[GRIDS_COLLECTION_NAME]

    wireframe_height_grid = copy_objects(grid_collection, grid_collection, False)
    remove_obj_faces(wireframe_height_grid)

    wireframe_height_grid.location[2] = wireframe_height_grid.location[2] + 0.5
    apply_transform(wireframe_height_grid, use_location=True)

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    for obj in grid_collection.objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = height_grid

    bpy.ops.object.join()


def get_tile_for_ray_cast(model_file_path, imported=True, objects_to_keep=[]):
    tile = None

    if imported:
        import_model_files([model_file_path], objects_to_keep=objects_to_keep)
    bpy.ops.object.select_all(action=SELECT_ACTION)
    keep_objects(objects_to_keep)
    objs = bpy.context.selected_objects
    bpy.ops.object.select_all(action=DESELECT_ACTION)
    mesh = None

    for obj in objs:
        if obj.type != MESH_OBJECT_TYPE:
            obj.select_set(True)
            bpy.ops.object.delete()
        if BOUNDING_BOX_OSM_KEY in obj.name:
            obj.select_set(True)
            bpy.ops.object.delete()
        else:
            mesh = obj

    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.select_all(action=SELECT_ACTION)
    keep_objects(objects_to_keep)
    bpy.ops.object.join()

    objs = bpy.context.selected_objects
    for obj in objs:
        tile = obj

    return tile


def prepare_ray_cast(obj, grid_factor=GRID_FACTOR):
    grid_dimensions = []
    width = 0.0

    bpy.ops.object.select_all(action=SELECT_ACTION)
    bpy.ops.object.join()
    objs = bpy.context.selected_objects
    bpy.ops.object.select_all(action=DESELECT_ACTION)

    for obj in objs:
        if obj.type != MESH_OBJECT_TYPE:
            obj.select_set(True)
            bpy.ops.object.delete()
        else:
            width = obj.dimensions.x
            grid_dimensions = obj.dimensions

    # create the grid
    new_collection = bpy.data.collections.new(name=GRIDS_COLLECTION_NAME)
    assert (new_collection is not bpy.context.scene.collection)
    bpy.context.scene.collection.children.link(new_collection)

    grid_dimension, grid = create_and_align_grid(obj, "grid", new_collection, grid_factor, grid_dimensions)
    coords = [v.co for v in grid.data.vertices]

    height_grid_dimension, height_grid = create_and_align_grid(obj, "height_grid", new_collection, grid_factor, grid_dimensions, keep_faces=True)
    heigth_grid_coords = [v.co for v in height_grid.data.vertices]

    return coords, width, grid, grid_dimension, heigth_grid_coords, height_grid


def extract_splitted_tile(model_file_path, node, texture_folder):
    if not bpy.context.scene: return False

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    objs = [obj for obj in bpy.context.scene.objects if obj.name in node]
    for obj in objs:
        obj.select_set(True)

    export_to_optimized_gltf_files(model_file_path, texture_folder, use_selection=True, export_extras=False)


def copy_objects(from_col, to_col, linked):
    for o in from_col.objects:
        dupe = o.copy()
        if not linked and o.data:
            dupe.data = dupe.data.copy()
        to_col.objects.link(dupe)

    return dupe


def get_geoid_height(lat, lon):
    interpolator = pygeodesy.GeoidKarney(os.path.join(GEOIDS_DATASET_FOLDER, EGM2008_5_DATASET))
    single_position = LatLon(lat, lon)
    h = interpolator(single_position)
    return h


def point_cloud(ob_name, coords, edges=[], faces=[]):
    """Create point cloud object based on given coordinates and name.

    Keyword arguments:
    ob_name -- new object name
    coords -- float triplets eg: [(-1.0, 1.0, 0.0), (-1.0, -1.0, 0.0)]
    """

    # Create new mesh and a new object
    me = bpy.data.meshes.new(ob_name + "Mesh")
    ob = bpy.data.objects.new(ob_name, me)

    # Make a mesh from a list of vertices/edges/faces
    me.from_pydata(coords, edges, faces)

    # Display name and update the mesh
    ob.show_name = True
    me.update()
    return ob


def apply_transform(ob, use_location=False, use_rotation=False, use_scale=False):
    mb = ob.matrix_basis
    I = mathutils.Matrix()
    loc, rot, scale = mb.decompose()

    # rotation
    T = mathutils.Matrix.Translation(loc)
    R = mb.to_3x3().normalized().to_4x4()
    S = mathutils.Matrix.Diagonal(scale).to_4x4()

    transform = [I, I, I]
    basis = [T, R, S]

    def swap(i):
        transform[i], basis[i] = basis[i], transform[i]

    if use_location:
        swap(0)
    if use_rotation:
        swap(1)
    if use_scale:
        swap(2)

    M = transform[0] @ transform[1] @ transform[2]
    if hasattr(ob.data, "transform"):
        ob.data.transform(M)
    for c in ob.children:
        c.matrix_local = M @ c.matrix_local

    ob.matrix_basis = basis[0] @ basis[1] @ basis[2]


def calculate_height_map_from_coords_from_bottom(tile, grid_dimension, coords, depsgraph, lat, lon, altitude, height_adjustment):
    results = defaultdict(dict)
    geoid_height = get_geoid_height(lat, lon)
    new_coords = []

    # downsample the grid for bottom ray casting
    coords = [co for i, co in enumerate(coords)]

    for co in coords:
        p = co
        ray_direction = [0, 0, 1]
        result = multi_ray_cast(tile, depsgraph, p, p[0], p[1], ray_direction, ray_bias=(GRID_FACTOR - 1))
        if result[0]:
            new_coords.append(mathutils.Vector((p[0], p[1], result[1][2])))
        else:
            new_coords.append(mathutils.Vector((p[0], p[1], np.nan)))

    if new_coords:
        points = np.array([[co[0], co[1]] for co in new_coords])
        values = np.array([co[2] for co in new_coords])

        # Use griddata to interpolate missing values
        interpolated = griddata(points[~np.isnan(values)], values[~np.isnan(values)], points, method='nearest')

        for i, co in enumerate(new_coords):
            new_coords[i] = (co[0], co[1], interpolated[i])

        points = np.array([[co[0], co[1]] for co in new_coords])
        values = np.array([co[2] for co in new_coords])

        # Use griddata to interpolate missing values
        interpolated = griddata(points[~np.isnan(values)], values[~np.isnan(values)], points, method='nearest')

        for i, co in enumerate(new_coords):
            new_coords[i] = (co[0], co[1], interpolated[i])

    if new_coords:
        new_coords = [co for i, co in enumerate(new_coords)]

        for i, p in enumerate(new_coords):
            p1 = p
            x = round_decimals_down(p1[0], 1)
            y = round_decimals_down(p1[1], 1)
            h = p1[2]

            if len(results[y]) <= grid_dimension:
                h = h + altitude + geoid_height
                results[y][x] = h + height_adjustment

    return results


def calculate_height_map_from_coords_from_top(tile, coords, depsgraph, lat, lon, altitude, hmatrix_base):
    results = hmatrix_base.copy()
    geoid_height = get_geoid_height(lat, lon)
    new_coords = []

    for co in coords:
        p = mathutils.Vector((co[0], co[1], 3000))
        ray_direction_inverted = [0, 0, -1]
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction_inverted, distance=6000)
        if result[0]:
            new_coords.append(result[1])

    if new_coords:
        new_coords = [co for i, co in enumerate(new_coords)]

        for i, co in enumerate(new_coords):
            p1 = co
            x = round_decimals_down(p1[0], 1)
            y = round_decimals_down(p1[1], 1)
            h = p1[2]

            h = h + altitude + geoid_height
            # h = h if h >= geoid_height else geoid_height

            if hmatrix_base is not None:
                if y in hmatrix_base:
                    if x in hmatrix_base[y]:
                        base_h = hmatrix_base[y][x]
                        h = h + 1.0 if h >= base_h else base_h
                        results[y][x] = h
            else:
                h = h + altitude + geoid_height
                results[y][x] = h

    return results


def fix_bridge_height_data_on_water(tile, depsgraph, lat, lon, altitude, hmatrix_base):
    return adjust_height_data_on_exclusion_area(tile, depsgraph, lat, lon, altitude, EXCLUSION_TYPE.WATER, hmatrix_base)


def fix_height_data_on_buildings(tile, depsgraph, lat, lon, altitude, hmatrix_base):
    return adjust_height_data_on_exclusion_area(tile, depsgraph, lat, lon, altitude, EXCLUSION_TYPE.BUILDING, hmatrix_base)


def adjust_height_data_on_ground_exclusion(tile, depsgraph, lat, lon, altitude, hmatrix_base):
    return adjust_height_data_on_exclusion_area(tile, depsgraph, lat, lon, altitude, EXCLUSION_TYPE.GROUND, hmatrix_base)


def adjust_height_data_on_rocks_exclusion(tile, depsgraph, lat, lon, altitude, hmatrix_base):
    return adjust_height_data_on_exclusion_area(tile, depsgraph, lat, lon, altitude, EXCLUSION_TYPE.ROCKS, hmatrix_base)


def adjust_height_data_on_exclusion_area(tile, depsgraph, lat, lon, altitude, exclusion_type, hmatrix_base):
    results = hmatrix_base.copy()
    geoid_height = get_geoid_height(lat, lon)
    new_coords = []

    if results is not None:
        for y in results:
            for x in results[y]:
                p1 = mathutils.Vector((x, y, 0))
                p2 = mathutils.Vector((x, y, 3000))

                if exclusion_type == EXCLUSION_TYPE.WATER or exclusion_type == EXCLUSION_TYPE.BUILDING:
                    # from bottom
                    ray_direction = (0, 0, 1)
                    result = multi_ray_cast(tile, depsgraph, p1, x, y, ray_direction, ray_bias=(GRID_FACTOR - 1))
                else:
                    # from top
                    ray_direction = (0, 0, -1)
                    result = multi_ray_cast(tile, depsgraph, p2, x, y, ray_direction, ray_bias=(GRID_FACTOR - 1))

                if result[0]:
                    new_coords.append(mathutils.Vector((x, y, result[1].z)))

    if new_coords:
        if exclusion_type == EXCLUSION_TYPE.WATER:
            # fix noise in the height map data
            tree = cKDTree(new_coords, leafsize=60)
            new_coords = spatial_median_kdtree(tree, np.array(new_coords), 100)
        if exclusion_type == EXCLUSION_TYPE.BUILDING:
            tree = cKDTree(new_coords, leafsize=60)
            new_coords = spatial_median_kdtree(tree, np.array(new_coords), 60)
        elif exclusion_type == EXCLUSION_TYPE.GROUND:
            new_coords = spatial_median(np.array(new_coords), 20)

    if hmatrix_base is not None:
        for i, co in enumerate(new_coords):
            p1 = co
            x = round(p1[0], 1)
            y = round(p1[1], 1)
            h = p1[2]
            h = h + altitude + geoid_height
            if exclusion_type == EXCLUSION_TYPE.ROCKS:
                h = h - 5.0
            elif exclusion_type == EXCLUSION_TYPE.BUILDING:
                h = h - 2.0
            elif exclusion_type != EXCLUSION_TYPE.BUILDING:
                h = h + 1.0

            if y in hmatrix_base:
                if x in hmatrix_base[y]:
                    results[y][x] = h

    return results


# based on Adam Steer's code: https://stackoverflow.com/questions/34972383/improving-a-method-for-a-spatially-aware-median-filter-for-point-clouds-in-pytho
# not really fast, but it an accurate method, and it is fast enough for the number of points treated here
def spatial_median(pointcloud, radius):
    new_p = []

    for i, point in enumerate(pointcloud):
        # pick a point and make it a shapely Point
        point = geometry.Point(pointcloud[i, :])

        # select a patch around the point and make it a shapely
        # MultiPoint
        patch = geometry.MultiPoint(list(pointcloud[
                     (pointcloud[:, 0] > point.x - radius + 0.5) &
                     (pointcloud[:, 0] < point.x + radius + 0.5) &
                     (pointcloud[:, 1] > point.y - radius + 0.5) &
                     (pointcloud[:, 1] < point.y + radius + 0.5)
                     ]))

        # buffer the Point by radius
        pbuff = point.buffer(radius)

        # use the intersection method to find points in our
        # patch that lie inside the Point buffer
        isect = pbuff.intersection(patch)

        points = []

        # initialise another list
        plist = []

        # f or every intersection set,
        # unpack it into a list and collect the median Z value
        if isect.geom_type == 'MultiPoint':
            for p in isect.geoms:
                plist.append(p.z)
            # isolated_print('point has neighbours')

            new_p.append((point.x, point.y, np.median(plist)))
        else:
            # if the intersection set isn't MultiPoint,
            # it is an isolated point, whose median Z value
            # is it's own.
            # isolated_print('isolated point')

            # append it to the big list)
            new_p.append((point.x, point.y, isect.z))

    # return a list of new median filtered Z coordinates
    return new_p


# less accurate, but faster method
def spatial_median_kdtree(tree, pointcloud, radius):
    new_p = []

    results = tree.query_ball_point(pointcloud, r=radius)
    for idx, result in enumerate(results):
        if len(result) > 0:
            if np.median(pointcloud[result, 2]) <= pointcloud[idx, 2]:
                new_p.append((pointcloud[idx, 0], pointcloud[idx, 1], np.median(pointcloud[result, 2])))
            else:
                new_p.append((pointcloud[idx, 0], pointcloud[idx, 1], pointcloud[idx, 2]))

    return new_p


def retrieve_tile_object_lod(obj):
    res = 99

    if OBJECT_NAME_SEP in obj.name:
        res = len(obj.name.split(OBJECT_NAME_SEP, 1)[0])

    return res


def object_touches_mask(obj, mask):
    bounding_box_obj = create_bounding_box(obj, BOUNDING_BOX_OSM_KEY)

    if not add_boolean_modifier(bounding_box_obj, mask, BOOLEAN_MODIFIER_OPERATION.INTERSECT):
        return False

    for modifier in bounding_box_obj.modifiers:
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    intersections = [vertex.co for vertex in bounding_box_obj.data.vertices]
    bounding_box_obj.select_set(True)
    bpy.ops.object.delete()

    return intersections


def add_subsurface_modifier(obj):
    subsurfacy = obj.modifiers.new(name="subsurfacy", type=SUBSURFACE_MODIFIER)

    if not subsurfacy:
        return False

    subsurfacy.subdivision_type = SIMPLE_SUBSURFACE_DIVISION_TYPE
    subsurfacy.levels = 2
    subsurfacy.render_levels = 2
    subsurfacy.use_limit_surface = True

    return True


def add_boolean_modifier(obj, mask, operation):
    booly = obj.modifiers.new(name="booly", type=BOOLEAN_MODIFIER)

    if not booly:
        return False

    booly.object = mask
    booly.operation = operation
    booly.solver = EXACT_BOOLEAN_SOLVER
    booly.use_hole_tolerant = True

    return True


def add_remesh_sharp_modifier(obj, octree_depth, scale=0.9):
    remeshy = obj.modifiers.new(name="remeshy", type=REMESH_MODIFIER)

    if not remeshy:
        return False

    remeshy.mode = "SHARP"
    remeshy.octree_depth = octree_depth
    remeshy.scale = scale

    return True


def add_remesh_voxel_modifier(obj, voxel_size):
    remeshy = obj.modifiers.new(name="remeshy", type=REMESH_MODIFIER)

    if not remeshy:
        return False

    remeshy.mode = VOXEL_REMESH_MODE
    remeshy.voxel_size = voxel_size
    remeshy.use_smooth_shade = True

    return True


def add_weighted_normal_modifier(obj):
    weighty = obj.modifiers.new(name="weighty", type=WEIGHTED_NORMAL_MODIFIER)

    if not weighty:
        return False

    weighty.weight = 100
    weighty.thresh = 5.0
    weighty.keep_sharp = True
    weighty.use_face_influence = True

    return True


def add_decimate_modifier(obj, decimate_type, ratio):
    decimaty = obj.modifiers.new(name="booly", type=DECIMATE_MODIFIER)

    if not decimaty:
        return False

    decimaty.decimate_type = decimate_type
    decimaty.ratio = ratio

    return True


def flat_cutted_faces(obj):
    me = obj.data

    polygons = me.polygons
    for polygon in polygons:
        polygon.use_smooth = False

    me.update()


def cleanup_cutted_faces(updated_objects):
    mat_osm = bpy.data.materials[OSM_MATERIAL_NAME]

    for obj in updated_objects:
        if obj.type == MESH_OBJECT_TYPE:
            me = obj.data

            osm_slots = [id for id, mat in enumerate(me.materials) if mat == mat_osm]

            faces_mat_osm = []
            bm = bmesh.new()
            bm.from_mesh(me)

            for face in bm.faces:
                if face.material_index in osm_slots:
                    faces_mat_osm.append(face)

            # delete faces with mat_osm
            bmesh.ops.delete(bm, geom=faces_mat_osm, context=FACES_DELETE_CONTEXT)
            bm.to_mesh(me)
            me.update()
            bm.free()
            del bm
        else:
            obj.select_set(False)


def find_center(obj):
    x, y, z = [sum([v.co[i] for v in obj.data.vertices]) for i in range(3)]
    count = float(len(obj.data.vertices))
    return obj.matrix_world @ (mathutils.Vector((x, y, z)) / count)


def split_obj(obj):
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    center = find_center(obj)

    bpy.ops.object.duplicate(linked=False)
    right = bpy.context.active_object

    obj.select_set(False)
    right.select_set(True)
    bpy.context.view_layer.objects.active = right

    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bisect(plane_co=center, plane_no=(1, 0, 0), use_fill=True, clear_inner=True)
    bpy.ops.object.editmode_toggle()

    right.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj # set obj as active

    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bisect(plane_co=center, plane_no=(1, 0, 0), use_fill=True, clear_outer=True)
    bpy.ops.object.editmode_toggle()


def face(rows, column, row):
    return column * rows + row, column * rows + row + 1, (column + 1) * rows + row + 1, (column + 1) * rows + row


def create_bounding_box(obj, prefix, spheric=False, cut_base=False, scale_x=1.0, scale_y=1.0, scale_z=1.0):
    scale = obj.scale

    minx = obj.bound_box[0][0] * scale.x
    maxx = obj.bound_box[4][0] * scale.x
    miny = obj.bound_box[0][1] * scale.y
    maxy = obj.bound_box[2][1] * scale.y
    minz = obj.bound_box[0][2] * scale.z
    maxz = obj.bound_box[1][2] * scale.z
    dx = maxx - minx
    dy = maxy - miny
    dz = maxz - minz

    new_name = '{0}{1}'.format(prefix, obj.name)

    loc = mathutils.Vector(((minx + 0.5 * dx), (miny + 0.5 * dy), (minz + 0.5 * dz)))
    loc.rotate(obj.rotation_euler)
    loc = loc + obj.location

    if spheric:
        bpy.ops.mesh.primitive_uv_sphere_add(location=loc, rotation=obj.rotation_euler)
        dx = dx * scale_x
        dy = dy * scale_y
        dz = dz * scale_z
    else:
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=obj.rotation_euler)

    bounding_box_obj = bpy.context.object

    bounding_box_obj.name = new_name
    bounding_box_obj.dimensions = mathutils.Vector((dx, dy, dz))

    if cut_base:
        bpy.ops.object.select_all(action=DESELECT_ACTION)
        bpy.ops.mesh.primitive_plane_add(location=loc, rotation=obj.rotation_euler)
        plane = bpy.context.object
        plane.dimensions = mathutils.Vector((dx, dy, dz))
        plane.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.align(bb_quality=True, align_mode='OPT_1', relative_to='OPT_4', align_axis={'Z'})
        bounding_box_obj.select_set(True)
        bpy.context.view_layer.objects.active = bounding_box_obj
        if add_boolean_modifier(bounding_box_obj, plane, BOOLEAN_MODIFIER_OPERATION.DIFFERENCE):
            for modifier in bounding_box_obj.modifiers:
                bpy.ops.object.modifier_apply(modifier=modifier.name)

        bpy.ops.object.select_all(action=DESELECT_ACTION)
        plane.select_set(True)
        bpy.ops.object.delete()

    return bounding_box_obj


def create_grid(obj, name, grid_dimension):
    bpy.ops.mesh.primitive_plane_add(location=[0.0, 0.0, 0.0], rotation=obj.rotation_euler, scale=obj.scale)

    new_obj = bpy.context.object
    reduction_factor = 0.99

    minx = obj.bound_box[0][0] * reduction_factor
    maxx = obj.bound_box[4][0] * reduction_factor
    miny = obj.bound_box[0][1] * reduction_factor
    maxy = obj.bound_box[2][1] * reduction_factor
    dx = maxx - minx
    dy = maxy - miny

    new_obj.name = name
    new_obj.dimensions = mathutils.Vector((dx, dy, 0))

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    grid = bpy.context.scene.objects.get(name)
    grid.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    me = new_obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, use_grid_fill=True, cuts=int(grid_dimension) - 1)
    bm.to_mesh(me)
    me.update()
    bm.free()

    remove_obj_faces(new_obj)

    bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_4', align_axis={'X', 'Y'})
    apply_transform(grid, use_location=True, use_rotation=True, use_scale=True)
    bpy.ops.object.align(bb_quality=True, align_mode='OPT_1', relative_to='OPT_4', align_axis={'Z'})
    apply_transform(grid, use_location=True, use_rotation=False, use_scale=False)

    return new_obj


def create_and_align_grid(obj, grid_name, grid_collection, grid_factor, grid_dimensions, keep_faces=False):
    reduction_factor = 0.95

    minx = obj.bound_box[0][0] * reduction_factor
    maxx = obj.bound_box[4][0] * reduction_factor
    miny = obj.bound_box[0][1] * reduction_factor
    maxy = obj.bound_box[2][1] * reduction_factor
    dx = maxx - minx
    dy = maxy - miny

    me = bpy.data.meshes.new(grid_name)
    bm = bmesh.new()
    max_grid_dimension = max(grid_dimensions.x, grid_dimensions.y)
    grid_dimension = floor(max_grid_dimension / grid_factor)
    grid_dimension_x = floor(grid_dimensions.x / grid_factor)
    grid_dimension_y = floor(grid_dimensions.y / grid_factor)
    bmesh.ops.create_grid(bm, x_segments=grid_dimension_x, y_segments=grid_dimension_y, size=round(max_grid_dimension / 2))
    bm.to_mesh(me)
    ob = bpy.data.objects.new(grid_name, me)

    if not keep_faces:
        remove_obj_faces(ob)

    grid_collection.objects.link(ob)

    bpy.ops.object.select_all(action=DESELECT_ACTION)

    grid = bpy.context.scene.objects.get(grid_name)

    grid.dimensions = mathutils.Vector((dx, dy, 0))

    grid.select_set(True)

    bpy.ops.object.select_all(action=SELECT_ACTION)

    bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_4', align_axis={'X', 'Y'})
    apply_transform(grid, use_location=True, use_rotation=False, use_scale=True)
    bpy.ops.object.align(bb_quality=True, align_mode='OPT_1', relative_to='OPT_4', align_axis={'Z'})
    apply_transform(grid, use_location=True, use_rotation=False, use_scale=False)

    return grid_dimension, grid


def delete_origin_points(obj):
    bpy.ops.object.select_all(action=DESELECT_ACTION)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj = bpy.context.active_object
    me = obj.data

    bm = bmesh.new()
    bm.from_mesh(me)

    vertices = [v for v in bm.verts if (v.co[0] == 0.0 and v.co[1] == 0.0 and v.co[2] == 0.0)]
    bmesh.ops.delete(bm, geom=vertices, context=VERTICES_DELETE_CONTEXT)

    bm.to_mesh(me)
    me.update()
    bm.free()


def create_vert(grid_dimension, column, row, h):
    """ Create a single vert """

    return column * grid_dimension, row * grid_dimension, h


def create_face(grid_dimension, column, row):
    """ Create a single face """

    return (column * grid_dimension + row,
            (column + 1) * grid_dimension + row,
            (column + 1) * grid_dimension + 1 + row,
            column * grid_dimension + 1 + row)


def round_decimals_down(number: float, decimals: int = 2):
    """
    Returns a value rounded down to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return floor(number)

    factor = 10 ** decimals
    return floor(number * factor) / factor


def remove_obj_faces(obj):
    remove_obj_nodes(obj, FACES_ONLY_DELETE_CONTEXT)


def remove_obj_faces_and_egdes(obj):
    remove_obj_nodes(obj, EDGES_FACES_DELETE_CONTEXT)


def remove_obj_nodes(obj, delete_context):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=bm.verts, context=delete_context)
    bmesh.ops.delete(bm, geom=bm.edges, context=delete_context)
    bmesh.ops.delete(bm, geom=bm.faces, context=delete_context)
    bm.to_mesh(me)
    me.update()
    bm.free()


def create_geocode_bounding_box(lat, lon, alt, landmark_location_file_path, new_lights=False, debug=False):
    data = {"x": [], "y": [], "z": [], "@": []}
    center_coords = 0.0
    height_adjust = 20.0
    scale_x = 1.5
    scale_y = 1.5
    scale_z = 1.5
    margin = 300.0 if new_lights else 100.0
    nb_vertices_treshold = 80
    bpy.ops.object.select_all(action=DESELECT_ACTION)
    mask = bpy.context.scene.objects.get("Areas")
    mask.select_set(True)
    mask.scale.x = scale_x
    mask.scale.y = scale_y
    mask.scale.z = scale_z
    final_points_collection = None

    bpy.ops.object.select_all(action=DESELECT_ACTION)
    import_osm_file(landmark_location_file_path)
    for obj in bpy.context.selected_objects:
        obj.name = "center"
        center = obj

    bpy.ops.object.select_all(action=SELECT_ACTION)
    obs = bpy.context.selected_objects
    bpy.ops.object.select_all(action=DESELECT_ACTION)

    for obj in obs:
        if obj == mask:
            continue

        if obj == center:
            continue

        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        bbox = create_bounding_box(obj, "geocode_", spheric=True, cut_base=True, scale_x=scale_x, scale_y=scale_y, scale_z=scale_z)
        mask.select_set(True)
        bpy.context.view_layer.objects.active = bbox
        bbox.select_set(True)
        bpy.ops.object.align(bb_quality=True, align_mode='OPT_2', relative_to='OPT_4', align_axis={'X', 'Y', 'Z'})
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bbox.select_set(True)
        bpy.context.view_layer.objects.active = bbox

        if add_remesh_sharp_modifier(mask, 7):
            for modifier in bbox.modifiers:
                bpy.ops.object.modifier_apply(modifier=modifier.name)

        if not add_decimate_modifier(bbox, COLLAPSE_DECIMATE_TYPE, 0.175):
            continue

        for modifier in bbox.modifiers:
            bpy.ops.object.modifier_apply(modifier=modifier.name)

        if add_boolean_modifier(bbox, mask, BOOLEAN_MODIFIER_OPERATION.INTERSECT):
            depsgraph = bpy.context.evaluated_depsgraph_get()
            bm = bmesh.new()
            bm.from_object(bbox, depsgraph)
            bm.verts.ensure_lookup_table()

            if len(bm.verts) > 0:
                for modifier in bbox.modifiers:
                    bpy.ops.object.modifier_apply(modifier=modifier.name)
            else:
                for modifier in bbox.modifiers:
                    bpy.ops.object.modifier_remove(modifier=modifier.name)

        bpy.ops.object.select_all(action=DESELECT_ACTION)
        mask.select_set(True)
        bpy.ops.object.delete()

        depsgraph = bpy.context.evaluated_depsgraph_get()
        bm = bmesh.new()
        bm.from_object(bbox, depsgraph)
        bm.verts.ensure_lookup_table()

        i = 0.99

        remeshed = False

        while len(bm.verts) > nb_vertices_treshold:
            if debug:
                isolated_print("number of vertices: ", len(bm.verts))

            for modifier in bbox.modifiers:
                bpy.ops.object.modifier_remove(modifier=modifier.name)

            # if add_decimate_modifier(bbox, COLLAPSE_DECIMATE_TYPE, 0.35):
            if add_remesh_sharp_modifier(bbox, 4, scale=i):
                remeshed = True

            depsgraph = bpy.context.evaluated_depsgraph_get()
            bm = bmesh.new()
            bm.from_object(bbox, depsgraph)
            bm.verts.ensure_lookup_table()
            i = i - 0.01

        if remeshed:
            for modifier in bbox.modifiers:
                bpy.ops.object.modifier_apply(modifier=modifier.name)

        if not debug:
            bbox.select_set(True)
            bpy.context.view_layer.objects.active = bbox
            remove_obj_faces_and_egdes(bbox)

        bpy.ops.object.select_all(action=DESELECT_ACTION)

        depsgraph = bpy.context.evaluated_depsgraph_get()
        bm = bmesh.new()
        bm.from_object(center, depsgraph)
        bm.verts.ensure_lookup_table()

        for v in bm.verts:
            center_coords = v.co

        bpy.ops.object.select_all(action=DESELECT_ACTION)

        depsgraph = bpy.context.evaluated_depsgraph_get()
        bm = bmesh.new()
        bm.from_object(bbox, depsgraph)
        bm.verts.ensure_lookup_table()

        bpy.ops.object.select_all(action=DESELECT_ACTION)

        if debug:
            isolated_print("number of vertices: ", len(bm.verts))
            final_points_collection = bpy.data.collections.new(name="final points")
            bpy.context.scene.collection.children.link(final_points_collection)

        for i, v in enumerate(bm.verts):
            if debug:
                isolated_print(v.co)

            coords = bbox.matrix_world @ v.co

            vec = coords - center_coords
            radius = vec.length + margin
            npo = (vec.normalized() * radius)

            if debug:
                pc = point_cloud("p" + str(i), [(npo.x + center_coords.x, npo.y + center_coords.y, coords.z)])
                final_points_collection.objects.link(pc)

            v1 = mathutils.Vector((vec.x, vec.y)).normalized()
            axis = mathutils.Vector((1, 0))
            angle = v1.angle_signed(axis) * (180 / np.pi)

            data["x"].append(npo.x)
            data["y"].append(npo.y)
            data["z"].append(coords.z + alt + height_adjust - obj.location.z)
            data["@"].append(angle)

        bm.free()
        gdf = create_latlon_gdf_from_meter_data(data, lat, lon, 0.0)

        return gdf


def multi_ray_cast(tile, depsgraph, source, x, y, ray_direction, ray_bias=0):
    result = tile.evaluated_get(depsgraph).ray_cast(source, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x, y + ray_bias, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x, y - ray_bias, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x + ray_bias, y, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x - ray_bias, y, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x - ray_bias, y + ray_bias, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x + ray_bias, y + ray_bias, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    if not result[0]:
        p = mathutils.Vector((x + ray_bias, y - ray_bias, 0))
        result = tile.evaluated_get(depsgraph).ray_cast(p, ray_direction, distance=6000)

    return result
