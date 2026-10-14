# Step 5: Generate height data based on Google Earth tiles

Shapes the MSFS terrain to the ground of the tiles, with height maps written to the scene. Without it, the MSFS terrain
shows through the tiles in some places and leaves them floating in others. It uses the OpenStreetMap data of
[step 3](3-polygons.md).

## What it does

* **The ground of the tiles.** In high precision mode (the default), the heights come from the ground seen from above
  on the most detailed LODs. A **ground filter** removes the buildings and trees, which would otherwise raise the terrain
  into mounds around them.
* **Under the buildings**, the ground is interpolated from the ground around them.
* **Water.** Each water body gets one flat level at the Google Earth waterline (*Flat water level*), since the MSFS water
  surface follows the terrain. Streams running down slopes get local levels instead. The shores are blended into the
  tiles' ground.
* **Excluded ground** (cut-out forests...): the terrain follows an estimated floor under the trees, from the ground at
  the edge of the cut and in the gaps between trees, instead of the treetops. The ground kept next to it (a house in a
  forest) meets its edge.
* **Outer edges.** On the outer border of the scenery, the terrain is raised to the ground of the tiles, so that there
  is no step between the tiles and the MSFS terrain.

The result is set slightly below the ground of the tiles (*MSFS terrain offset*), so that the terrain doesn't poke
through.

## Settings (OPENSTREETMAP section)

| Setting | Default | Effect |
|---|---|---|
| **MSFS terrain offset (m)** | -1 | The height of the MSFS terrain against the ground of the tiles, 0 or below. More negative if the terrain shows through the tiles, closer to 0 if gaps appear at the edges. |
| **Ground filter size** (m) | 40 | The width of the filter removing the buildings and trees from the heights. 0 turns it off. |
| **Blend the outer edges of the scenery** | on | See above. For a scenery made of several projects, see [Workflow](../workflow.md#large-sceneries). |
| **Flat water level** | on | One flat level per water body (needs high precision). |
| **High precision height data generation** | on | The heights from the most detailed LODs. Off: from the coarsest LODs, smoothed into a nearly flat plane. |

Step 5's log prints the level chosen for each water body, and the spread of its heights used to tell sloped streams
from level water.
