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
* Download the tiles at level 17 with their LODs down to level 19. Level 20 is meant for the landmark buildings only:
  either download 17–20 and let the [landmarks tool](../steps/landmarks.md) remove level 20 from the other tiles, or
  download 17–19 and fetch level 20 for the landmarks with the [optional tile downloader](../tile-downloader.md).
* Older tiles without these node names (e.g. from the Google Earth Decoder tool) are still placed by their bounding
  box, the old way, with gaps between the tiles.

Using Google's 3D tiles is subject to Google's terms. Make sure you have the right to use the tiles you process.

## Network services

* **Overpass API** (OpenStreetMap data), for steps 3 to 5 and the landmarks. The default is the public server
  `https://overpass-api.de/api`, which throttles or blocks large sceneries. **Recommended:** a local Overpass server in
  Docker with an extract of your country, see [Local OpenStreetMap server](openstreetmap-server.md).
* **OpenStreetMap API** (the outlines of the landmark buildings) and **Nominatim** (the geocode tools and the airport
  city). Light use, the public servers are fine.
* **Wikidata** (the notability of the landmark candidates, by their Wikipedia articles).
* **Python packages and data**, downloaded once on first use: see [Installation](installation.md).

## Optional

* **A tile downloader**, only to fetch the more detailed level of the landmarks: see
  [The optional tile downloader](../tile-downloader.md).

No texture compression tool is needed: the MSFS 2024 package builder compresses the textures itself (KTX2).
