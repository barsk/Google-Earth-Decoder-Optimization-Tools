# GEDOT for MSFS 2024

GEDOT is a Blender addon that turns Google Earth photogrammetry tiles into an optimized scenery package for Microsoft
Flight Simulator 2024.

It is an independent fork of [Google-Earth-Decoder-Optimization-Tools](https://github.com/Thalixte/Google-Earth-Decoder-Optimization-Tools)
by Thalixte, rewritten to a large degree for MSFS 2024 and Blender 3.5. It is not meant to be merged back upstream.

## What a scenery goes through

The raw tiles of a download don't make a good MSFS scenery as they are:

* their textures carry the colours, the haze and the shadows of the moment they were photographed;
* the nodes of the photogrammetry overlap, which flickers in the sim;
* the Google Earth water surface pokes through the MSFS water;
* the MSFS terrain doesn't follow the tiles, so it shows through them, or the tiles float;
* MSFS places its own buildings and trees on top of the photogrammetry.

GEDOT handles these in numbered steps, each one a menu entry with its settings window:

1. **Initialize** the MSFS 2024 project.
2. **Optimize** the tiles: exact placement, packed textures, LOD sizes.
   * **Landmarks** (optional): chosen buildings in more detail than the tiles, and the points of interest.
   * **2a, Colour correction:** haze, white balance and tone of the textures, with a live preview.
   * **2b, Shadow lightening:** the baked-in shadows lightened, since MSFS lights the tiles again.
3. **Polygons:** building and vegetation exclusions and terraform polygons from OpenStreetMap.
4. **Trim:** node overlaps removed, excluded ground cut out, the water pushed under the MSFS water.
5. **Height data:** the MSFS terrain shaped to the ground of the tiles.
6. **Finalize:** the tiles prepared for MSFS, the points of interest written, unused files removed.
7. **Colliders:** collision and road traffic in one light collider per tile.

Then the package is built with the MSFS 2024 SDK.

## Where to start

* [Prerequisites](installation/prerequisites.md): what you need besides the addon.
* [Installation](installation/installation.md): the addon, its Python libraries and its preferences.
* [Workflow](workflow.md): a scenery from the download to the Community folder.
* The pages of the steps, the [other tools](tools.md) and the [settings](settings.md).
