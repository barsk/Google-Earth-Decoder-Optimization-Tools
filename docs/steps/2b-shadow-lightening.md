# Step 2b: Shadow lightening

Lightens the shadows baked into the textures. Run it after step 2a; steps 4 to 7 keep its result.

The photos were taken in sunshine: walls facing away from the sun are dark, and buildings and trees cast dark shadows
on the ground. MSFS then lights the tiles again with its own sun, at any time of day, so the photo's shadows look wrong,
especially when the sim's sun comes from another side. This step brightens them, with the 3D geometry of the tiles as
its guide.

## What it does

1. **The sun of the capture.** For each tile it estimates the sun's direction from the cast shadows in the textures,
   or takes the directions given in *Sun directions*.
2. **Shaded sides** (part 1). The walls, roofs and trees facing away from that sun are brightened up to their lit side,
   by a fit of brightness against the facing measured on the tile's walls. The colour shift of the shaded side (lit only
   by the bluish sky) is partly fixed. The result is never brighter than the sunlit surfaces of the same kind around it
   (walls against walls), which keeps lumpy meshes (silos, tanks, tree crowns) from turning yellow.
3. **Cast shadows** (part 2). The shadows of the tile and its neighbours are predicted by casting rays towards the sun
   through the 3D geometry, landmark objects included, then confirmed by the darkness of the photo against the lit
   surfaces around. They are lifted towards that lit level by a lit/shadow ratio measured on the tile, with part of
   their bluish colour shift removed. The edges of the shadows are handled texel by texel, so no dark or light outline is
   left around them.
4. Both corrections are applied to all the LODs of the tile, with the fit of its most detailed LOD, so that the LODs
   match. A landmark object uses the fit of its tile.

The report, with the estimated suns and the fits of each tile, is written to `shadow_lightening.txt` in the project
folder.

## Settings

The SHADOW_LIGHTENING section, as percent sliders (hover for the details):

| Setting | Default | Effect |
|---|---|---|
| **Shaded side: max boost** | 300 % | The most a shaded side is brightened (300 % = up to 3 times). |
| **Shaded side: color fix** | 50 % | The share of the shaded side's colour shift that is fixed: 0 % = brightness only (stays bluish), 100 % = the full shift (tends to orange). |
| **Shaded side: vegetation** | 90 % | The share of the correction applied to trees and other vegetation. |
| **Cast shadows: strength** | 60 % | How much the cast shadows are lifted: 100 % = up to the lit surface around them. Lower keeps some shadow and gives fewer artifacts. |
| **Cast shadows: color fix** | 50 % | The share of the shadows' bluish colour shift that is removed (100 % can turn yellowish). |
| **Cast shadows: max boost** | 600 % | The most a cast shadow is brightened, before the strength is applied. Shadows of a sunny capture can be 10 to 20 times darker than the lit ground. |
| **Cast shadows: vegetation** | 50 % | The share of the cast shadow correction applied to vegetation (shadows of trees on trees). |
| **Sun directions** | empty | The sun directions of the capture as azimuth/elevation in degrees, separated by commas (e.g. `168/34, 150/40`). Empty: estimated from the tiles. |

Strong settings make the lightened shadows look flat and blocky: the dark parts of an 8-bit texture hold few levels,
and multiplying them several times makes the steps visible.

## Reruns and memory

* The original textures are kept in `backup\shadow_lightening`: the step can run again with other settings, always from
  the originals, so the corrections never stack.
* A task on the most detailed LOD of a tile needs up to about 4.5 GB of memory. The number of tasks is limited by the
  free memory, and the tiles whose task failed are retried one at a time.
* *View the tiles in Blender* (or *Show the tiles in Blender after steps 2 and 2b*) shows the result.
