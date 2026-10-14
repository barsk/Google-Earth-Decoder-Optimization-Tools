# Step 1: Initialize a new MSFS scenery project

Creates the structure of an MSFS scenery project.

## Settings

* **Path of the project:** the parent folder. The project folder is `<parent folder>\<Name>` (the name with a capital
  first letter).
* **Name of the project to initialize**, **Author of the project:** used in the names of the project file, the
  package definition and the package (`<author>-<name>`).

## Result

* `<Name>.xml`, the project file for the SDK's package builder.
* `PackageDefinitions\<author>-<name>.xml`, the package definition, with its asset groups:
  * `ContentInfo` (the thumbnail);
  * the tiles, `PackageSources\<name>-modelLib\`, as a `ModelLib` asset group, built into `scenery/global/scenery`;
  * the scenery objects, `PackageSources\scene\`, as a `BGL` asset group, built into `scenery/world/scenery`.
* `PackageSources`, with the folders above, and the backup folder.

For MSFS 2024 (the *Target simulator* preference), the files are written in the MSFS 2024 form: the project has its
metadata folder and publishing groups, the `ModelLib` asset group is version 1, and the package order hint is
`CUSTOM_WORLD_SCENERY`. MSFS 2024 devmode opens such a project without asking to convert it.

Then copy the `modelLib` and `scene` folders of the tiles' download into `PackageSources` (GEDOT renames `modelLib`
to `<name>-modelLib`).

Always create the projects with this step. A project created in MSFS 2024 devmode lacks the asset groups of the tiles
and the texture configuration files, and its package comes out empty or with magenta tiles.
