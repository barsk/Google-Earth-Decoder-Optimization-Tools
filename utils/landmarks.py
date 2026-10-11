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

# Landmarks file of a project (landmarks.csv, ';' separated, windows-1252, for a spreadsheet): one row per building suggested
# from OpenStreetMap, scored on notability signals (wikidata, historic, place of worship, public buildings, size...). The columns:
#   landmark  true: the building keeps more detailed lods than the tiles (the landmarks step)
#   poi       true: the building is a point of interest in MSFS, named after the name column (step 6)
#   name      the name of the point of interest (from OpenStreetMap, editable)
#   osm_id    W<id> (way) or R<id> (relation)
#   lat, lon  the place of the point of interest (the centre of the building)
#   the others are informative (score, wikipedias, building, area_m2, reasons). Rows can be added, removed or reordered, the
#   columns are found by their name in the first row
# wikipedias: the number of Wikipedia languages with an article on the building (Wikidata), its notability beyond the city. Most
# churches have one (a Swedish article on each church): a place of worship is a point of interest by default only when it is a
# cathedral or has articles in POI_WORSHIP_MIN_WIKIPEDIAS languages

import csv
import math
import re
import time
import uuid

import requests

from constants import POI_WORSHIP_MIN_WIKIPEDIAS, EOL, CEND
from utils.colored_print import pr_bg_orange
from utils.geo_pandas import overpass_query
from utils.script_errors import ScriptError

LANDMARK_ID = re.compile(r"^([WRwr]?)(\d+)$")
LANDMARKS_COLUMNS = ("landmark", "poi", "name", "osm_id", "score", "wikipedias", "building", "area_m2", "lat", "lon", "reasons")
DELIMITER = ";"
# what a spreadsheet saves a CSV file back as (e.g. Excel 2010, which reads UTF-8 but writes windows-1252)
ENCODING = "cp1252"
# (also the values of a spreadsheet that saved the column as booleans, e.g. a Swedish Excel)
TRUE_VALUES = {"true", "yes", "y", "1", "x", "sant", "ja", "j"}
FALSE_VALUES = {"false", "no", "n", "0", "", "falskt", "nej"}
UNNAMED = "(unnamed)"
# the first group of the instance ids of the points of interest made from the landmarks file: the ones of the rows removed from
# the file are found by it
POI_INSTANCE_ID_PREFIX = "6E0D0791"
NOTABLE_BUILDINGS = {"cathedral", "church", "chapel", "mosque", "synagogue", "temple", "stadium", "sports_hall", "train_station",
                     "transportation", "civic", "public", "government", "university", "college", "hospital", "museum", "castle",
                     "palace", "theatre", "hotel", "grandstand", "tower", "fire_station", "library", "school"}
PLACES_OF_WORSHIP = {"cathedral", "church", "chapel", "mosque", "synagogue", "temple"}
STRUCTURES = {"tower", "water_tower", "lighthouse", "chimney", "silo", "storage_tank"}
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_BATCH = 50
WIKIDATA_RETRIES = 4
WIKIDATA_RETRY_PAUSE = 15
# the sitelinks of Wikidata that are not Wikipedias (the other projects end with their own name, e.g. svwikivoyage)
NOT_WIKIPEDIAS = {"commonswiki", "specieswiki", "metawiki", "wikidatawiki", "mediawikiwiki", "sourceswiki", "outreachwiki",
                  "wikimaniawiki", "incubatorwiki", "wikifunctionswiki", "abstractwiki"}
# a cathedral: its name (the languages around), or its Wikidata class (e.g. "Lutheran cathedral", "co-cathedral")
CATHEDRAL_NAME = re.compile(r"domkyrka|domkirke|domkirkja|tuomiokirkko|cathedral|cathédrale|catedral|cattedrale|kathedrale|katedral", re.IGNORECASE)


def normalize_osm_id(value, file_path=str()):
    # W<id> or R<id> (an id without type is a way)
    match = LANDMARK_ID.match(str(value).strip())
    if not match:
        raise ScriptError("Invalid OSM id in " + file_path + ": " + str(value) + " (expected e.g. W96307473 or R1388249)")
    return (match.group(1) or "W").upper() + match.group(2)


def read_landmark_rows(file_path):
    # the rows of the landmarks file: {landmark, poi (bools), name, osm_id, lat, lon, area_m2 (floats or None), line}
    # (UTF-8 first: the files written before windows-1252, or saved as UTF-8 by a spreadsheet; windows-1252 text is not valid UTF-8)
    try:
        with open(file_path, encoding="utf-8-sig") as file:
            text = file.read()
    except UnicodeDecodeError:
        with open(file_path, encoding=ENCODING) as file:
            text = file.read()
    lines = text.splitlines()
    if not lines:
        return []
    delimiter = DELIMITER if DELIMITER in lines[0] or "," not in lines[0] else ","
    reader = csv.reader(lines, delimiter=delimiter)
    header = [column.strip().lower() for column in next(reader)]
    for column in ("landmark", "osm_id"):
        if column not in header:
            raise ScriptError("Column " + column + " missing in the first row of " + file_path + " (" + DELIMITER.join(LANDMARKS_COLUMNS) + ")")

    def cell(values, column):
        index = header.index(column) if column in header else -1
        return values[index].strip() if 0 <= index < len(values) else str()

    def boolean(values, column, line):
        value = cell(values, column).lower()
        if value in TRUE_VALUES:
            return True
        if value in FALSE_VALUES:
            return False
        raise ScriptError("Row %d of %s: %s is '%s' (expected true or false)" % (line, file_path, column, cell(values, column)))

    def number(values, column):
        try:
            return float(cell(values, column).replace(",", "."))
        except ValueError:
            return None

    rows = []
    for line, values in enumerate(reader, start=2):
        if not "".join(values).strip() or values[0].strip().startswith("#"):
            continue
        osm_id = cell(values, "osm_id")
        if not osm_id:
            continue
        rows.append({"landmark": boolean(values, "landmark", line), "poi": "poi" in header and boolean(values, "poi", line),
                     "name": cell(values, "name"), "osm_id": normalize_osm_id(osm_id, file_path), "lat": number(values, "lat"),
                     "lon": number(values, "lon"), "area_m2": number(values, "area_m2"), "line": line})
    return rows


def read_landmarks(file_path):
    # the OSM ids of the landmarks (landmark true), as W<id> or R<id>
    landmarks = []
    for row in read_landmark_rows(file_path):
        if row["landmark"] and row["osm_id"] not in landmarks:
            landmarks.append(row["osm_id"])
    return landmarks


def poi_instance_id(osm_id):
    # the same instance id for a building at each run (its point of interest is replaced)
    digest = uuid.uuid5(uuid.NAMESPACE_URL, "https://www.openstreetmap.org/" + osm_id).hex.upper()
    return "{%s-%s-%s-%s-%s}" % (POI_INSTANCE_ID_PREFIX, digest[8:12], digest[12:16], digest[16:20], digest[20:32])


def is_poi_instance_id(instance_id):
    return str(instance_id).upper().startswith("{" + POI_INSTANCE_ID_PREFIX + "-")


def wikidata_notability(qids):
    """{Wikidata id: (number of Wikipedia languages, a cathedral)} of the ids (Wikidata unreachable: {} and a warning)."""
    qids = sorted({qid for qid in qids if re.match(r"^Q\d+$", str(qid))})
    entities = {}
    try:
        for i in range(0, len(qids), WIKIDATA_BATCH):
            entities.update(__wikidata_entities(qids[i:i + WIKIDATA_BATCH], "sitelinks|claims"))
        classes = sorted({c for entity in entities.values() for c in __claim_ids(entity, "P31")})
        labels = {}
        for i in range(0, len(classes), WIKIDATA_BATCH):
            labels.update({qid: entity.get("labels", {}).get("en", {}).get("value", "") for qid, entity in __wikidata_entities(classes[i:i + WIKIDATA_BATCH], "labels").items()})
    except (requests.exceptions.RequestException, ValueError, KeyError) as ex:
        pr_bg_orange("Wikidata not reachable (%s): no wikipedias column, a place of worship is a point of interest only as a cathedral by its name" % ex + EOL + CEND)
        return {}
    return {qid: (len([site for site in entity.get("sitelinks", {}) if site.endswith("wiki") and site not in NOT_WIKIPEDIAS]),
                  any("cathedral" in labels.get(c, "").lower() for c in __claim_ids(entity, "P31")))
            for qid, entity in entities.items() if "missing" not in entity}


def is_place_of_worship(tags):
    return tags.get("amenity") == "place_of_worship" or tags.get("building") in PLACES_OF_WORSHIP


def default_poi(tags, score, poi_min_score, notability):
    # named, and for a place of worship a cathedral or an article in POI_WORSHIP_MIN_WIKIPEDIAS languages (most churches have one,
    # the cathedral of a city many), else a score from poi_min_score
    if "name" not in tags:
        return False
    if not is_place_of_worship(tags):
        return score >= poi_min_score
    wikipedias, cathedral = notability.get(tags.get("wikidata"), (0, False))
    return cathedral or tags.get("building") == "cathedral" or bool(CATHEDRAL_NAME.search(tags["name"])) or wikipedias >= POI_WORSHIP_MIN_WIKIPEDIAS


def landmark_candidates(elements, min_score, poi_min_score, keep_ids=(), notability=None):
    # the rows of the OSM elements (out tags geom) scoring at least one point (or in keep_ids), the best first: landmark true
    # from min_score, poi true as default_poi. notability: wikidata_notability of their wikidata tags (None: fetched)
    if notability is None:
        notability = wikidata_notability(element.get("tags", {}).get("wikidata") for element in elements)
    candidates = []
    for element in elements:
        osm_id = element["type"][0].upper() + str(element["id"])
        tags = element.get("tags", {})
        area, (lat, lon) = __footprint(element)
        points, reasons = __score(tags, area)
        if points == 0 and osm_id not in keep_ids:
            continue
        name = tags.get("name") or (tags.get("addr:street", "") + " " + tags.get("addr:housenumber", "")).strip() or UNNAMED
        candidates.append({"score": points, "osm_id": osm_id, "name": name, "building": tags.get("building") or tags.get("man_made", ""),
                           "area_m2": area, "lat": lat, "lon": lon, "reasons": reasons, "wikipedias": notability.get(tags.get("wikidata"), (None,))[0],
                           "poi": default_poi(tags, points, poi_min_score, notability)})
    candidates.sort(key=lambda c: (-c["score"], -c["area_m2"]))

    # unnamed candidates next to a named one are usually a part of it (e.g. a church annex)
    named = [c for c in candidates if c["name"] != UNNAMED]
    for candidate in candidates:
        if candidate["name"] == UNNAMED:
            near = [n for n in named if math.hypot((n["lat"] - candidate["lat"]) * 110574, (n["lon"] - candidate["lon"]) * 111320 * math.cos(math.radians(candidate["lat"]))) < 60]
            if near:
                candidate["name"] = "(next to " + near[0]["name"] + ")"

    for candidate in candidates:
        candidate["landmark"] = candidate["score"] >= min_score
    return candidates


def write_landmarks_file(file_path, candidates):
    # (a character outside windows-1252 becomes '?', as when a spreadsheet saves the file back)
    with open(file_path, "w", encoding=ENCODING, errors="replace", newline="") as file:
        writer = csv.writer(file, delimiter=DELIMITER)
        writer.writerow(LANDMARKS_COLUMNS)
        for c in candidates:
            writer.writerow(["true" if c["landmark"] else "false", "true" if c["poi"] else "false", c["name"], c["osm_id"], c["score"],
                             "" if c.get("wikipedias") is None else c["wikipedias"], c["building"], "%.0f" % c["area_m2"], "%.6f" % c["lat"],
                             "%.6f" % c["lon"], ", ".join(c["reasons"])])


def write_landmark_candidates(file_path, coords, overpass_api_uri, min_score, poi_min_score):
    # suggest the landmarks of the project area (coords: north, south, east, west) from OpenStreetMap. Returns the number of
    # candidates, of landmarks and of points of interest
    north, south, east, west = coords[0], coords[1], coords[2], coords[3]
    b = "%.6f,%.6f,%.6f,%.6f" % (min(south, north), min(west, east), max(south, north), max(west, east))
    structures = "|".join(sorted(STRUCTURES))
    query = "[out:json][timeout:90];(way[\"building\"](%s);relation[\"building\"](%s);way[\"man_made\"~\"^(%s)$\"](%s););out tags geom;" % (b, b, structures, b)
    candidates = landmark_candidates(overpass_query(overpass_api_uri, query).get("elements", []), min_score, poi_min_score)
    write_landmarks_file(file_path, candidates)
    return len(candidates), len([c for c in candidates if c["landmark"]]), len([c for c in candidates if c["poi"]])


def query_landmark_elements(overpass_api_uri, osm_ids):
    # the OSM elements (out tags geom) of W<id> and R<id> ids
    ways = ",".join(i[1:] for i in osm_ids if i.startswith("W"))
    relations = ",".join(i[1:] for i in osm_ids if i.startswith("R"))
    if not ways and not relations:
        return []
    query = "[out:json][timeout:90];(%s%s);out tags geom;" % ("way(id:%s);" % ways if ways else "", "relation(id:%s);" % relations if relations else "")
    return overpass_query(overpass_api_uri, query).get("elements", [])


def landmark_outlines(elements):
    # {osm id: outline (shapely, lon/lat)} of OSM elements (out geom): a way's outline, a relation's outer ways
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    outlines = {}
    for element in elements:
        rings = [element["geometry"]] if element["type"] == "way" and "geometry" in element else \
            [m["geometry"] for m in element.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        polygons = [Polygon([(p["lon"], p["lat"]) for p in ring]).buffer(0) for ring in rings if len(ring) >= 4]
        if polygons:
            outlines[element["type"][0].upper() + str(element["id"])] = unary_union(polygons)
    return outlines


def gltf_vertices(gltf_path):
    # the vertices (east, north, up in m from the model origin: the model frame is east = -X, north = +Z, up = +Y) of the
    # textured primitives of a model (not the MSFS bounding box cube)
    import json
    import os
    import numpy as np

    with open(gltf_path, encoding="utf-8") as file:
        gltf = json.load(file)
    folder = os.path.dirname(gltf_path)
    buffers = {}
    meshes = {node["mesh"] for node in gltf.get("nodes", []) if "mesh" in node and "bbox" not in node.get("name", "").lower()}
    vertices = []
    for index in sorted(meshes):
        mesh = gltf["meshes"][index]
        if "bbox" in mesh.get("name", "").lower():
            continue
        for primitive in mesh.get("primitives", []):
            attributes = primitive.get("attributes", {})
            if "POSITION" not in attributes or "TEXCOORD_0" not in attributes:
                continue
            accessor = gltf["accessors"][attributes["POSITION"]]
            view = gltf["bufferViews"][accessor["bufferView"]]
            if view["buffer"] not in buffers:
                with open(os.path.join(folder, gltf["buffers"][view["buffer"]]["uri"]), "rb") as file:
                    buffers[view["buffer"]] = file.read()
            stride = view.get("byteStride") or 12
            offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
            raw = np.frombuffer(buffers[view["buffer"]], dtype=np.uint8, count=(accessor["count"] - 1) * stride + 12, offset=offset)
            positions = np.lib.stride_tricks.as_strided(raw, shape=(accessor["count"], 12), strides=(stride, 1)).copy().view(np.float32).reshape(-1, 3)
            vertices.append(np.column_stack([-positions[:, 0], positions[:, 2], positions[:, 1]]))
    return np.concatenate(vertices).astype(np.float64) if vertices else np.empty((0, 3))


def __wikidata_entities(qids, props):
    # (tried again after a pause: a busy server, or a short network failure, made a whole city fall back to the cathedral names)
    for attempt in range(WIKIDATA_RETRIES):
        try:
            response = requests.get(WIKIDATA_API, params={"action": "wbgetentities", "ids": "|".join(qids), "props": props, "languages": "en", "format": "json"},
                                    headers={"User-Agent": "GEDOT-landmarks/1.0 (MSFS scenery tool)"}, timeout=60)
            response.raise_for_status()
            return response.json()["entities"]
        except (requests.exceptions.RequestException, ValueError, KeyError):
            if attempt == WIKIDATA_RETRIES - 1:
                raise
            time.sleep(WIKIDATA_RETRY_PAUSE)


def __claim_ids(entity, prop):
    return [claim["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for claim in entity.get("claims", {}).get(prop, [])
            if isinstance(claim["mainsnak"].get("datavalue", {}).get("value"), dict)]


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
