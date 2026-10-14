# Build the package

The package is built with the MSFS 2024 SDK's package builder, into `<project>\Packages\<package>`. Then copy that
folder into the Community folder, or link it there with a directory junction.

## Ways to build

* **MSFS 2024 devmode:** open the project file (`<project>\<Name>.xml`) and use *Build All*. *Build & Export* also
  makes a ZIP for publishing.
* **The command line:**

  ```
  fspackagetool.exe -nopause -outputtoseparateconsole <project>\<Name>.xml -outputdir <project>
  ```

  Add `-forcesteam` for the Steam version, and `-rebuild` to build everything again. `fspackagetool` returns at once:
  the build runs in a sim instance of its own, with its own console, and is over when that instance exits. Without
  `-outputtoseparateconsole` the build fails, and without `-nopause` the instance waits for Enter at the end.
* **At the end of a step:** *Build package enabled* (AUTOMATIC_BUILD section) runs the builder set in the addon
  preferences when the step is done, with `-forcesteam` if *Msfs Steam version* is ticked. It doesn't pass `-nopause`:
  press Enter in the build's console when it is done. It is off for new projects.

## Before and after building

* **Close the sim.** A build starts a sim instance of its own, which clashes with a running sim.
* **Keep the paths free of characters outside ASCII** (å, ä, ö, é...). The MSFS 2024 builder crashes on them at once,
  before building anything (the crash report says there is no mapping for a Unicode character).
* **Don't end a build instance in the Task Manager.** Steam then thinks the game is still running and refuses to start
  it again until it is stopped from the Steam library. If a build seems stuck, stop it from the Steam library.
* **Check the textures.** Magenta tiles in the sim mean that textures weren't converted: the package should hold as many
  `.KTX2` files in `scenery/global/scenery/texture` as there are PNG textures in the modelLib. The texture configuration
  files written by steps 2 and 4 make the builder convert them.
* **Test points of interest from the Community folder,** not with the package loaded in devmode.

The builder compresses the textures itself (KTX2). The original GEDOT's step 8, which compressed the DDS textures of
MSFS 2020 packages with Compressonator, has been removed.
