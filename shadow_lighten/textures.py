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

# The tiles as data for the shadow lightening: the triangles of a LOD with their uvs, normals and texture, the placement of the
# tiles, the ray casting structure (Blender's mathutils, no scene), the texture maps (3D point and normal of each texel) and
# the image helpers. Tile frame (GEDOT placement): glTF +Z = north, -X = east, +Y = up, meters from the south west corner of the
# tile; here (east, north, up).

import json
import math
import os
import re

import numpy as np
from mathutils.bvhtree import BVHTree
from PIL import Image

from utils.octant import get_coords_from_file_name
from utils.placement import wgs84_to_tile

COMPONENTS = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
SIZES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
LUMINANCE = np.array([0.2126, 0.7152, 0.0722])


def read_accessor(gltf, data, index):
    accessor = gltf["accessors"][index]
    view = gltf["bufferViews"][accessor["bufferView"]]
    dtype, n = COMPONENTS[accessor["componentType"]], SIZES[accessor["type"]]
    stride = view.get("byteStride")
    if stride and stride != np.dtype(dtype).itemsize * n:
        raise ValueError("interleaved buffers are not supported")
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    values = np.frombuffer(data, dtype=dtype, count=accessor["count"] * n, offset=offset)
    return values.reshape(accessor["count"], n) if n > 1 else values


def load_triangles(gltf_path):
    # the triangles of a model (T, 3, 3) as (east, north, up), their uvs (T, 3, 2) and vertex normals (T, 3, 3), the image files of
    # the model and the index of each triangle's image (-1: no texture). A LOD can have several textures (the terrain completion
    # of the partial tiles): each texture must be handled with its own triangles only
    with open(gltf_path, encoding="utf-8") as f:
        gltf = json.load(f)
    with open(os.path.join(os.path.dirname(gltf_path), gltf["buffers"][0]["uri"]), "rb") as f:
        data = f.read()
    images = [image["uri"] for image in gltf.get("images", [])]
    positions, uvs, normals, owners = [], [], [], []
    for node in gltf["nodes"]:
        if "mesh" not in node:
            continue
        if any(key in node for key in ("matrix", "rotation", "scale")):
            raise ValueError("transformed nodes are not supported")
        translation = np.array(node.get("translation", [0.0, 0.0, 0.0]))
        for primitive in gltf["meshes"][node["mesh"]]["primitives"]:
            attributes = primitive["attributes"]
            position = read_accessor(gltf, data, attributes["POSITION"]).astype(np.float64) + translation
            indices = read_accessor(gltf, data, primitive["indices"]).astype(np.int64).reshape(-1, 3)
            positions.append(np.column_stack([-position[:, 0], position[:, 2], position[:, 1]])[indices])
            uv = read_accessor(gltf, data, attributes["TEXCOORD_0"]).astype(np.float64) if "TEXCOORD_0" in attributes else np.zeros((len(position), 2))
            uvs.append(uv[indices])
            if "NORMAL" in attributes:
                normal = read_accessor(gltf, data, attributes["NORMAL"]).astype(np.float64)
                normals.append(np.column_stack([-normal[:, 0], normal[:, 2], normal[:, 1]])[indices])
            else:
                face = np.cross(positions[-1][:, 1] - positions[-1][:, 0], positions[-1][:, 2] - positions[-1][:, 0])
                face /= np.maximum(np.linalg.norm(face, axis=1), 1e-12)[:, None]
                normals.append(np.repeat(face[:, None, :], 3, axis=1))
            owner = -1
            try:
                material = gltf["materials"][primitive["material"]]
                owner = gltf["textures"][material["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]
            except (KeyError, IndexError, TypeError):
                pass
            owners.append(np.full(len(indices), owner))
    if not positions:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 2)), np.zeros((0, 3, 3)), images, np.zeros(0, dtype=int)
    return np.concatenate(positions), np.concatenate(uvs), np.concatenate(normals), images, np.concatenate(owners)


def tile_placements(objects_xml_path, model_lib_folder):
    # tile name -> (lat, lon, alt) of its scenery object (the tiles are recognized by the guid of their definition file)
    guid_to_tile = {}
    for name in os.listdir(model_lib_folder):
        if re.fullmatch(r"\d+\.xml", name):
            with open(os.path.join(model_lib_folder, name), encoding="utf-8") as f:
                m = re.search(r'guid="(\{[^}]+\})"', f.read())
            if m:
                guid_to_tile[m.group(1).lower()] = name[:-4]
    with open(objects_xml_path, encoding="utf-8") as f:
        scene = f.read()
    placements = {}
    for m in re.finditer(r'<SceneryObject ([^>]*)>\s*<LibraryObject name="(\{[^}]+\})"', scene):
        attributes = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        tile = guid_to_tile.get(m.group(2).lower())
        if tile:
            placements[tile] = (float(attributes["lat"]), float(attributes["lon"]), float(attributes["alt"]))
    return placements


def neighbours(tile, tiles):
    # the tiles touching the tile (sides and corners)
    n, s, w, e = get_coords_from_file_name(tile)
    eps_lat, eps_lon = (n - s) * 0.01, (e - w) * 0.01
    result = []
    for other in tiles:
        if other == tile:
            continue
        n2, s2, w2, e2 = get_coords_from_file_name(other)
        if s2 <= n + eps_lat and n2 >= s - eps_lat and w2 <= e + eps_lon and e2 >= w - eps_lon:
            result.append(other)
    return result


def load_occluders(model_lib_folder, tile, placements, triangles, lod="LOD02"):
    # the ray casting structure of the tile and its neighbours (their coarse LOD), placed in the tile frame: the shadows cast
    # across the tile edges
    lat, lon, alt = placements[tile]
    occluders = [triangles]
    for other in neighbours(tile, sorted(placements)):
        path = os.path.join(model_lib_folder, "%s_%s.gltf" % (other, lod))
        if os.path.isfile(path):
            tris = load_triangles(path)[0]
            east, north, up = wgs84_to_tile(*placements[other], lat, lon, alt)
            occluders.append(tris + np.array([east, north, up]))
    everything = np.concatenate(occluders)
    return BVHTree.FromPolygons(everything.reshape(-1, 3).tolist(), np.arange(len(everything) * 3).reshape(-1, 3).tolist(), all_triangles=True)


def smooth_normals(triangles, normals, cell):
    # vertex normals averaged over the vertices in the 3 x 3 x 3 cells around each one (a crown of a tree gets one rounded shape)
    points, vectors = triangles.reshape(-1, 3), normals.reshape(-1, 3)
    if not len(points):
        return normals
    coords = np.floor(points / cell).astype(np.int64)
    keys, inverse = np.unique(encode_cells(coords), return_inverse=True)
    sums = np.zeros((len(keys), 3))
    np.add.at(sums, inverse, vectors)
    cell_coords = np.zeros((len(keys), 3), dtype=np.int64)
    cell_coords[inverse] = coords
    total = np.zeros_like(sums)
    for offset in NEIGHBOUR_CELLS:
        neighbour = encode_cells(cell_coords + offset)
        index = np.clip(np.searchsorted(keys, neighbour), 0, len(keys) - 1)
        found = keys[index] == neighbour
        total[found] += sums[index[found]]
    smoothed = total[inverse]
    smoothed /= np.maximum(np.linalg.norm(smoothed, axis=1), 1e-9)[:, None]
    return smoothed.reshape(normals.shape)


def encode_cells(coords):
    return ((coords[:, 0] + 2 ** 20) << 42) + ((coords[:, 1] + 2 ** 20) << 21) + (coords[:, 2] + 2 ** 20)


NEIGHBOUR_CELLS = [np.array([dx, dy, dz]) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]


def reference_cells(points, values, cell):
    # the sums and counts of values per cell of a 3D grid
    keys, inverse = np.unique(encode_cells(np.floor(points / cell).astype(np.int64)), return_inverse=True)
    sums = np.zeros((len(keys), values.shape[1]))
    counts = np.zeros(len(keys))
    np.add.at(sums, inverse, values)
    np.add.at(counts, inverse, 1)
    return {"keys": keys, "sums": sums, "counts": counts, "cell": cell}


def cell_means(cells, points):
    # for each point, the mean of the values in the 3 x 3 x 3 cells around it, and their number
    keys, cell = cells["keys"], cells["cell"]
    sums, counts = np.zeros((len(points), cells["sums"].shape[1])), np.zeros(len(points))
    if not len(keys):
        return sums, counts
    coords = np.floor(points / cell).astype(np.int64)
    for offset in NEIGHBOUR_CELLS:
        neighbour = encode_cells(coords + offset)
        index = np.clip(np.searchsorted(keys, neighbour), 0, len(keys) - 1)
        found = keys[index] == neighbour
        sums[found] += cells["sums"][index[found]]
        counts[found] += cells["counts"][index[found]]
    return sums / np.maximum(counts, 1)[:, None], counts


def rasterize(triangles, uvs, normal_sets, width, height):
    # the 3D point of each texel of a (width, height) texture covered by the triangles (NaN elsewhere), and one interpolated
    # normal map per set of vertex normals
    point_map = np.full((height, width, 3), np.nan, dtype=np.float32)
    normal_maps = [np.zeros((height, width, 3), dtype=np.float32) for _ in normal_sets]
    pix = uvs * np.array([width, height])
    for t in range(len(triangles)):
        a, b, c = pix[t]
        x0, x1 = int(max(math.floor(min(a[0], b[0], c[0])), 0)), int(min(math.ceil(max(a[0], b[0], c[0])), width - 1))
        y0, y1 = int(max(math.floor(min(a[1], b[1], c[1])), 0)), int(min(math.ceil(max(a[1], b[1], c[1])), height - 1))
        if x1 < x0 or y1 < y0:
            continue
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / det
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not inside.any():
            continue
        w = np.column_stack([l1[inside], l2[inside], l3[inside]])
        yy, xx = (ys[inside] - 0.5).astype(int), (xs[inside] - 0.5).astype(int)
        point_map[yy, xx] = w @ triangles[t]
        for normal_map, normals in zip(normal_maps, normal_sets):
            n = w @ normals[t]
            normal_map[yy, xx] = n / np.maximum(np.linalg.norm(n, axis=1), 1e-9)[:, None]
    return point_map, normal_maps


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def lum(linear):
    return linear @ LUMINANCE


def smoothstep(x, low, high):
    t = np.clip((x - low) / (high - low), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def upsample_smooth(small, height, width, valid=None):
    # bilinear upsampling of a (h, w) or (h, w, c) array; with a valid mask, the mean over the valid texels only (NaN where none)
    channels = small[..., None] if small.ndim == 2 else small
    mask = np.ones(channels.shape[:2], dtype=np.float32) if valid is None else valid.astype(np.float32)
    resize = lambda a: np.asarray(Image.fromarray(a.astype(np.float32), mode="F").resize((width, height), Image.BILINEAR), dtype=np.float64)
    weight = resize(mask)
    big = np.stack([resize(np.nan_to_num(channels[..., c]) * mask) for c in range(channels.shape[2])], axis=-1)
    big = big / np.maximum(weight, 1e-6)[..., None]
    if valid is not None:
        big[weight < 0.25] = np.nan
    return big[..., 0] if small.ndim == 2 else big


def box_blur(values, mask, radius):
    # mean over the (2 radius + 1)^2 texels around each one, over the masked texels only (the mesh texels of the atlas)
    def box(a):
        c = np.cumsum(np.cumsum(np.pad(a, ((radius + 1, radius), (radius + 1, radius))), axis=0), axis=1)
        k = 2 * radius + 1
        return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    weights = box(mask.astype(np.float64))
    return box(np.where(mask, values, 0.0)) / np.maximum(weights, 1e-9)


def pad_gain(gain_map, iterations=8):
    # spreads a per-texel gain (NaN outside the mesh) into the uncovered texels around the pieces of the atlas: the sim filters
    # across them, uncorrected borders showed as dark lines along the triangle edges
    gain = gain_map.copy()
    for _ in range(iterations):
        missing = np.isnan(gain[..., 0])
        if not missing.any():
            break
        valid = ~missing
        filled = np.where(valid[..., None], gain, 0.0)
        sums = np.zeros_like(gain)
        counts = np.zeros(missing.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sums += np.roll(filled, (dy, dx), axis=(0, 1))
            counts += np.roll(valid, (dy, dx), axis=(0, 1))
        fill = missing & (counts > 0)
        gain[fill] = sums[fill] / counts[fill, None]
    return np.nan_to_num(gain, nan=1.0)
