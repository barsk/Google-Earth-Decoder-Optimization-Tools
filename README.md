# GEDOT for MSFS 2024

A Blender addon that turns Google Earth photogrammetry tiles into an optimized scenery package for **Microsoft Flight
Simulator 2024**: tiles placed in their exact position, colours and baked shadows corrected, the overlaps and the water
trimmed, the terrain matched to the tiles, landmark buildings kept in more detail, points of interest, and the MSFS
package files written.

## Status of this fork

This is an independent fork of [Google-Earth-Decoder-Optimization-Tools](https://github.com/Thalixte/Google-Earth-Decoder-Optimization-Tools)
(GEDOT) by Thalixte. Thanks to Thalixte for the original addon, which this fork builds on.

* **Targets MSFS 2024 and Blender 3.5.** The MSFS 2020 code paths are still there (the *Target simulator* addon
  preference), but are no longer tested.
* **Lives its own life.** Since the fork, the processing has been rewritten to a large degree (more than 100 commits),
  so it is not meant to be merged back upstream.
* **Licence:** GNU General Public License, version 2 or later, like the original: the licence text is in
  [LICENSE](LICENSE), the "or later" in the headers of the source files.

## What it does

The addon adds a *Google Earth Decoder Optimization Tools* menu to Blender's top bar. A scenery goes through numbered
steps, each with a settings window:

| Step | Menu entry | Result |
|---|---|---|
| 1 | Initialize a new MSFS scenery project | The MSFS 2024 project structure (project, package definition, asset groups). |
| 2 | Optimize an existing MSFS scenery project | The tiles placed exactly, their textures packed per tile LOD (no external addon needed), the LOD sizes set. |
| | Upgrade the landmarks of the scenery | Chosen buildings upgraded to higher detail (e.g. LOD 20) than the tiles; `landmarks.csv` also lists POI (points of interest) that will create markers in sim. |
| 2a | Colour correction | Haze, white balance, brightness, contrast and saturation of the textures, with a live preview. |
| 2b | Shadow lightening | The shadows baked into the downloaded textures is *lightened* to prepare for MSFS own lighting on top that would otherwise create too deep shadows.  |
| 3 | Create the terraform and exclusion polygons | Building and vegetation exclusions, terraform polygons, optional vegetation polygons, from OpenStreetMap. |
| 4 | Trim the Google Earth tiles | Overlaps between nodes removed, excluded ground (forests) cut out, the water pushed under the MSFS water. |
| 5 | Generate height data | The MSFS terrain under the tiles, flat water levels, the floor under cut-out forests. |
| 6 | Finalize the tiles for MSFS | Materials and normals for MSFS, POI markers, unused files removed. |
| 7 | Add a collider for each tile | Collision and road traffic in one light collider per tile. |

Then the package is built with the MSFS 2024 SDK. See [Workflow](docs/workflow.md) for the complete walkthrough.

## Main changes from the original GEDOT

* **MSFS 2024 packaging:** projects in the MSFS 2024 form (`ModelLib` asset group version 1, publishing groups, package
  order hint), texture configuration files (`.png.xml`) so that the builder converts the textures to KTX2,
  non-metallic materials (tiles were rendered too dark), terraforming in the MSFS 2024 form.
* **Exact tile placement:** the tiles are placed in their octree cells from the names of their nodes, in the WGS 84
  frame of the project (the old placement by bounding box with a 1.0045 scale left gaps of up to 1.8 m between tiles).
* **Texture packing** built in (no paid addon), always on.
* **Landmarks:** buildings listed in `landmarks.csv` (suggested from OpenStreetMap and Wikidata) keep a more detailed
  LOD than the tiles. Rows marked as points of interest become MSFS POIs above their roof. The more detailed level can be
  fetched for the landmarks only (optional, see [The optional tile downloader](docs/tile-downloader.md)).
* **Step 2a, colour correction,** with automatic haze and white balance measurement, a grey picker and a live preview.
* **Step 2b, shadow lightening:** the sun direction of the capture is estimated from the shadows, the shaded sides of walls,
  roofs and trees are brightened, and cast shadows are lifted, with the originals kept.
* **OpenStreetMap:** a single Overpass query per step, any Overpass server (e.g. a local one), the settings set once
  in step 3 for steps 3 to 5, exclusions of forests, woods, other ground, nature reserves and parks on their own.
* **Step 4, Trim:** nodes clipped to their octree cells and the ground duplicated between octants removed (no flicker
  between overlapping nodes), the water pushed down under the MSFS water instead of cut (no holes along the shores),
  sloped streams on local levels, beaches smoothed, the tiles covering only water removed.
* **Step 5, height data:** a ground filter keeps buildings and trees out of the terrain, high precision from the most
  detailed LODs, flat water levels at the Google Earth waterline, an estimated floor under cut-out forests, the ground
  under buildings interpolated, the outer edges of the scenery blended into the tiles.
* **Step 6, Finalize:** the normals along the node edges computed again (no dark ramps in the sim), points of interest
  written, broken LODs and unused files removed.
* **Speed:** the Blender tasks run as a pool, the LODs of a tile in one Blender process, and memory-heavy tasks are
  limited by the free memory. Steps 4 and 5 are about three times faster.
* Many fixes: reruns of steps on finished projects, invalid OpenStreetMap geometries, collider handling, panel settings
  saved before each step.
* **Removed:** the Compressonator step (step 8, texture compression of MSFS 2020 packages). The MSFS 2024 package
  builder compresses the textures itself.

## Requirements

* **Blender 3.5**
* **Microsoft Flight Simulator 2024** and its **SDK** (the package builder, `fspackagetool.exe`)
* **Google Earth photogrammetry tiles as glTF**, in the layout of an Earth2MSFS download. Using Google's 3D tiles is
  subject to Google's terms; make sure you have the right to use the tiles you process.
* **Internet access** for OpenStreetMap: an Overpass server, the OpenStreetMap API and Nominatim. The addon installs
  its Python libraries on first use.
* **Recommended:** a [local Overpass server in Docker](docs/installation/openstreetmap-server.md). The public Overpass
  servers throttle or block the many queries of a large scenery.

See [Prerequisites](docs/installation/prerequisites.md) and [Installation](docs/installation/installation.md).

## Documentation

* [Presentation](docs/index.md)
* [Prerequisites](docs/installation/prerequisites.md) and [Installation](docs/installation/installation.md)
* [Workflow](docs/workflow.md)
* The steps: [1 Initialize](docs/steps/1-initialize.md), [2 Optimize](docs/steps/2-optimize.md),
  [Landmarks](docs/steps/landmarks.md), [2a Colour correction](docs/steps/2a-colour-correction.md),
  [2b Shadow lightening](docs/steps/2b-shadow-lightening.md), [3 Polygons](docs/steps/3-polygons.md),
  [4 Trim](docs/steps/4-trim.md), [5 Height data](docs/steps/5-height-data.md), [6 Finalize](docs/steps/6-finalize.md),
  [7 Colliders](docs/steps/7-colliders.md), [Build](docs/steps/build.md)
* [Usage scenarios](docs/scenarios.md): tuning the colours and the shadows, changing landmarks, exclusions or tiles
* [Other tools](docs/tools.md)
* [Settings](docs/settings.md)
* [The optional tile downloader](docs/tile-downloader.md)

The documentation can also be served as a site with [MkDocs](https://www.mkdocs.org/) (`mkdocs.yml`, Material theme).
