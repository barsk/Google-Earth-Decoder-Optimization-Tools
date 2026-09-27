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

##################################################################
# Placement of the Google Earth tiles in their MSFS frame
##################################################################
#
# Earth2MSFS writes all the tiles of a download in one frame: the tangent plane of Google's globe (a sphere) at a reference
# node, in meters (glTF: east = -x, north = z, up = y). MSFS places each tile at the south west corner of its octree cell,
# on the WGS84 ellipsoid, with the tile model in the local tangent frame of that corner. The frame of the download is
# found from the octree cells of the node meshes (their names are their octant paths), so that the placement also corrects
# the scale error of older Earth2MSFS versions (0.3% to the north), and the curvature of the earth over large sceneries.

import json
import math
import os
import re

import numpy as np

from .octant import get_latlonbox_from_file_name

GOOGLE_EARTH_RADIUS = 6371010.0
WGS84_SEMI_MAJOR_AXIS = 6378137.0
WGS84_ECCENTRICITY_SQUARED = 0.00669437999014
# maximum distance (in meters) between a node and its octree cell for the node to be used by the fit
PLACEMENT_OUTLIER_DISTANCE = 0.3
# a tile whose nodes are further than this distance (in meters) from the frame of the project comes from another download
PLACEMENT_FRAME_MISMATCH_DISTANCE = 1.0
PLACEMENT_MIN_NODES = 6
OCTANT_PATH_PATTERN = re.compile(r"^(\d{2,})")


def enu_basis(lat, lon):
    # east, north and up unit vectors of the tangent frame at the (geodetic or spherical) latitude and longitude, in degrees
    phi, lam = math.radians(lat), math.radians(lon)
    east = np.array([-math.sin(lam), math.cos(lam), 0.0])
    north = np.array([-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)])
    up = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
    return east, north, up


def sphere_to_ecef(lat, lon, alt):
    phi, lam = np.radians(lat), np.radians(lon)
    r = GOOGLE_EARTH_RADIUS + np.asarray(alt, dtype=float)
    return np.stack([r * np.cos(phi) * np.cos(lam), r * np.cos(phi) * np.sin(lam), r * np.sin(phi)], axis=-1)


def ecef_to_sphere(points):
    x, y, z = points[..., 0], points[..., 1], points[..., 2]
    return np.degrees(np.arctan2(z, np.hypot(x, y))), np.degrees(np.arctan2(y, x)), np.linalg.norm(points, axis=-1) - GOOGLE_EARTH_RADIUS


def wgs84_to_ecef(lat, lon, alt):
    phi, lam = np.radians(lat), np.radians(lon)
    n = WGS84_SEMI_MAJOR_AXIS / np.sqrt(1.0 - WGS84_ECCENTRICITY_SQUARED * np.sin(phi) ** 2)
    alt = np.asarray(alt, dtype=float)
    return np.stack([(n + alt) * np.cos(phi) * np.cos(lam), (n + alt) * np.cos(phi) * np.sin(lam), (n * (1.0 - WGS84_ECCENTRICITY_SQUARED) + alt) * np.sin(phi)], axis=-1)


def wgs84_meters_per_degree(lat):
    # meters per degree of latitude and of longitude on the WGS84 ellipsoid
    phi = math.radians(lat)
    w = math.sqrt(1.0 - WGS84_ECCENTRICITY_SQUARED * math.sin(phi) ** 2)
    return math.radians(1.0) * WGS84_SEMI_MAJOR_AXIS * (1.0 - WGS84_ECCENTRICITY_SQUARED) / w ** 3, math.radians(1.0) * WGS84_SEMI_MAJOR_AXIS / w * math.cos(phi)


def wgs84_to_tile(lat, lon, alt, tile_lat, tile_lon, tile_alt):
    # east, north and up coordinates (in meters) of WGS84 positions in the local tangent frame of a tile origin
    east, north, up = enu_basis(tile_lat, tile_lon)
    d = wgs84_to_ecef(lat, lon, alt) - wgs84_to_ecef(tile_lat, tile_lon, tile_alt)
    return d @ east, d @ north, d @ up


class DownloadFrame:
    # the frame of the models of one Earth2MSFS download: raw (east, north) -> tangent plane of Google's globe at the
    # reference (lat, lon, alt), through a 2x2 matrix and an offset found from the octree cells of the nodes
    def __init__(self, lat, lon, alt, matrix, offset):
        self.lat, self.lon, self.alt = float(lat), float(lon), float(alt)
        self.matrix = np.array(matrix, dtype=float)
        self.offset = np.array(offset, dtype=float)

    def to_dict(self):
        return {"lat": self.lat, "lon": self.lon, "alt": self.alt, "matrix": self.matrix.tolist(), "offset": self.offset.tolist()}

    @staticmethod
    def from_dict(data):
        return DownloadFrame(data["lat"], data["lon"], data["alt"], data["matrix"], data["offset"])

    def to_sphere(self, east, north, up):
        # raw coordinates -> latitude, longitude and altitude on Google's globe
        plane = np.stack([east, north], axis=-1) @ self.matrix.T + self.offset
        e, n, u = enu_basis(self.lat, self.lon)
        points = sphere_to_ecef(self.lat, self.lon, self.alt) + plane[..., 0:1] * e + plane[..., 1:2] * n + np.asarray(up, dtype=float)[..., None] * u
        return ecef_to_sphere(points)

    def to_tile(self, east, north, up, tile_lat, tile_lon, tile_alt):
        # raw coordinates -> local frame of the tile placed by MSFS at (tile_lat, tile_lon, tile_alt) on the WGS84 ellipsoid.
        # The latitudes and longitudes of Google's globe are WGS84 ones, and its altitudes are kept
        lat, lon, alt = self.to_sphere(east, north, up)
        return wgs84_to_tile(lat, lon, alt, tile_lat, tile_lon, tile_alt)


def read_raw_nodes(model_file_path):
    # (east, north, up) center of each node mesh of an Earth2MSFS glTF file, with the center of its octree cell.
    # Returns None if the file is not a raw Earth2MSFS file (transformed nodes, or no octant names)
    try:
        with open(model_file_path, "r") as file:
            gltf = json.load(file)
    except (OSError, ValueError):
        return None

    for node in gltf.get("nodes", []):
        if any(key in node for key in ("matrix", "translation", "rotation", "scale")):
            return None

    nodes = []
    for mesh in gltf.get("meshes", []):
        match = OCTANT_PATH_PATTERN.match(mesh.get("name", ""))
        if not match:
            continue
        box = get_latlonbox_from_file_name(match.group(1))
        if tuple(box) == (0, 0, 0, 0):
            continue
        mins, maxs = [math.inf] * 3, [-math.inf] * 3
        for primitive in mesh.get("primitives", []):
            accessor = gltf["accessors"][primitive["attributes"]["POSITION"]]
            if "min" not in accessor or "max" not in accessor:
                continue
            mins = [min(a, b) for a, b in zip(mins, accessor["min"])]
            maxs = [max(a, b) for a, b in zip(maxs, accessor["max"])]
        if math.isinf(mins[0]):
            continue
        n, s, w, e = tuple(box)
        # glTF axes: east = -x, north = z, up = y
        nodes.append((-(mins[0] + maxs[0]) / 2.0, (mins[2] + maxs[2]) / 2.0, (mins[1] + maxs[1]) / 2.0, (n + s) / 2.0, (w + e) / 2.0))

    return nodes if nodes else None


def fit_download_frame(nodes, alt):
    # nodes: rows of (east, north, up, cell center lat, cell center lon). Returns the frame and the distance of each node
    # to its cell (in meters), or None if the nodes do not constrain the frame
    nodes = np.asarray(nodes, dtype=float)
    if len(nodes) < PLACEMENT_MIN_NODES:
        return None
    east, north, up, cell_lat, cell_lon = nodes.T
    if np.ptp(east) < 10.0 or np.ptp(north) < 10.0:
        return None

    # first guess of the reference (the raw origin): linear fits of the cell centers
    lat = np.polyval(np.polyfit(north, cell_lat, 1), 0.0)
    lon = np.polyval(np.polyfit(east, cell_lon, 1), 0.0)
    keep = np.ones(len(nodes), dtype=bool)
    frame, distances = None, None

    for _ in range(8):
        # the cell centers in the tangent plane at the reference
        e, n, u = enu_basis(lat, lon)
        d = sphere_to_ecef(cell_lat, cell_lon, alt + up) - sphere_to_ecef(lat, lon, alt)
        plane = np.stack([d @ e, d @ n], axis=-1)
        # the raw axes are the east and north of the reference node: one scale per axis, no rotation
        a_east = np.column_stack([east, np.ones(len(nodes))])
        a_north = np.column_stack([north, np.ones(len(nodes))])
        for _ in range(5):
            if keep.sum() < PLACEMENT_MIN_NODES:
                return None
            scale_east, offset_east = np.linalg.lstsq(a_east[keep], plane[keep, 0], rcond=None)[0]
            scale_north, offset_north = np.linalg.lstsq(a_north[keep], plane[keep, 1], rcond=None)[0]
            distances = np.hypot(scale_east * east + offset_east - plane[:, 0], scale_north * north + offset_north - plane[:, 1])
            new_keep = distances < max(PLACEMENT_OUTLIER_DISTANCE, 3.0 * float(np.median(distances[keep])))
            if (new_keep == keep).all():
                break
            keep = new_keep
        frame = DownloadFrame(lat, lon, alt, [[scale_east, 0.0], [0.0, scale_north]], [offset_east, offset_north])
        # move the reference to the raw origin, so that the tangent plane is the one of the download
        if np.hypot(*frame.offset) < 0.001:
            break
        lat, lon, _ = ecef_to_sphere(sphere_to_ecef(lat, lon, alt) + frame.offset[0] * e + frame.offset[1] * n)
        lat, lon = float(lat), float(lon)

    return frame, distances


def fit_tiles_placement(tile_model_files, tile_altitudes):
    # tile_model_files: tile name -> raw glTF files of the tile (all lods), tile_altitudes: tile name -> altitude of the tile.
    # Returns {"frames": [...], "tiles": {tile name: frame index}}: one frame for the tiles of one download, and separate
    # frames for the tiles that do not match it (another download). The tiles without raw nodes are not placed
    tile_nodes = {}
    for tile_name, model_files in tile_model_files.items():
        nodes = []
        for model_file in model_files:
            nodes.extend(read_raw_nodes(model_file) or [])
        if nodes:
            tile_nodes[tile_name] = nodes

    frames, tiles = [], {}
    remaining = dict(tile_nodes)
    while remaining:
        names = list(remaining.keys())
        alt = float(tile_altitudes.get(names[0], 0.0))
        result = fit_download_frame([node for name in names for node in remaining[name]], alt)
        if result is None:
            break
        frame, distances = result
        matching, i = [], 0
        for name in names:
            count = len(remaining[name])
            if float(np.median(distances[i:i + count])) < PLACEMENT_FRAME_MISMATCH_DISTANCE:
                matching.append(name)
            i += count
        if not matching:
            # no tile matches the frame of the whole set: fit the tiles one by one
            for name in names:
                single = fit_download_frame(remaining[name], float(tile_altitudes.get(name, 0.0)))
                if single is not None:
                    tiles[name] = len(frames)
                    frames.append(single[0].to_dict())
            break
        if len(matching) < len(names):
            # refit the frame without the tiles of the other downloads
            result = fit_download_frame([node for name in matching for node in remaining[name]], alt)
            if result is None:
                break
            frame = result[0]
        for name in matching:
            tiles[name] = len(frames)
            del remaining[name]
        frames.append(frame.to_dict())

    return {"frames": frames, "tiles": tiles}


def save_tiles_placement(file_path, placement):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as file:
        json.dump(placement, file, indent=1)


def load_tile_frame(file_path, tile_name):
    # the frame of a tile, or None if the tile has no placement (it is placed by its bounding box then)
    if not file_path or not os.path.isfile(file_path):
        return None
    with open(file_path, "r") as file:
        placement = json.load(file)
    index = placement.get("tiles", {}).get(tile_name)
    if index is None:
        return None
    return DownloadFrame.from_dict(placement["frames"][index])
