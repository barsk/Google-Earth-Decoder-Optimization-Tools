# Step 6: Finalize the tiles for MSFS

Finalizes the project before its build.

## What it does

* **Prepares the tiles for MSFS:** non-metallic materials, the MSFS extensions, and the road traffic and collision tags
  (moved to the colliders when the project has them).
* **Computes the normals along the edges of the nodes again.** The normals of a download average the vertical skirts of
  the nodes into the ground along their edges, which shows as dark ramps in the sim, square by square. The normals are
  computed again from the real surfaces.
* **Writes the points of interest** of `landmarks.csv` (the rows with `poi` true) above the top of their building, and
  removes those of rows removed or set to false. See [Landmarks](landmarks.md#points-of-interest).
* **Removes the broken LODs** (a LOD whose file is missing) and the unused glTF, bin and texture files, e.g. of tiles
  removed by hand or by step 4.

Run it again after changing the points of interest, then build.

## Settings

PROJECT, AUTOMATIC_BUILD and BACKUP sections, see [Settings](../settings.md).
