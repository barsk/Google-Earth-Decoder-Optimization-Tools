# Prerequisites

## Software

* **[Blender 3.5](https://www.blender.org/download/releases/3-5/)**. The addon runs its heavy work in background
  Blender processes, several at a time.
* **Microsoft Flight Simulator 2024** and the **MSFS 2024 SDK**, for the package builder (`fspackagetool.exe`, in
  `<SDK>\Tools\bin`). The sim must not be running while a package is built.
* **Windows**, like the sim. The addon uses Windows paths and tools.

## Tiles

GEDOT works on Google Earth photogrammetry tiles saved as glTF, in the layout of an Earth2MSFS download:

```
modelLib\<tile>_LOD00.gltf, <tile>_LOD01.gltf, ...   one glTF per tile and LOD, with its .bin and its textures
modelLib\<tile>.xml                                  the model definition of the tile (its LODs)
scene\objects.xml                                    the scenery objects (one per tile)
```

* A tile is an octree node of Google's globe, named by its octree path (e.g. `30606160516243707`, level 17). Its LODs
  hold the nodes of the more detailed levels, as glTF nodes named after their octree paths, so that GEDOT can place
  them exactly.
* Typical sceneries use tiles of level 17 with LODs down to level 19 or 20.
* Older tiles without these node names (e.g. from the Google Earth Decoder tool) are still placed by their bounding
  box, the old way, with gaps between the tiles.

Using Google's 3D tiles is subject to Google's terms. Make sure you have the right to use the tiles you process.

## Network services

* **Overpass API** (OpenStreetMap data), for steps 3 to 5 and the landmarks. The default is the public server
  `https://overpass-api.de/api`. Large sceneries can hit its limits: a local Overpass server (e.g. the
  `wiktorn/overpass-api` Docker image with an extract of your country) avoids them. Set its address in the addon
  preferences.
* **OpenStreetMap API** (the outlines of the landmark buildings) and **Nominatim** (the geocode tools and the airport
  city). Light use, the public servers are fine.
* **Wikidata** (the notability of the landmark candidates, by their Wikipedia articles).
* **Python packages and data**, downloaded once on first use: see [Installation](installation.md).

## Optional

* **A tile downloader**, only to fetch the more detailed level of the landmarks: see
  [The optional tile downloader](../tile-downloader.md).
* **Compressonator CLI**, only for MSFS 2020 packages ([step 8](../steps/build.md#step-8-compress-the-built-package-msfs-2020-only)).
  MSFS 2024 compresses the textures itself.
