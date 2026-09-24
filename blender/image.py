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

SHADER_TEX_IMAGE_NODE_TYPE = "ShaderNodeTexImage"
TEX_IMAGE_NODE_TYPE = "TEX_IMAGE"
BSDF_NODE_TYPE = "BSDF_PRINCIPLED"
BASE_COLOR_INDEX = 0
BLANK_IMAGE_NAME = "blank"
BLANK_COLOR = (0.0, 0.0, 0.0, 1.0)
DUMMY_IMAGE_WIDTH = 256
DUMMY_IMAGE_HEIGHT = 256
PACKED_IMAGE_NAME = "PackedImage"
# pixels around each packed texture, filled with its border pixels, so that mipmaps don't bleed between textures
PACKED_TEXTURE_PADDING = 8
# packed textures are aligned on the 4x4 pixel blocks of the MSFS texture compression
PACKED_TEXTURE_ALIGNMENT = 4
MAX_PACKED_IMAGE_SIZE = 8192
UV_EPSILON = 1e-4

######################################################
# Image management methods
######################################################

import bpy
import numpy as np
from math import ceil, floor, sqrt
from blender.material import get_material_output


def list_image_nodes(node, weight=0):
    if node.type == TEX_IMAGE_NODE_TYPE:
        return [(node, weight)]
    image_nodes = []
    for i, in_socket in enumerate(node.inputs):
        w = weight
        if node.type == BSDF_NODE_TYPE and i == BASE_COLOR_INDEX:
            w += 100
        for l in in_socket.links:
            image_nodes += list_image_nodes(l.from_node, weight=w - 1)

    return image_nodes


def get_image_node(obj):
    material = obj.material_slots[0].material
    material_output = get_material_output(material)
    image_nodes = list_image_nodes(material_output)
    image_nodes.sort(key=lambda x: -x[1])

    if len(image_nodes) <= 0:
        nodes = material.node_tree.nodes
        node_texture = nodes.new(type=SHADER_TEX_IMAGE_NODE_TYPE)
        node_texture.image = bpy.data.images.new(name=BLANK_IMAGE_NAME, width=DUMMY_IMAGE_WIDTH, height=DUMMY_IMAGE_HEIGHT, alpha=True)
        node_texture.image.generated_color = BLANK_COLOR
        node_texture.location = 0, 0
        links = material.node_tree.links
        bsdf = next((node for node in nodes if node.type == BSDF_NODE_TYPE), None)
        if bsdf is not None:
            links.new(node_texture.outputs[0], bsdf.inputs[BASE_COLOR_INDEX])
        print("texture added to ", obj)
        return node_texture

    return image_nodes[0][0]


##################################################################
# fix texture final size for package compilation
##################################################################
def fix_texture_size_for_package_compilation(packed_image):
    # only resize (and resample) the image if its size is not already a multiple of 4
    if packed_image.size[0] % 4 == 0 and packed_image.size[1] % 4 == 0:
        return
    new_img_width = packed_image.size[0] + (4 - packed_image.size[0] % 4) % 4
    new_img_height = packed_image.size[1] + (4 - packed_image.size[1] % 4) % 4
    packed_image.scale(new_img_width, new_img_height)


##################################################################
# pack the textures of the objects into a single image
##################################################################
def pack_textures(objects):
    # Pack the base color textures of the objects into a single image, and remap their uvs to it.
    # Only the part of each texture used by the uvs is kept. Returns the packed image, or None if
    # the textures can't be packed (uvs repeating the texture, or packed image too large)
    textures = {}
    for obj in objects:
        image_node = get_image_node(obj)
        if image_node is None or image_node.image is None or not obj.data.uv_layers:
            return None
        textures.setdefault(image_node.image.name, (image_node.image, []))[1].append(obj)

    rects = []
    for image, texture_objects in textures.values():
        width, height = image.size
        uvs = [get_uvs(obj) for obj in texture_objects]
        used_uvs = [uv for uv in uvs if len(uv)]
        if not width or not height:
            return None
        if not used_uvs:
            continue

        uv_min = np.min([uv.min(axis=0) for uv in used_uvs], axis=0)
        uv_max = np.max([uv.max(axis=0) for uv in used_uvs], axis=0)
        if uv_min.min() < -UV_EPSILON or uv_max.max() > 1 + UV_EPSILON:
            return None

        # part of the texture used by the uvs, with one more texel for the texture filtering
        x0 = max(0, floor(uv_min[0] * width) - 1)
        y0 = max(0, floor(uv_min[1] * height) - 1)
        x1 = min(width, max(ceil(uv_max[0] * width) + 1, x0 + 1))
        y1 = min(height, max(ceil(uv_max[1] * height) + 1, y0 + 1))
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        crop = pixels.reshape(height, width, 4)[y0:y1, x0:x1]

        rect_width = align_size(crop.shape[1] + 2 * PACKED_TEXTURE_PADDING, PACKED_TEXTURE_ALIGNMENT)
        rect_height = align_size(crop.shape[0] + 2 * PACKED_TEXTURE_PADDING, PACKED_TEXTURE_ALIGNMENT)
        rects.append((rect_width, rect_height, crop, image, texture_objects, uvs, x0, y0))

    if not rects:
        return None

    positions, packed_width, packed_height = pack_rectangles([(rect[0], rect[1]) for rect in rects])
    if max(packed_width, packed_height) > MAX_PACKED_IMAGE_SIZE:
        return None

    packed_pixels = np.zeros((packed_height, packed_width, 4), dtype=np.float32)
    for (x, y), (rect_width, rect_height, crop, image, texture_objects, uvs, x0, y0) in zip(positions, rects):
        crop_height, crop_width = crop.shape[:2]
        # fill the padding with the border pixels of the texture
        packed_pixels[y:y + rect_height, x:x + rect_width] = np.pad(crop, ((PACKED_TEXTURE_PADDING, rect_height - crop_height - PACKED_TEXTURE_PADDING), (PACKED_TEXTURE_PADDING, rect_width - crop_width - PACKED_TEXTURE_PADDING), (0, 0)), mode="edge")

        width, height = image.size
        for obj, uv in zip(texture_objects, uvs):
            if not len(uv):
                continue
            new_uv = np.empty(uv.shape, dtype=np.float64)
            new_uv[:, 0] = (x + PACKED_TEXTURE_PADDING - x0 + uv[:, 0] * width) / packed_width
            new_uv[:, 1] = (y + PACKED_TEXTURE_PADDING - y0 + uv[:, 1] * height) / packed_height
            obj.data.uv_layers.active.data.foreach_set("uv", new_uv.astype(np.float32).ravel())

    packed_pixels[:, :, 3] = 1.0
    packed_image = bpy.data.images.new(name=PACKED_IMAGE_NAME, width=packed_width, height=packed_height, alpha=False)
    packed_image.pixels.foreach_set(packed_pixels.ravel())
    packed_image.update()

    return packed_image


def get_uvs(obj):
    uv_data = obj.data.uv_layers.active.data
    uvs = np.empty(len(uv_data) * 2, dtype=np.float32)
    uv_data.foreach_get("uv", uvs)
    return uvs.reshape(-1, 2).astype(np.float64)


def align_size(size, alignment):
    return (size + alignment - 1) // alignment * alignment


def pack_rectangles(sizes):
    # shelf packing of the rectangles (sorted by decreasing height), trying several widths to get the
    # smallest and most square packed image. Returns the rectangle positions and the packed image size
    area = sum(width * height for width, height in sizes)
    min_width = max(width for width, height in sizes)
    start = align_size(max(min_width, int(sqrt(area) * 0.8)), PACKED_TEXTURE_ALIGNMENT)
    end = align_size(max(min_width, int(sqrt(area) * 1.6)), PACKED_TEXTURE_ALIGNMENT)
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))

    best = None
    for packed_width in range(start, end + 1, 4 * PACKED_TEXTURE_ALIGNMENT):
        positions = [None] * len(sizes)
        x = y = shelf_height = used_width = 0
        for i in order:
            width, height = sizes[i]
            if x + width > packed_width:
                y += shelf_height
                x = shelf_height = 0
            positions[i] = (x, y)
            x += width
            used_width = max(used_width, x)
            shelf_height = max(shelf_height, height)
        packed_height = y + shelf_height
        score = (max(used_width, packed_height), used_width * packed_height)
        if best is None or score < best[0]:
            best = (score, positions, used_width, packed_height)

    return best[1], best[2], best[3]
