# Landmarks and points of interest

*Geocode tools > Upgrade the landmarks of the scenery (more detailed lods than the tiles)*. Run it after step 2,
before step 2a.

Some buildings deserve more detail than the rest of the city: a cathedral, a castle, a stadium. This tool keeps the
most detailed LOD (e.g. LOD 20) for chosen buildings, as separate objects, while the tiles keep less detailed LODs
(e.g. up to LOD 19). The same list marks the buildings that become points of interest in MSFS.

## landmarks.csv

The list is `landmarks.csv` in the project folder: `;` separated, in the Windows-1252 encoding, for a spreadsheet
(Excel writes it back in that encoding). If it doesn't exist, the first run creates it with candidates from
OpenStreetMap and stops, so that you can review it.

| Column | Meaning |
|---|---|
| `landmark` | `true`: the building keeps the most detailed LOD. Suggested from a score of 3. |
| `poi` | `true`: the building is a point of interest in MSFS, written by [step 6](6-finalize.md). Suggested for the named buildings from a score of 10. A place of worship is suggested only if it is a cathedral or has Wikipedia articles in at least 5 languages. |
| `name` | The name shown by the point of interest (editable). |
| `osm_id` | The OpenStreetMap id: `W` for a way, `R` for a relation (e.g. `W96307473`). |
| `score` | The notability score: Wikidata, historic, place of worship, public building, size... |
| `wikipedias` | The number of Wikipedia languages with an article about the building, from Wikidata. Sort by it to judge how well known a building is. |
| `building`, `area_m2`, `lat`, `lon`, `reasons` | The kind of building, its footprint, its position, and why it was suggested. |

The `landmark` and `osm_id` columns are required. The `true`/`false` values can also be `yes`/`no`, `1`/`0`, `x`, or
the booleans of a Swedish Excel. Rows can be added by hand with just an OpenStreetMap id. A file saved with `,` as the
separator is read too, rows starting with `#` are skipped, and other columns are ignored.

## What it does

For each row with `landmark` true:

1. The building's outline comes from the OpenStreetMap API, enlarged by the *Geocode margin* (GEOCODE section; Google
   Earth's buildings are a little larger than the OpenStreetMap footprints).
2. The parts of the tiles inside it, on every LOD, become separate objects, `landmark_<id>_<tile>`, then are removed
   from the tiles.

Then the tile LODs more detailed than `tiles_max_lod_level` (`[LANDMARKS]` section of the project's ini file, 19 by
default) are removed, and the textures of the landmarks are repacked to keep only the parts they use.

* **Buildings already upgraded are skipped.** Define all the landmarks before running it on the full list: the tile
  LODs it removes can't be used by later landmarks.
* **Tiles listed in `upgrade_tiles.txt`** (project folder, one tile name per line) keep all their LODs, and the
  landmarks inside them are skipped.

## Projects downloaded only up to the tiles' level

If the tiles go only up to `tiles_max_lod_level`, there is no more detailed data in the project. With the
[optional tile downloader](../tile-downloader.md), the tool downloads the next level for the landmarks only and adds it
to their tiles before isolating them. Set the colours of the tiles' download in the TEXTURES section (e.g. brightness
0.85), so that the landmarks match the tiles. Without a downloader, the landmarks keep the levels of the tiles.

## Points of interest

[Step 6](6-finalize.md) writes a point of interest (an MSFS `LandmarkLocation` of type POI) for each row with `poi`
true, named after `name`:

* above the top of the building (its highest point, from the landmark object or the tiles inside its outline), plus 2 m;
* with an id made from the OpenStreetMap id, so that the points of interest of rows removed or set to `false` are
  removed again;
* in a scenery made of several projects, only by the project whose tiles contain the point.

After changing `poi` or `name`, run step 6 again and build. Test from the Community folder: the points of interest
don't show when the package is loaded in devmode. In flight, the sim's landmark markers option must be on.
