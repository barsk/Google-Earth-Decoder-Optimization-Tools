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

# The normals along the node edges of a model. Google's nodes have skirts: vertical curtains (~0.5 m) along their edges, whose
# lower corners reuse the texture coordinates of the edge above (hiding the cracks between nodes). The downloaders compute the
# vertex normals by averaging the faces around each vertex, the skirts included: the ground corners on a node edge got normals
# tilted by up to ~40 degrees, which MSFS lit as dark or bright ramps along every node edge (also on the corners step 4 makes
# when it clips the nodes, which carry the tilted normals). The normals are computed again from the surface faces around each
# position, as the downloaders did without the skirts (the corners at the same position welded, also across the node edges);
# the skirts keep hiding the cracks, with the ground's normals. Plain numpy on the glTF files (no Blender), idempotent.

import json
import os

import numpy as np

# a face with less than this share of the texels per m2 usual in its primitive is a skirt
SKIRT_DENSITY = 0.01
# the corners at the same position (m)
WELD = 0.001
FLOAT = 5126


def _accessor(gltf, buffers, index, components):
    # (array (count, components), (buffer index, byte offset, stride)) of a float or index accessor
    accessor = gltf["accessors"][index]
    view = gltf["bufferViews"][accessor["bufferView"]]
    dtype = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[accessor["componentType"]]
    size = np.dtype(dtype).itemsize * components
    stride = view.get("byteStride") or size
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    data = buffers[view["buffer"]]
    count = accessor["count"]
    raw = np.frombuffer(data, dtype=np.uint8, count=(count - 1) * stride + size, offset=offset)
    array = np.lib.stride_tricks.as_strided(raw, shape=(count, size), strides=(stride, 1)).copy().view(dtype).reshape(count, components)
    return array, (view["buffer"], offset, stride)


def _corner_weights(a, b, c):
    # each face's corner angles (the downloaders' weighting)
    def angle(p, q):
        with np.errstate(invalid="ignore", divide="ignore"):
            cos = np.einsum("ij,ij->i", p, q) / (np.linalg.norm(p, axis=1) * np.linalg.norm(q, axis=1))
        return np.arccos(np.clip(np.nan_to_num(cos, nan=1.0), -1.0, 1.0))
    return np.column_stack([angle(b - a, c - a), angle(c - b, a - b), angle(a - c, b - c)])


def fix_skirt_normals(gltf_path):
    """The normals computed again from the surface faces around each position (models with skirts). Returns the number of
    vertices changed (0: the file is left as it is)."""
    with open(gltf_path, encoding="utf-8") as file:
        gltf = json.load(file)
    folder = os.path.dirname(gltf_path)
    uris = [buffer.get("uri") for buffer in gltf.get("buffers", [])]
    if not uris or any(uri is None or uri.startswith("data:") for uri in uris):
        return 0
    buffers = [bytearray(open(os.path.join(folder, uri), "rb").read()) for uri in uris]
    changed = 0
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            attributes = primitive.get("attributes", {})
            if primitive.get("mode", 4) != 4 or "indices" not in primitive or not all(k in attributes for k in ("POSITION", "NORMAL", "TEXCOORD_0")):
                continue
            if gltf["accessors"][attributes["NORMAL"]]["componentType"] != FLOAT:
                continue
            positions, _ = _accessor(gltf, buffers, attributes["POSITION"], 3)
            normals, (buffer, offset, stride) = _accessor(gltf, buffers, attributes["NORMAL"], 3)
            uvs, _ = _accessor(gltf, buffers, attributes["TEXCOORD_0"], 2)
            faces = _accessor(gltf, buffers, primitive["indices"], 1)[0].astype(np.int64).reshape(-1, 3)
            if not len(faces):
                continue
            p = positions.astype(np.float64)
            a, b, c = p[faces[:, 0]], p[faces[:, 1]], p[faces[:, 2]]
            cross = np.cross(b - a, c - a)
            area = np.linalg.norm(cross, axis=1) / 2
            t = uvs.astype(np.float64)[faces]
            uv_area = np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1])) / 2
            if not uv_area.sum():
                continue
            density = uv_area / np.maximum(area, 1e-12)
            order = np.argsort(density)
            weights = np.cumsum(uv_area[order])
            usual = density[order][np.searchsorted(weights, weights[-1] / 2)]
            skirt = (density < usual * SKIRT_DENSITY) & (area > 1e-8)
            if not skirt.any():
                continue
            # the positions (welded), the surface faces' angle weighted normals summed per position
            keys, position_ids = np.unique(np.round(p / WELD).astype(np.int64), axis=0, return_inverse=True)
            position_ids = position_ids.ravel()
            surface = ~skirt
            sums = np.zeros((len(keys), 3))
            corner = _corner_weights(a[surface], b[surface], c[surface])
            for k in range(3):
                np.add.at(sums, position_ids[faces[surface, k]], cross[surface] * corner[:, k:k + 1])
            length = np.linalg.norm(sums, axis=1)
            # (the corners of the skirts only: as they are)
            new = length[position_ids] > 0
            if not new.any():
                continue
            values = (sums[position_ids[new]] / length[position_ids[new], None]).astype(np.float32)
            # (the side of the original normals, for the whole primitive: the face winding of the export may be reversed; a
            # corner by corner check flipped some, their original normals being too tilted)
            if np.einsum("ij,ij->i", values, normals[new]).sum() < 0:
                values *= -1
            differ = np.abs(values - normals[new]).max(axis=1) > 1e-4
            if not differ.any():
                continue
            target = buffers[buffer]
            for index, value in zip(np.nonzero(new)[0][differ], values[differ]):
                start = offset + int(index) * stride
                target[start:start + 12] = value.tobytes()
            changed += int(differ.sum())
    if changed:
        for uri, data in zip(uris, buffers):
            with open(os.path.join(folder, uri), "wb") as file:
                file.write(data)
    return changed
