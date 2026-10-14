# Other tools

The menu entries besides the numbered steps.

## View the tiles in Blender (after 2 / 2b)

Shows the tiles of the project in Blender's 3D view with their current textures, flat lit, north up: the colours of the
download after step 2, the shadow lightening after step 2b. *Tiles* limits them (tile names or their beginnings,
separated by commas; empty = all), *LOD shown* chooses the LOD. Every tile shown is imported, so keep the area small.
The tiles shown are replaced at each display. Steps 2 and 2b can also show them when they are done (*Show the tiles in
Blender after steps 2 and 2b*).

## (Optional) Merge an existing MSFS scenery project into another one

Merges the tiles (and colliders) of another project into the selected one. In the MERGE section, select the project to
merge into the one of the PROJECT section.

## Geocode tools

A geocode is a place name as OpenStreetMap's Nominatim knows it, e.g. "Buckingham Palace, London", or an OpenStreetMap
id (e.g. `5208404`).

* **Create MSFS landmark from geocode:** a landmark location (type POI or City, with a height offset) at the geocode,
  optionally with lights around it. For the buildings of `landmarks.csv`, step 6 writes the points of interest itself.
* **Add lights all around a geocode:** lights around the outline of the geocode (the type of light in the GEOCODE
  section).
* **Remove a building from the Google Earth 3d data:** cuts the geocode's outline, enlarged by the *Geocode margin*, out
  of the tiles, optionally preserving the roads and the buildings around it.
* **Isolate a building from the Google Earth 3d data:** copies the parts of the tiles inside the geocode's outline,
  enlarged by the margin, into separate objects. The tiles stay as they are.
* **Upgrade the landmarks of the scenery:** see [Landmarks](steps/landmarks.md).

## Other tools

* **Update LOD min size values for each tile of the project:** applies the min sizes of the LODS section to every tile
  (see [step 2](steps/2-optimize.md#settings)).
* **Remove the colliders for each tile of the project:** see [step 7](steps/7-colliders.md).
* **Adjusts the altitude of the whole scenery:** moves the tiles, objects, colliders, landmarks and height maps up or
  down by the *altitude adjustment* (ALTITUDE_ADJUSTMENT section).
* **Update the position of the MSFS scenery tiles:** computes the positions of tiles placed the old way (by their
  bounding box), with the latitude and longitude corrections of the TILE section. Not needed for tiles placed exactly by
  step 2.
* **Fix lightning issues on tiles at dawn or dusk:** adds the `ASOBO_material_fake_terrain` extension to the LODs of the
  tiles. A tool of the original GEDOT, kept as it was.
* **Resize the textures of the tiles of the scenery:** scales all the textures by the *resize ratio* (TEXTURES section,
  0.5 by default), e.g. to make a lighter package.
