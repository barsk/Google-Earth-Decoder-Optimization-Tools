# Usage scenarios

Common tasks, and the steps to run for each.

## Tuning the colours

Colours are best tuned on a small test project, then applied to the whole scenery.

1. **A test project.** Make a project from a small part of the scenery (a few tiles, with buildings, streets and some
   vegetation) and run steps 1, 2 and the window of step 2a. The landmarks aren't needed for this.
2. **Look at the tiles.** In the 2a window, *Show the tiles with the colours live*. Use *Auto* to measure the haze and
   the white balance: recommended.
3. **Brightness only.** Of brightness, contrast and saturation, change only the brightness. It almost always needs to
   go down, so that the ground of the tiles matches the sim's own terrain around the scenery, and so that MSFS's lighting,
   added on top, doesn't make the lit sides too bright. *Auto* plus a brightness of about 60-80 % usually works best.
   Avoid raising the contrast: it also makes the shadows deeper.
4. **Run 2a**, then *View the tiles in Blender*, and repeat until you are satisfied.
5. **Check in the sim.** MSFS adds its own lighting and processing, so the colours must be judged in the sim. Build the
   test project and load it, either the test project or the package of the whole scenery, never both: disable the other
   package in the sim (*Marketplace*, the Community packages) first. With the test project loaded in devmode, a new
   run of step 2a in Blender shows in the sim (a build in devmode may be needed).
6. **Apply to the scenery.** Copy the colour settings to the other projects (the `[COLOR_CORRECTION]` section of their
   ini file; the haze and white balance can be measured with *Auto* in each project), run step 2a, then step 2b again
   (it works on the corrected textures), and build.

## Tuning the shadow lightening

The default settings are a safe floor: they rarely give artifacts, and most sceneries take stronger values.

1. Start with the default settings, run step 2b, and look at the result with *View the tiles in Blender*.
2. Raise the settings above the defaults step by step (mainly the boosts and the strength), run 2b again (it always
   starts from the original textures), and repeat. The goal is the strongest lightening without unwanted artifacts:
   when they appear, go back a step.
3. Apply the settings to the other projects (the `[SHADOW_LIGHTENING]` section), run 2b there, and build.

The changes can be judged fully in Blender: if they look good there, they look good in MSFS. Signs of settings that are
too strong:

* **Flat, blocky or noisy shadows:** the dark parts of the textures, stretched too far. Lower *Cast shadows: max boost*
  or *strength*.
* **Lifted shadows turning grey-blue, or yellowish:** adjust *Cast shadows: color fix*.
* **Shaded walls turning orange, or brighter than their lit side:** lower *Shaded side: color fix* or *max boost*.
* **Patches on trees and round shapes** (tanks, silos): lower the *vegetation* settings.

## Changing the landmarks and the points of interest

* **The `poi` or `name` columns** of `landmarks.csv`: run [step 6](steps/6-finalize.md) again, then build.
* **New landmarks** (`landmark` set to true): run the landmarks tool again (it only adds the new ones), then steps 2a,
  2b and 3 to 7, then build.
* **Removing a landmark** can't be undone this way: its object stays, and its area stays cut out of the tiles. Make the
  project again from its download.

## Changing the exclusions

The exclusions (forests, woods, other ground, nature reserves, parks) and the other OpenStreetMap settings are set in
step 3. After changing them, run steps 3, 4, 5, 6 and 7, then build. Step 4 starts from its backup of the untrimmed
tiles, so ground that is no longer excluded comes back. Steps 2a and 2b don't need to run again.

## Changing the tiles of a scenery

A project's tiles come from its download: to change its area, download the new area and make a new project. In a
scenery made of several projects, also run step 5 again in the neighbouring projects (the outer edges of their tiles
change), with `scenery_tiles.txt` updated (see [Workflow](workflow.md#large-sceneries)), then build.
