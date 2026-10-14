# The optional tile downloader

GEDOT doesn't download anything from Google itself. Only one feature can use an external command line downloader: the
[landmarks tool](steps/landmarks.md) can fetch the next, more detailed level (e.g. LOD 20) for the landmark buildings
only, when the project was downloaded up to the maximum level of the tiles (e.g. LOD 19).

The downloader is optional. Without it, the landmarks keep the levels that are already in the project: to get LOD 20
landmarks without a downloader, download the whole area up to LOD 20 and let the landmarks tool remove that level from
the other tiles.

## No downloader is published

A tool that downloads Google Earth's 3D tiles like this violates Google's policy for the Google Earth 3D tiles, so it
cannot be published publicly. GEDOT neither includes nor links to one. This page only describes the interface GEDOT
expects from such a tool.

## Configuration

* **Addon preferences**, *Tile downloader (optional)*, *Path to the tile downloader*: the executable.
* Or the environment variable `GEDOT_TILE_DOWNLOADER`, which takes precedence over the preference (for tools that run
  GEDOT's steps from the command line).

When neither is set, or the download fails, the landmarks tool prints a message and goes on with the levels already in
the project.

## Command line

```
<downloader> --rects <file> --min-lod <level> --max-lod <level> --group-level <tile level> --out <folder>
             [--brightness <x>] [--contrast <x>] [--saturation <x>] [--hue <x>] [--red <x>] [--green <x>] [--blue <x>]
```

| Option | Meaning |
|---|---|
| `--rects <file>` | A text file with one rectangle per line: `<lat>,<lon>,<width>,<height>`. The centre in decimal degrees (WGS 84), the width (east-west) and height (north-south) in metres. Anything after `#` is a comment (GEDOT writes the OpenStreetMap id of the landmark there). GEDOT writes one rectangle per landmark: the bounding box of its OpenStreetMap outline, plus 2 m on each side. |
| `--min-lod`, `--max-lod` | The octree level to download. GEDOT passes the same value to both: the level after the most detailed level of the project's tiles (e.g. 20). |
| `--group-level <level>` | The level of the project's tiles (the number of digits of their names, e.g. 17). Each downloaded node goes into the model of its ancestor at that level. |
| `--out <folder>` | The output folder. GEDOT creates it empty (`<project>\landmarks_download`) and removes it afterwards. |
| `--brightness`, `--contrast`, `--saturation`, `--hue`, `--red`, `--green`, `--blue` | Colour corrections of the downloaded textures: the values of the `[TEXTURES]` section of the project, so that the landmarks match the colours of the tiles' download. GEDOT only passes the options that differ from the neutral value (1, and 0 for the hue). |

## What the downloader must do

* Download only the 3D (photogrammetry) nodes of the requested level that intersect at least one of the rectangles, all
  the rectangles in one run.
* Exit with code 0 on success. Any other exit code, or a missing `scene\objects.xml`, counts as a failure. The console
  output is copied into GEDOT's log, in any encoding.

## Output

```
<out>\modelLib\<tile>_LOD00.gltf   with its .bin and its textures
<out>\scene\objects.xml
```

* **One glTF file per tile**, named `<tile>_LOD00.gltf`. `<tile>` is the octree path of the ancestor at the group level
  (digits 0-7), so the same name as the project's tile. Files of tiles that aren't in the project are ignored.
* **One glTF node per downloaded octree node**, named `<octree path>_<n>` (`n` = 0, 1, ... when a node has several
  meshes). GEDOT reads the octree cell of each node from its name (step 4 clips the nodes to their cells).
* **Geometry in metres, all the models in one shared frame:** the tangent plane of Google's globe (a sphere) at a
  reference point, with the axes of MSFS models: +Y up, +Z north, -X east. No scale or rotation on the nodes.
* **Textures** referenced by the glTF with relative URIs (next to it, or in a `texture` subfolder), JPEG or PNG. A
  texture per node is fine: GEDOT packs the textures of each tile LOD.
* **`objects.xml`**: an MSFS scenery objects file. GEDOT reads the `lat`, `lon` and `alt` (metres) of its first
  `SceneryObject` as the reference point of the shared frame. Like the downloads of the tiles, every model is placed at
  that reference point.

This is the layout of an Earth2MSFS download, which GEDOT also uses for the tiles themselves (see
[Prerequisites](installation/prerequisites.md)).
