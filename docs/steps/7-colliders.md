# Step 7: Add a collider for each tile of the project

Moves the collision detection and the road traffic of each tile into one light collider.

Without colliders, the collision and road tags are on every LOD of the tiles, so the sim tests the detailed meshes. This
step removes those tags from the LODs and adds an invisible collider per tile, made from its least detailed LOD.

## Settings

* **Add the collider as the lower LOD for each tile** (PROJECT section, off by default): the collider becomes the last
  LOD of the tile, so that the tile disappears when it covers less than 1 % of the screen.

## Removing the colliders

*Other tools > Remove the colliders for each tile of the project* removes them and puts the road and collision tags
back on the LODs.

A rerun of [step 4](4-trim.md) on a finished project makes the colliders again.
