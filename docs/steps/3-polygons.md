# Step 3: Create the terraform and exclusion polygons

Downloads the OpenStreetMap data of the scenery and creates the polygons that keep MSFS's own buildings and trees off
the photogrammetry. The OpenStreetMap settings of the project are set in this step only: steps 4 and 5 use the same
data and settings, so set them before running step 3.

## OpenStreetMap data

All the data the enabled options need comes in a single query to the Overpass server (*Uri of the Overpass API*, set in
the addon preferences; a [local server](../installation/openstreetmap-server.md) is recommended), clipped a little
beyond the border of the scenery. It is kept in the `osm` and `shp` folders
of the project and reused by steps 4 and 5. *Force openStreetMap data download* downloads it again (e.g. after the
OpenStreetMap data has changed).

## Polygons

The polygons are written to `scene\objects.xml`, at the altitude of the ground, in groups that the MSFS scenery editor
shows by name:

* **`GEDOT_generated_exclusion_building_polygons`:** excludes MSFS's generated buildings from the area of the tiles,
  and from the water around it, so that they don't stand in the photogrammetry. The airport area stays out of it.
* **`GEDOT_generated_exclusion_vegetation_polygons`:** excludes MSFS's vegetation along the shores.
* **`GEDOT_generated_forests_vegetation_polygons`** and **`GEDOT_generated_woods_vegetation_polygons`** (optional): one
  polygon per OpenStreetMap forest or wood. They have no effect at first (MSFS's default forest): their vegetation can
  be set one by one in the scenery editor.

Outlines that cross themselves are repaired before they are written. The ground itself is shaped by the height data of
[step 5](5-height-data.md): this step no longer creates terraform polygons, and removes those of older runs.

## Settings (OPENSTREETMAP section)

| Setting | Default | Effect |
|---|---|---|
| **Push down the water instead of cutting it** | on | [Step 4](4-trim.md) pushes the Google Earth water under the MSFS water instead of cutting it out (no holes along the shores). The water is always excluded (*Exclude water 3d data*). |
| **Smooth the beaches** | off | Step 4 smooths the sand of the beaches (OpenStreetMap `natural=beach`), which the photogrammetry makes spiky. |
| **Forests vegetation polygons**, **Woods vegetation polygons** | off | Create the vegetation polygons above, for the scenery editor. |
| **Exclude forests 3d data**, **Exclude woods 3d data** | off | Step 4 cuts the forests (OpenStreetMap `landuse=forest` and `natural=forest`) or the woods (`natural=wood`) out of the tiles, so that MSFS's trees show there instead. |
| **Exclude other ground 3d data** | off | The same for farmland, vineyards, allotments, meadows and orchards. |
| **Exclude nature reserves 3d data**, **Exclude parks 3d data** | off | The same for nature reserves and parks. |
| **Building margin** | 8 m | The margin kept around a building inside excluded ground (e.g. a house in an excluded forest). Google Earth's buildings are larger than the OpenStreetMap footprints. |
| **Keep the roads and bridges through the excluded ground** | on | The roads and bridges crossing the excluded ground stay in the tiles. |
| **Keep the height data of the construction areas in the excluded ground** | on | Step 5 keeps the ground of the construction areas from the tiles. |
| **Airport city** | empty | The city whose airport lies in the scenery (found as "airport, *city*"). Its area keeps the sim's airport. |
| **Force openStreetMap data download** | off | See above. |

Excluding ground can leave artifacts where Google Earth's trees overhang the OpenStreetMap areas (cut trees), and
buildings missing from OpenStreetMap are cut with the ground around them.
