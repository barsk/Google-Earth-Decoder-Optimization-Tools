# Workflow

A scenery from the downloaded tiles to the Community folder. Each step is an entry of the *Google Earth Decoder
Optimization Tools* menu. Its window shows the settings of the step in sections (left), a description, and the button
that runs it. The work runs in background Blender processes: the console window shows the progress, and Blender stays
busy until the step is over.

## 1. Create the project

1. Run [step 1, Initialize](steps/1-initialize.md): choose the parent folder, the project name and the author. The
   project folder is `<parent folder>\<Name>`.
2. Copy the `modelLib` and `scene` folders of the tiles' download (tool not part of this repo) into the project's `PackageSources` folder. GEDOT
   renames `modelLib` to `<name>-modelLib` the next time it opens the project. GEDOT for MS2024 expects **LOD 17-19** to be downloaded.


Keep the paths free of characters outside ASCII (å, ä, ö, é...): the MSFS 2024 package builder crashes on them.

## 2. Prepare the tiles

3. [Step 2, Optimize](steps/2-optimize.md) places the tiles exactly and packs their textures. Previously an extra addon was needed fro texture packing, this is now built-in.
4. Optional: [Landmarks](steps/landmarks.md). The first run writes `landmarks.csv` with suggested buildings: review it
   (which buildings keep more detail, which become points of interest), then run it again. Define all the landmarks
   before that second run: the tile LODs it removes can't be used afterwards.
5. [Step 2a, Colour correction](steps/2a-colour-correction.md): *Show the tiles with the colours live*, *Auto*, adjust,
   *Run*.
6. [Step 2b, Shadow lightening](steps/2b-shadow-lightening.md).

*View the tiles in Blender* shows the tiles with their current textures, to judge the colours and the shadows.

## 3. Fit the tiles into MSFS

7. [Step 3, Polygons](steps/3-polygons.md): the OpenStreetMap settings (what to exclude, the airport) are set here and
   used by steps 4 and 5.
8. [Step 4, Trim](steps/4-trim.md).
9. [Step 5, Height data](steps/5-height-data.md).
10. [Step 6, Finalize](steps/6-finalize.md).
11. [Step 7, Colliders](steps/7-colliders.md).

## 4. Build and test

12. [Build](steps/build.md) the package with the MSFS 2024 SDK (devmode, the command line, or the steps' *Build package
    enabled* option), while the sim is closed.
13. Copy or link the built package (`<project>\Packages\<package>`) into the Community folder, and start the sim.
    Test points of interest from the Community folder: they don't show when the package is loaded in devmode.

## The project folder

```
<Name>\
  <Name>.xml                       the project file (built with the SDK)
  PackageDefinitions\              the package definition and its ContentInfo
  PackageSources\
    <name>-modelLib\               the tiles: <tile>.xml, <tile>_LODnn.gltf/.bin, texture\
    scene\objects.xml              the scenery objects, polygons and height maps
  <name>.ini                       the settings of the project
  landmarks.csv                    the landmarks and points of interest
  osm\, shp\, xml\                 OpenStreetMap data and intermediate files of steps 3 to 5
  backup\                          see below
  shadow_lightening.txt            the report of step 2b
  color_correction.txt             the settings and measurements of step 2a
  Packages\                        the built package
```

## Reruns and backups

* **Steps 2a and 2b** can run again at any time with other settings: they start from the original textures, kept in
  `backup\colors` and `backup\shadow_lightening`. Run 2b again after 2a.
* **Step 4** keeps the tiles as they were before its first run in `backup\cleanup_3d_data`, and each rerun starts from
  there. Steps 2a and 2b update that backup's textures too.
* **Steps 5 to 7** can run again on a finished project, e.g. after changing a water or terrain setting.
* **Points of interest or their names** changed in `landmarks.csv`: run step 6 again, then build.
* **Landmarks** already upgraded are skipped by later runs. New landmarks can only use the LODs still in the tiles.
* The **Backup enabled** option (BACKUP section) also copies the project files before each step. It is off for new
  projects.

## Large sceneries

* **Parallel tasks:** set *Number of parallel Blender tasks* (PROJECT section) up to the number of logical processors.
  Step 2b needs up to about 4.5 GB of memory per task on the most detailed LODs and limits its tasks to the free memory.
* **Overpass:** a scenery of a whole city makes many OpenStreetMap queries. A
  [local Overpass server](installation/openstreetmap-server.md) avoids being blocked by the public one.
* **Splitting:** a big area can be made of several projects (e.g. one per octree cell, all in the same parent folder)
  built into one package, or merged with *Merge an existing MSFS scenery project into another one* (see
  [Other tools](tools.md)). Step 5 blends the terrain into the tiles at the outer border of each project. To blend only
  the outer border of the whole scenery, put a `scenery_tiles.txt` file in the parent folder, with the names of all
  the tiles of the scenery, one per line.
