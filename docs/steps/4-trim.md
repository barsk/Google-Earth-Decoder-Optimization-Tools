# Step 4: Trim the Google Earth tiles

Trims the 3D data of the tiles: the overlaps between nodes, the excluded ground and the water. It uses the OpenStreetMap
data and settings of [step 3](3-polygons.md).

## What it does

* **Overlaps.** The photogrammetry nodes overlap their neighbours by a few metres with identical surfaces, which
  flicker in the sim (z-fighting), mostly along node and tile borders. Each node is clipped to its octree cell. The
  ground duplicated between the lower and upper octants of a level is removed too.
* **Excluded ground.** The ground excluded in step 3 (forests, woods, other ground, nature reserves, parks) is cut out,
  except the buildings with their margin and, if set, the roads and bridges crossing it.
* **Water.** The Google Earth water surface is noisy and would poke through the MSFS water. It is pushed down below the
  water level of each water body (*Push down the water instead of cutting it*), with a ramp from the shore, so that the
  shores keep no holes. Near bridges and buildings, only the water surface itself is pushed down. Streams running down
  slopes get local levels instead of one level per water body. The tiles covering only water are removed from the
  project and the scene.
* **Beaches** (optional, *Smooth the beaches*): the spiky photogrammetry of the sand is smoothed.

The normals of the tiles are kept through all these edits, so that the lighting doesn't change.

## Settings

* **OPENSTREETMAP:** the settings of step 3 are shown for information. *Process all the tiles*: if unticked, only the
  tiles not trimmed yet are processed.
* **PROJECT:** the number of parallel Blender tasks.

## Backup and reruns

The first run copies the tiles as they are to `backup\cleanup_3d_data`. Each rerun starts from that copy, so the step
can run again after changing the OpenStreetMap settings. Steps 2a and 2b keep the textures of that copy up to date. On a
finished project, the colliders of [step 7](7-colliders.md) are made again.

Buildings that OpenStreetMap doesn't know are cut out with the excluded ground around them.
