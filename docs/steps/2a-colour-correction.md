# Step 2a: Colour correction

Corrects the colours of the downloaded textures. Run it after step 2 and the landmarks, before step 2b.

Aerial photos carry the light of the moment they were taken: a bluish haze added by the atmosphere, the white balance
of the camera, sometimes a flat or overexposed look. MSFS lights the scenery itself, so neutral textures blend better
with its terrain and its own lighting.

## Usage

1. Open *2a. Colour correction*, then *Show the tiles with the colours live*: the tiles appear in Blender's 3D view
   with the settings applied in real time. Limit them with *Tiles shown* (tile names or their beginnings, separated by
   commas; empty = all) and *LOD shown*. Every tile shown is imported, so keep the area small.
2. *Auto* measures the haze colour and the white balance on the tiles shown.
3. Optionally, *Pick grey* (also in the menu, as *2a. Pick grey*), then click surfaces that should be grey (asphalt,
   concrete, grey roofs): the white balance is set from them.
4. Adjust the sliders and watch the tiles.
5. *Run*: the corrected textures are written for the whole project.

The settings are saved in the `[COLOR_CORRECTION]` section of the project's ini file, the measurements and the settings
used in `color_correction.txt`.

## Settings

| Setting | Effect |
|---|---|
| **Haze removal** (%) and **Haze colour** (levels R, G, B) | Removes the light the atmosphere adds to every pixel. *Auto* measures its colour: the black point of each channel, since nothing in the scene is darker than the haze. |
| **Temperature** (%) | White balance: warmer (more red, less blue) above 0, cooler below. *Auto* makes the grey surfaces grey (6500 K). |
| **Tint** (%) | White balance: magenta above 0, green below. |
| **Brightness**, **Contrast**, **Saturation** (%) | The tone of the textures. |

The haze, the white balance and the brightness are applied in linear light, the way the light mixed in the photo, the
contrast and the saturation in sRGB, as seen.

## Reruns

The original textures are kept in `backup\colors`: the step can run again with other settings at any time, always from
the originals. Textures rewritten by another step (e.g. new landmark objects) are taken as new originals. Run step 2b
again afterwards, since it works on the corrected textures. Step 4's backup gets the corrected textures too.
