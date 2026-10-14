# Step 2: Optimize an existing MSFS scenery project

Prepares the downloaded tiles for MSFS: places them, packs their textures and sets their LODs.

## What it does

* **Places each tile exactly.** The download writes all its tiles in one frame, the tangent plane of Google's globe at
  a reference point. GEDOT finds that frame from the names of the nodes (their octree paths give the cell each node
  belongs to) and places each tile in the WGS 84 frame of the project, to within about a centimetre. The frames are
  saved in `tiles_placement.json`, in the project folder. Tiles whose nodes have no octree names (older downloads) are
  placed by their bounding box, the old way.
* **Packs the textures** of each tile LOD into a single texture, PNG or JPEG (*Output texture format*). Fewer files load
  faster and stutter less in the sim.
* **Sets the LOD min sizes** of the tiles (the LODS section, see below).
* **Prepares the models for MSFS:** non-metallic materials (a metallic factor of 1 renders the tiles far too dark), the
  MSFS extensions for collisions and road traffic, and for MSFS 2024 the texture configuration files (`.png.xml`), which
  the package builder needs to convert the textures.

The LODs of a tile are handled in one Blender process, several tiles at a time (*Number of parallel Blender tasks*).

## Settings

* **PROJECT:** *Output texture format* (PNG by default), the number of parallel tasks, and *Show the tiles in Blender
  after steps 2 and 2b* with the LOD to show.
* **TILE:** *Latitude correction*, *Longitude correction*, only for tiles placed the old way.
* **LODS:** the *min size* of each LOD: the share of the screen below which MSFS switches to the next, less detailed LOD.
  Starting from LOD 0, MSFS shows the first LOD whose min size is smaller than the model's size on the screen. The
  default values `0, 15, 50, 70, 80, 90, 100` go from the least to the most detailed LOD.
* **AUTOMATIC_BUILD**, **BACKUP:** see [Build](build.md) and [Settings](../settings.md).
