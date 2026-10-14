# Settings

Each step window shows the settings of the step in sections. They are saved in the settings file of the project
(*Save settings*, and automatically before a step runs), and can be edited there directly (*Open settings file*).

* **`GEDOT.ini`** (addon folder): the global settings: the selected project, the number of parallel tasks, the Overpass
  address.
* **`<name>.ini`** (project folder): the settings of the project, created from the template
  `resource\config\project_settings.ini`.
* **Addon preferences:** the tools and services of the computer, see [Installation](installation/installation.md#addon-preferences).

The sections of the project's ini file:

| Section | Settings | Used by |
|---|---|---|
| `PROJECT` | `output_texture_format` (png or jpg), `collider_as_lower_lod` | [2](steps/2-optimize.md), [7](steps/7-colliders.md) |
| `TILE` | `lat_correction`, `lon_correction` | tiles placed the old way |
| `LODS` | `target_min_size_values`: the min size of each LOD, from the least to the most detailed | [2](steps/2-optimize.md), the landmarks |
| `OPENSTREETMAP` | the exclusions, the water and beach options, the building margin, the airport city, the vegetation polygons, `high_precision` | [3](steps/3-polygons.md), [4](steps/4-trim.md), [5](steps/5-height-data.md) |
| `HEIGHT_MAPS` | `height_adjustment` (MSFS terrain offset), `ground_filter_size`, `blend_outer_edges`, `flat_water_level` | [5](steps/5-height-data.md) |
| `GEOCODE` | `geocode`, `geocode_margin`, `preserve_roads`, `preserve_buildings`, `landmark_type`, `landmark_offset`, `add_lights` | the geocode tools, the landmarks (margin) |
| `LANDMARKS` | `tiles_max_lod_level` (19) | [the landmarks](steps/landmarks.md) |
| `TEXTURES` | the colours of the tiles' download (`brightness`, `contrast`, `saturation`, `hue`, `red_level`, `green_level`, `blue_level`), `resize_ratio` | the landmarks' download, *Resize the textures* |
| `COLOR_CORRECTION` | haze removal and colour, temperature, tint, brightness, contrast, saturation | [2a](steps/2a-colour-correction.md) |
| `SHADOW_LIGHTENING` | `wall_gain_cap`, `wall_color`, `vegetation_strength`, `shadow_strength`, `shadow_color`, `shadow_gain_cap`, `shadow_vegetation_strength`, `sun_candidates` | [2b](steps/2b-shadow-lightening.md) |
| `VIEW` | the tiles and the LOD shown in Blender, `view_after_steps` | *View the tiles*, 2a, 2b |
| `ALTITUDE_ADJUSTMENT` | `altitude_adjustment` | *Adjusts the altitude of the whole scenery* |
| `MERGE` | the project to merge | *Merge an existing MSFS scenery project* |
| `AUTOMATIC_BUILD` | `build_package_enabled` | [Build](steps/build.md) |
| `BACKUP` | `backup_enabled`: copy the project files before each step | every step |

The percent sliders of steps 2a and 2b are stored as factors (e.g. 60 % as 0.6). The `VIEW` and `COLOR_CORRECTION`
sections are added when they are first used.

New projects start with no ground exclusions, no beach smoothing, and the backup and the build off.
