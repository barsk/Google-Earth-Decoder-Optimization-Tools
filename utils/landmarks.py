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

# Landmarks file of a project: the OSM ids of the buildings that keep more detailed lods than the tiles.
# One id per line, prefixed by its OSM type (W way, R relation), comments after '#'. The candidates are suggested
# from OpenStreetMap, scored on notability signals (wikidata, historic, place of worship, public buildings, size...)

import math
import re

from utils.geo_pandas import overpass_query
from utils.script_errors import ScriptError

LANDMARK_ID = re.compile(r"^([WRwr]?)(\d+)$")
NOTABLE_BUILDINGS = {"cathedral", "church", "chapel", "mosque", "synagogue", "temple", "stadium", "sports_hall", "train_station",
                     "transportation", "civic", "public", "government", "university", "college", "hospital", "museum", "castle",
                     "palace", "theatre", "hotel", "grandstand", "tower", "fire_station", "library", "school"}
PLACES_OF_WORSHIP = {"cathedral", "church", "chapel", "mosque", "synagogue", "temple"}
STRUCTURES = {"tower", "water_tower", "lighthouse", "chimney", "silo", "storage_tank"}


def read_landmarks(file_path):
    # the OSM ids of the landmarks file, as W<id> or R<id> (ids without type are ways)
    landmarks = []
    with open(file_path, encoding="utf-8") as file:
        for line in file:
            token = line.split("#", 1)[0].strip().split()
            if not token:
                continue
            match = LANDMARK_ID.match(token[0])
            if not match:
                raise ScriptError("Invalid OSM id in " + file_path + ": " + token[0] + " (expected e.g. W96307473 or R1388249)")
            osm_id = (match.group(1) or "W").upper() + match.group(2)
            if osm_id not in landmarks:
                landmarks.append(osm_id)
    return landmarks


def write_landmark_candidates(file_path, coords, overpass_api_uri, project_name, min_score):
    # suggest the landmarks of the project area (coords: north, south, east, west) from OpenStreetMap
    north, south, east, west = coords[0], coords[1], coords[2], coords[3]
    b = "%.6f,%.6f,%.6f,%.6f" % (min(south, north), min(west, east), max(south, north), max(west, east))
    structures = "|".join(sorted(STRUCTURES))
    query = "[out:json][timeout:90];(way[\"building\"](%s);relation[\"building\"](%s);way[\"man_made\"~\"^(%s)$\"](%s););out tags geom;" % (b, b, structures, b)
    candidates = []
    for element in overpass_query(overpass_api_uri, query).get("elements", []):
        tags = element.get("tags", {})
        area, (lat, lon) = __footprint(element)
        points, reasons = __score(tags, area)
        if points == 0:
            continue
        name = tags.get("name") or (tags.get("addr:street", "") + " " + tags.get("addr:housenumber", "")).strip() or "(unnamed)"
        candidates.append([points, element["type"][0].upper() + str(element["id"]), name, tags.get("building") or tags.get("man_made", ""), area, lat, lon, reasons])
    candidates.sort(key=lambda c: (-c[0], -c[4]))

    # unnamed candidates next to a named one are usually a part of it (e.g. a church annex)
    named = [c for c in candidates if c[2] != "(unnamed)"]
    for candidate in candidates:
        if candidate[2] == "(unnamed)":
            near = [n for n in named if math.hypot((n[5] - candidate[5]) * 110574, (n[6] - candidate[6]) * 111320 * math.cos(math.radians(candidate[5]))) < 60]
            if near:
                candidate[2] = "(next to " + near[0][2] + ")"

    with open(file_path, "w", encoding="utf-8") as file:
        file.write("# Landmarks of %s: buildings keeping more detailed lods than the tiles. One OpenStreetMap id per line\n" % project_name)
        file.write("# (W way, R relation), comments after '#'. Suggested from OpenStreetMap: the candidates with a score >= %d are\n" % min_score)
        file.write("# active, the others are commented out. Edit freely, then run the upgrade landmarks tool again.\n")
        file.write("# id          score  name                             building       footprint  centre             reasons\n")
        for points, osm_id, name, kind, area, lat, lon, reasons in candidates:
            file.write("%s%-12s # %2d  %-32s %-14s %6.0f m2  %.5f,%.5f  %s\n" % ("" if points >= min_score else "# ", osm_id, points, name[:32], kind[:14], area, lat, lon, ", ".join(reasons)))

    return len(candidates), len([c for c in candidates if c[0] >= min_score])


def __footprint(element):
    # area (m2) and centre of a way's outline, of a relation's outer ways, or of its bounding box
    rings = [element["geometry"]] if element["type"] == "way" and "geometry" in element else \
        [m["geometry"] for m in element.get("members", []) if m.get("role") == "outer" and "geometry" in m]
    points = [p for ring in rings for p in ring]
    if not points and "bounds" in element:
        b = element["bounds"]
        lat0 = (b["minlat"] + b["maxlat"]) / 2
        return (b["maxlat"] - b["minlat"]) * 110574 * (b["maxlon"] - b["minlon"]) * 111320 * math.cos(math.radians(lat0)), (lat0, (b["minlon"] + b["maxlon"]) / 2)
    if not points:
        return 0.0, (element.get("lat", 0.0), element.get("lon", 0.0))
    lat0 = sum(p["lat"] for p in points) / len(points)
    lon0 = sum(p["lon"] for p in points) / len(points)
    area = 0.0
    for ring in rings:
        xy = [((p["lon"] - lon0) * 111320 * math.cos(math.radians(lat0)), (p["lat"] - lat0) * 110574) for p in ring]
        area += abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))) / 2
    return area, (lat0, lon0)


def __number(value):
    try:
        return float(str(value).split(";")[0].replace("m", "").strip())
    except ValueError:
        return None


def __score(tags, area):
    reasons = []
    if "wikidata" in tags or "wikipedia" in tags:
        reasons.append((5, "wikipedia/wikidata"))
    if "historic" in tags or "heritage" in tags:
        reasons.append((4, "historic"))
    if tags.get("amenity") == "place_of_worship" or tags.get("building") in PLACES_OF_WORSHIP:
        reasons.append((4, "place of worship"))
    if tags.get("tourism") in ("attraction", "museum", "gallery", "viewpoint"):
        reasons.append((4, "tourism=" + tags["tourism"]))
    if tags.get("man_made") in STRUCTURES:
        reasons.append((3, "man_made=" + tags["man_made"]))
    if tags.get("building") in NOTABLE_BUILDINGS:
        reasons.append((2, "building=" + tags["building"]))
    height = __number(tags.get("height"))
    levels = __number(tags.get("building:levels"))
    if (height and height >= 20) or (levels and levels >= 6):
        reasons.append((2, "tall (%s)" % ("%.0f m" % height if height else "%d levels" % levels)))
    if "name" in tags:
        reasons.append((1, "named"))
    if area >= 5000:
        reasons.append((2, "very large (%.0f m2)" % area))
    elif area >= 2000:
        reasons.append((1, "large (%.0f m2)" % area))
    return sum(points for points, _ in reasons), [reason for _, reason in reasons]
