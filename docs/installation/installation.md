# Installation

## Install the addon

The addon folder must be named **`Google-Earth-Decoder-Optimization-Tools`** (its preferences are registered under
that name).

**With git** (easiest to update):

1. Clone the repository into Blender's addon folder,
   `%APPDATA%\Blender Foundation\Blender\3.5\scripts\addons\Google-Earth-Decoder-Optimization-Tools`.
   Or clone it anywhere, and make a directory junction with that name in the addon folder pointing to the clone.
2. Start Blender, *Edit > Preferences > Add-ons*, search for *Google Earth Decoder Optimization Tools* and enable it.

**From a ZIP download:**

1. Download the repository as a ZIP. The folder inside is named after the branch (e.g.
   `Google-Earth-Decoder-Optimization-Tools-main`): rename it to `Google-Earth-Decoder-Optimization-Tools` and zip it
   again.
2. In Blender, *Edit > Preferences > Add-ons > Install...*, select the ZIP, then enable the addon.

A *Google Earth Decoder Optimization Tools* menu then appears in Blender's top bar.

Restart Blender after updating the addon files.

## First use: libraries and data

The first time a step needs them, the addon installs into Blender's Python: Pillow, NumPy, GDAL and Fiona (Windows
wheels from the repository set in the preferences), Shapely, pandas, GeoPandas, Rtree, NetworkX, Matplotlib, OSMnx and
PyGeodesy. If that fails, start Blender once as administrator: the libraries go into Blender's own folder.

It also downloads:

* the **BlenderGIS** addon, for the steps that need it;
* the OpenStreetMap **land polygons** shapefile (about 1.3 GB unpacked, into `resource\shapes`), to tell the sea from
  the land.

The console window shows the progress and the result of each check.

## Addon preferences

*Edit > Preferences > Add-ons > Google Earth Decoder Optimization Tools*:

| Preference | Use |
|---|---|
| **Path to the MSFS bin exe that builds the MSFS packages** | The SDK's `fspackagetool.exe` (e.g. `C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe`). Only needed if the steps should build the package themselves (*Build package enabled*). |
| **Target simulator** | *Automatic* (MSFS 2024, unless the builder's path doesn't contain "2024"), *MSFS 2020* or *MSFS 2024*. Decides the form of the project files, the texture configuration files and the package order hint. |
| **Msfs Steam version** | Tick it for the Steam version of the sim: the builder is started with `-forcesteam`. |
| **Uri of the Overpass API** | The OpenStreetMap server for steps 3 to 5 and the landmarks, e.g. `https://overpass-api.de/api`, or a [local server](openstreetmap-server.md) such as `http://localhost:12345/api` (recommended). |
| **Path to the tile downloader** | Optional, see [The optional tile downloader](../tile-downloader.md). |
| **GDAL and FIONA libraries** | The wheel repository and versions used for the first installation (defaults for Blender 3.5's Python 3.10). |
| **BLENDER GIS addon**, **Landmass shapefile** | Where these are downloaded from. |

## GEDOT.ini

`GEDOT.ini`, in the addon folder, keeps the global settings: the selected project (its folder, name and author), the
number of parallel Blender tasks and the Overpass address. Each project has its own settings file, see
[Settings](../settings.md).
