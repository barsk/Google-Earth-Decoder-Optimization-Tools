#  #
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#  #
#
#  <pep8 compliant>
import os

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty, IntProperty
from constants import TARGET_MIN_SIZE_VALUE_PROPERTY_PREFIX, PNG_TEXTURE_FORMAT, JPG_TEXTURE_FORMAT, MAX_PHOTOGRAMMETRY_LOD, POI_LANDMARK_FORMAT_TYPE, CITY_LANDMARK_FORMAT_TYPE, LIGHT_WARM_DISPLAY_NAME, LIGHT_COLD_DISPLAY_NAME, LIGHT_WARM_GUID, LIGHT_COLD_GUID, LIGHT_100_BLUE_GUID, LIGHT_500_BLUE_GUID, LIGHT_1000_BLUE_GUID, LIGHT_100_BLUE_DISPLAY_NAME, LIGHT_500_BLUE_DISPLAY_NAME, LIGHT_1000_BLUE_DISPLAY_NAME, LIGHT_100_GREEN_GUID, LIGHT_100_GREEN_DISPLAY_NAME, LIGHT_500_GREEN_GUID, \
    LIGHT_500_GREEN_DISPLAY_NAME, LIGHT_1000_GREEN_GUID, LIGHT_1000_GREEN_DISPLAY_NAME, LIGHT_100_SOFT_GREEN_GUID, LIGHT_100_SOFT_GREEN_DISPLAY_NAME, LIGHT_500_SOFT_GREEN_GUID, LIGHT_500_SOFT_GREEN_DISPLAY_NAME, LIGHT_1000_SOFT_GREEN_GUID, LIGHT_1000_SOFT_GREEN_DISPLAY_NAME, LIGHT_100_WHITE_GUID, LIGHT_100_WHITE_DISPLAY_NAME, LIGHT_500_WHITE_GUID, LIGHT_500_WHITE_DISPLAY_NAME, LIGHT_1000_WHITE_GUID, LIGHT_1000_WHITE_DISPLAY_NAME, LIGHT_100_MINT_GREEN_GUID, LIGHT_100_MINT_GREEN_DISPLAY_NAME, \
    LIGHT_500_MINT_GREEN_GUID, LIGHT_500_MINT_GREEN_DISPLAY_NAME, LIGHT_1000_MINT_GREEN_GUID, LIGHT_1000_MINT_GREEN_DISPLAY_NAME, LIGHT_100_PINK_GUID, LIGHT_100_PINK_DISPLAY_NAME, LIGHT_500_PINK_GUID, LIGHT_500_PINK_DISPLAY_NAME, LIGHT_1000_PINK_GUID, LIGHT_1000_PINK_DISPLAY_NAME, LIGHT_100_RED_GUID, LIGHT_100_RED_DISPLAY_NAME, LIGHT_500_RED_GUID, LIGHT_500_RED_DISPLAY_NAME, LIGHT_1000_RED_GUID, LIGHT_1000_RED_DISPLAY_NAME, LIGHT_100_SKY_BLUE_GUID, LIGHT_100_SKY_BLUE_DISPLAY_NAME, \
    LIGHT_500_SKY_BLUE_GUID, LIGHT_500_SKY_BLUE_DISPLAY_NAME, LIGHT_1000_SKY_BLUE_GUID, LIGHT_1000_SKY_BLUE_DISPLAY_NAME, LIGHT_100_PURPLE_GUID, LIGHT_100_PURPLE_DISPLAY_NAME, LIGHT_500_PURPLE_GUID, LIGHT_500_PURPLE_DISPLAY_NAME, LIGHT_1000_PURPLE_GUID, LIGHT_1000_PURPLE_DISPLAY_NAME, LIGHT_100_YELLOW_GUID, LIGHT_100_YELLOW_DISPLAY_NAME, LIGHT_500_YELLOW_GUID, LIGHT_500_YELLOW_DISPLAY_NAME, LIGHT_1000_YELLOW_GUID, LIGHT_1000_YELLOW_DISPLAY_NAME


def save_float_setting(props, context, name):
    # a float setting of the project ini (2 decimals) saved: a module function, not a method, because the property group used at
    # runtime (updatedSettingsPropertyGroup) is built from the annotations only, so the update functions can't call its methods
    setattr(context.scene.project_settings, name, "{:.2f}".format(float(str(getattr(props, name)))).rstrip("0").rstrip("."))
    context.scene.project_settings.save()


def save_percent_setting(props, context, name):
    # a setting shown in percent in the panel, saved as a factor in the project ini (60 % -> 0.6)
    setattr(context.scene.project_settings, name, "{:.2f}".format(float(str(getattr(props, name))) / 100.0).rstrip("0").rstrip("."))
    context.scene.project_settings.save()


class SettingsPropertyGroup(bpy.types.PropertyGroup):
    def projects_path_updated(self, context):
        context.scene.global_settings.projects_path = self.projects_path_readonly = self.projects_path

    def project_path_updated(self, context):
        if not os.path.isdir(context.scene.global_settings.projects_path):
            context.scene.global_settings.projects_path = str()
        if hasattr(context.scene.global_settings, "project_path"):
            if not os.path.isdir(context.scene.global_settings.project_path):
                context.scene.global_settings.project_path = str()
        if not os.path.isdir(os.path.join(context.scene.global_settings.projects_path, context.scene.global_settings.project_name)):
            context.scene.global_settings.project_name = str()
        if hasattr(context.scene.global_settings, "project_path"):
            if not os.path.isfile(os.path.join(context.scene.global_settings.project_path, context.scene.global_settings.definition_file)):
                context.scene.global_settings.definition_file = str()

        if os.path.isdir(self.project_path):
            context.scene.global_settings.projects_path = self.projects_path = self.projects_path_readonly = os.path.dirname(os.path.dirname(self.project_path)) + os.sep
            context.scene.global_settings.project_path = self.project_path
            context.scene.global_settings.project_name = self.project_name = os.path.relpath(self.project_path, start=self.projects_path)

        if os.path.isfile(os.path.join(self.project_path, self.definition_file)):
            context.scene.global_settings.definition_file = self.definition_file

        self.project_path_readonly = getattr(context.scene.global_settings, "project_path", str())

    def project_name_updated(self, context):
        context.scene.global_settings.project_name = self.project_name
        context.scene.global_settings.project_path = os.path.join(context.scene.global_settings.projects_path, context.scene.global_settings.project_name)

    def project_path_to_merge_updated(self, context):
        if context.scene.project_settings is None:
            return

        if not os.path.isdir(context.scene.project_settings.project_path_to_merge):
            context.scene.project_settings.project_path_to_merge = str()

        if not os.path.isfile(os.path.join(context.scene.project_settings.project_path_to_merge, context.scene.project_settings.definition_file_to_merge)):
            context.scene.project_settings.definition_file_to_merge = str()

        if os.path.isdir(self.project_path_to_merge):
            context.scene.project_settings.project_path_to_merge = os.path.dirname(self.project_path_to_merge)

        if os.path.isfile(os.path.join(self.project_path_to_merge, self.definition_file_to_merge)):
            context.scene.project_settings.definition_file_to_merge = self.definition_file_to_merge

        self.project_path_to_merge_readonly = context.scene.project_settings.project_path_to_merge
        context.scene.project_settings.save()

    def author_name_updated(self, context):
        context.scene.global_settings.author_name = self.author_name

    def nb_parallel_blender_tasks_updated(self, context):
        context.scene.global_settings.nb_parallel_blender_tasks = int(self.nb_parallel_blender_tasks)

    def output_texture_format_updated(self, context):
        context.scene.project_settings.output_texture_format = self.output_texture_format
        context.scene.project_settings.save()

    def collider_as_lower_lod_updated(self, context):
        context.scene.project_settings.collider_as_lower_lod = self.collider_as_lower_lod
        context.scene.project_settings.save()

    def backup_enabled_updated(self, context):
        context.scene.project_settings.backup_enabled = self.backup_enabled
        context.scene.project_settings.save()

    def lat_correction_updated(self, context):
        context.scene.project_settings.lat_correction = "{:.9f}".format(float(str(self.lat_correction))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def lon_correction_updated(self, context):
        context.scene.project_settings.lon_correction = "{:.9f}".format(float(str(self.lon_correction))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def target_min_size_value_updated(self, context):
        prev_value = -1

        for idx, min_size_value in enumerate(bpy.types.Scene.project_settings.target_min_size_values):
            reverse_idx = (len(bpy.types.Scene.project_settings.target_min_size_values) - 1) - idx
            cur_lod = MAX_PHOTOGRAMMETRY_LOD - reverse_idx
            name = TARGET_MIN_SIZE_VALUE_PROPERTY_PREFIX + str(cur_lod)
            cur_value = int(eval("self." + name))
            cur_value = prev_value if cur_value < prev_value else cur_value
            self[name] = cur_value
            context.scene.project_settings.target_min_size_values[idx] = str(cur_value)
            prev_value = int(context.scene.project_settings.target_min_size_values[idx])

        context.scene.project_settings.save()

    def airport_city_updated(self, context):
        context.scene.project_settings.airport_city = self.airport_city
        context.scene.project_settings.save()

    def isolate_3d_data_updated(self, context):
        context.scene.project_settings.isolate_3d_data = (self.isolate_3d_data == "GOOD")
        context.scene.project_settings.save()

    def exclude_ground_updated(self, context):
        context.scene.project_settings.exclude_ground = self.exclude_ground
        context.scene.project_settings.save()

    def exclude_forests_updated(self, context):
        context.scene.project_settings.exclude_forests = self.exclude_forests
        context.scene.project_settings.save()

    def exclude_woods_updated(self, context):
        context.scene.project_settings.exclude_woods = self.exclude_woods
        context.scene.project_settings.save()

    def exclude_nature_reserves_updated(self, context):
        context.scene.project_settings.exclude_nature_reserves = self.exclude_nature_reserves
        context.scene.project_settings.save()

    def exclude_parks_updated(self, context):
        context.scene.project_settings.exclude_parks = self.exclude_parks
        context.scene.project_settings.save()

    def keep_roads_updated(self, context):
        context.scene.project_settings.keep_roads = self.keep_roads
        context.scene.project_settings.save()

    def keep_constructions_updated(self, context):
        context.scene.project_settings.keep_constructions = self.keep_constructions
        context.scene.project_settings.save()

    def keep_residential_updated(self, context):
        context.scene.project_settings.keep_residential = self.keep_residential
        context.scene.project_settings.save()

    def force_osm_data_download_updated(self, context):
        context.scene.project_settings.force_osm_data_download = self.force_osm_data_download
        context.scene.project_settings.save()

    def process_all_updated(self, context):
        context.scene.project_settings.process_all = self.process_all
        context.scene.project_settings.save()

    def flat_water_level_updated(self, context):
        context.scene.project_settings.flat_water_level = self.flat_water_level
        context.scene.project_settings.save()

    def smooth_beaches_updated(self, context):
        context.scene.project_settings.smooth_beaches = self.smooth_beaches
        context.scene.project_settings.save()

    def push_down_water_updated(self, context):
        context.scene.project_settings.push_down_water = self.push_down_water
        context.scene.project_settings.save()

    def blend_outer_edges_updated(self, context):
        context.scene.project_settings.blend_outer_edges = self.blend_outer_edges
        context.scene.project_settings.save()

    def high_precision_updated(self, context):
        context.scene.project_settings.high_precision = self.high_precision
        context.scene.project_settings.save()

    def ground_filter_size_updated(self, context):
        context.scene.project_settings.ground_filter_size = "{:.1f}".format(float(str(self.ground_filter_size))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def height_adjustment_updated(self, context):
        context.scene.project_settings.height_adjustment = "{:.1f}".format(float(str(self.height_adjustment))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def geocode_updated(self, context):
        context.scene.project_settings.geocode = self.geocode
        context.scene.project_settings.save()

    def geocode_margin_updated(self, context):
        context.scene.project_settings.geocode_margin = self.geocode_margin
        context.scene.project_settings.save()

    def building_margin_updated(self, context):
        context.scene.project_settings.building_margin = self.building_margin
        context.scene.project_settings.save()

    def preserve_roads_updated(self, context):
        context.scene.project_settings.preserve_roads = self.preserve_roads
        context.scene.project_settings.save()

    def preserve_buildings_updated(self, context):
        context.scene.project_settings.preserve_buildings = self.preserve_buildings
        context.scene.project_settings.save()

    def landmark_type_updated(self, context):
        context.scene.project_settings.landmark_type = self.landmark_type
        context.scene.project_settings.save()

    def landmark_offset_updated(self, context):
        context.scene.project_settings.landmark_offset = "{:.1f}".format(float(str(self.landmark_offset))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def add_lights_updated(self, context):
        context.scene.project_settings.add_lights = self.add_lights
        context.scene.project_settings.save()

    def light_guid_updated(self, context):
        context.scene.project_settings.light_guid = self.light_guid
        context.scene.project_settings.save()

    def altitude_adjustment_updated(self, context):
        context.scene.project_settings.altitude_adjustment = "{:.2f}".format(float(str(self.altitude_adjustment))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def create_forests_vegetation_updated(self, context):
        context.scene.project_settings.create_forests_vegetation = self.create_forests_vegetation
        context.scene.project_settings.save()

    def create_woods_vegetation_updated(self, context):
        context.scene.project_settings.create_woods_vegetation = self.create_woods_vegetation
        context.scene.project_settings.save()

    def resize_ratio_updated(self, context):
        context.scene.project_settings.resize_ratio = "{:.2f}".format(float(str(self.resize_ratio))).rstrip("0").rstrip(".")
        context.scene.project_settings.save()

    def brightness_updated(self, context):
        save_float_setting(self, context, "brightness")

    def contrast_updated(self, context):
        save_float_setting(self, context, "contrast")

    def saturation_updated(self, context):
        save_float_setting(self, context, "saturation")

    def hue_updated(self, context):
        save_float_setting(self, context, "hue")

    def red_level_updated(self, context):
        save_float_setting(self, context, "red_level")

    def green_level_updated(self, context):
        save_float_setting(self, context, "green_level")

    def blue_level_updated(self, context):
        save_float_setting(self, context, "blue_level")

    # shadow lightening (step 2b): the settings of the SHADOW_LIGHTENING section
    def wall_gain_cap_updated(self, context):
        save_percent_setting(self, context, "wall_gain_cap")

    def vegetation_strength_updated(self, context):
        save_percent_setting(self, context, "vegetation_strength")

    def shadow_strength_updated(self, context):
        save_percent_setting(self, context, "shadow_strength")

    def shadow_color_updated(self, context):
        save_percent_setting(self, context, "shadow_color")

    def shadow_gain_cap_updated(self, context):
        save_percent_setting(self, context, "shadow_gain_cap")

    def shadow_vegetation_strength_updated(self, context):
        save_percent_setting(self, context, "shadow_vegetation_strength")

    def sun_candidates_updated(self, context):
        context.scene.project_settings.sun_candidates = self.sun_candidates.strip()
        context.scene.project_settings.save()

    def build_package_enabled_updated(self, context):
        context.scene.project_settings.build_package_enabled = self.build_package_enabled
        context.scene.project_settings.save()

    def python_reload_modules_updated(self, context):
        context.scene.global_settings.reload_modules = self.python_reload_modules

    def overpass_api_uri_updated(self, context):
        context.scene.global_settings.overpass_api_uri = self.overpass_api_uri

    def get_msfs_build_path(self):
        from UI.prefs import get_prefs
        prefs = get_prefs()

        if prefs is not None:
            return prefs.msfs_build_exe_path

        return str()

    def get_compressonator_exe_path(self):
        from UI.prefs import get_prefs
        prefs = get_prefs()

        if prefs is not None:
            return prefs.compressonator_exe_path

        return str()

    def get_overpass_api_uri(self):
        from UI.prefs import get_prefs
        prefs = get_prefs()

        if prefs is not None:
            return prefs.overpass_api_uri

        return str()

    projects_path: bpy.props.StringProperty(
        subtype="DIR_PATH",
        name="Path of the projects",
        description="Select the path containing all your MSFS scenery projects",
        maxlen=1024,
        default=bpy.types.Scene.global_settings.projects_path,
        update=projects_path_updated
    )
    projects_path_readonly: bpy.props.StringProperty(
        name="Path of the projects",
        description="Select the path containing all your MSFS scenery projects",
        default=bpy.types.Scene.global_settings.projects_path
    )
    project_path: StringProperty(
        subtype="FILE_PATH",
        name="Path of the xml definition_file of the project",
        description="Select the path of the xml definition file of the MSFS scenery project",
        maxlen=1024,
        default=os.path.join(os.path.join(bpy.types.Scene.global_settings.projects_path, bpy.types.Scene.global_settings.project_name), bpy.types.Scene.global_settings.definition_file),
        update=project_path_updated
    )
    project_path_readonly: bpy.props.StringProperty(
        name="Path of the project",
        description="Select the path containing the MSFS scenery project",
        default=os.path.join(bpy.types.Scene.global_settings.projects_path, bpy.types.Scene.global_settings.project_name)
    )
    project_name: StringProperty(
        name="Project name",
        description="Name of the project to initialize",
        default=bpy.types.Scene.global_settings.project_name,
        maxlen=256,
        update=project_name_updated
    )
    definition_file: StringProperty(
        name="Definition file",
        description="Xml definition_file of the MSFS project",
        default=bpy.types.Scene.global_settings.definition_file,
        maxlen=256
    )
    nb_parallel_blender_tasks: IntProperty(
        name="Number of parallel Blender tasks",
        description="Set the number of parallel Blender tasks to run concurrently (up to the number of logical processors is useful)",
        min=1,
        max=64,
        soft_min=1,
        soft_max=max(10, os.cpu_count() or 10),
        step=1,
        default=int(bpy.types.Scene.global_settings.nb_parallel_blender_tasks),
        update=nb_parallel_blender_tasks_updated
    )
    project_path_to_merge: StringProperty(
        subtype="FILE_PATH",
        name="Path of the xml definition_file of the project you want to merge into the final one",
        description="Select the path of the xml definition file of the the project you want to merge into the final msfs scenery project",
        maxlen=1024,
        default= (os.path.join(bpy.types.Scene.project_settings.project_path_to_merge, bpy.types.Scene.project_settings.definition_file_to_merge)) if bpy.types.Scene.project_settings is not None else str(),
        update=project_path_to_merge_updated
    )
    definition_file_to_merge: StringProperty(
        name="Definition file",
        description="Xml definition_file of the project you want to merge into the final one",
        default=bpy.types.Scene.project_settings.definition_file_to_merge if bpy.types.Scene.project_settings is not None else str(),
        maxlen=256
    )
    project_path_to_merge_readonly: bpy.props.StringProperty(
        name="Path of the project you want to merge into the final msfs scenery project",
        description="Select the path containing the project you want to merge into the final msfs scenery project",
        default=(os.path.join(bpy.types.Scene.project_settings.project_path_to_merge, bpy.types.Scene.project_settings.definition_file_to_merge)) if bpy.types.Scene.project_settings is not None else str()
    )
    author_name: StringProperty(
        name="Author name",
        description="Author of the msfs scenery project",
        default=bpy.types.Scene.global_settings.author_name if bpy.types.Scene.global_settings is not None else str(),
        maxlen=256,
        update=author_name_updated
    )
    output_texture_format: EnumProperty(
        name="Output texture format",
        description="output format of the texture files (jpg or png) used by the photogrammetry tiles",
        items=[
            (PNG_TEXTURE_FORMAT, PNG_TEXTURE_FORMAT, str()),
            (JPG_TEXTURE_FORMAT, JPG_TEXTURE_FORMAT, str()),
        ],
        default=bpy.types.Scene.project_settings.output_texture_format if bpy.types.Scene.project_settings is not None else PNG_TEXTURE_FORMAT,
        update=output_texture_format_updated
    )
    collider_as_lower_lod: BoolProperty(
        name="Add the collider as the lower LOD for each tile",
        description="Add the collider as the lower LOD for each tile (make the tiles disappear when they take less than 1% of the screen)",
        default=bpy.types.Scene.project_settings.collider_as_lower_lod if bpy.types.Scene.project_settings is not None else False,
        update=collider_as_lower_lod_updated
    )
    backup_enabled: BoolProperty(
        name="Backup enabled",
        description="Enable the backup of the project files before processing",
        default=bpy.types.Scene.project_settings.backup_enabled if bpy.types.Scene.project_settings is not None else False,
        update=backup_enabled_updated
    )
    lat_correction: FloatProperty(
        name="Latitude correction",
        description="Set the latitude correction for positioning the tiles",
        soft_min=-0.1,
        soft_max=0.1,
        step=1,
        precision=6,
        default=float(bpy.types.Scene.project_settings.lat_correction) if bpy.types.Scene.project_settings is not None else 0.0,
        update=lat_correction_updated
    )
    lon_correction: FloatProperty(
        name="Longitude correction",
        description="Set the longitude correction for positioning the tiles",
        soft_min=-0.1,
        soft_max=0.1,
        step=1,
        precision=6,
        default=float(bpy.types.Scene.project_settings.lon_correction) if bpy.types.Scene.project_settings is not None else 0.0,
        update=lon_correction_updated
    )
    airport_city: StringProperty(
        name="City",
        description="City of the airport to exclude",
        default=bpy.types.Scene.project_settings.airport_city if bpy.types.Scene.project_settings is not None else str(),
        maxlen=256,
        update=airport_city_updated
    )
    smooth_beaches: BoolProperty(
        name="Smooth the beaches",
        description="Smooth the beaches (OpenStreetMap natural=beach) of the Google Earth tiles, whose photogrammetry of the sand is spiky",
        default=bpy.types.Scene.project_settings.smooth_beaches if bpy.types.Scene.project_settings is not None else False,
        update=smooth_beaches_updated
    )
    push_down_water: BoolProperty(
        name="Push down the water",
        description="Push the water of the Google Earth tiles down under the water level, instead of cutting it (no holes in the 3d data along the shores)",
        default=bpy.types.Scene.project_settings.push_down_water if bpy.types.Scene.project_settings is not None else True,
        update=push_down_water_updated
    )
    exclude_water: BoolProperty(
        name="Exclude water 3d data",
        description="Exclude water 3d data",
        default=True,
    )
    exclude_forests: BoolProperty(
        name="Exclude forests 3d data",
        description="Exclude forests 3d data",
        default=bpy.types.Scene.project_settings.exclude_forests if bpy.types.Scene.project_settings is not None else False,
        update=exclude_forests_updated
    )
    exclude_woods: BoolProperty(
        name="Exclude woods 3d data",
        description="Exclude woods 3d data",
        default=bpy.types.Scene.project_settings.exclude_woods if bpy.types.Scene.project_settings is not None else False,
        update=exclude_woods_updated
    )
    exclude_ground: BoolProperty(
        name="Exclude ground 3d data",
        description="Exclude other ground 3d data (farmlands, vineyards, allotments, meadows, orchards)",
        default=bpy.types.Scene.project_settings.exclude_ground if bpy.types.Scene.project_settings is not None else False,
        update=exclude_ground_updated
    )
    exclude_nature_reserves: BoolProperty(
        name="Exclude nature reserves 3d data",
        description="Exclude nature reserves 3d data",
        default=bpy.types.Scene.project_settings.exclude_nature_reserves if bpy.types.Scene.project_settings is not None else False,
        update=exclude_nature_reserves_updated
    )
    exclude_parks: BoolProperty(
        name="Exclude parks 3d data",
        description="Exclude parks 3d data",
        default=bpy.types.Scene.project_settings.exclude_parks if bpy.types.Scene.project_settings is not None else False,
        update=exclude_parks_updated
    )
    keep_buildings: BoolProperty(
        name="Keep buildings 3d data",
        description="Keep buildings 3d data",
        default=True,
    )
    building_margin: FloatProperty(
        name="Building margin",
        description="Margin of the around the buildings in order to fix the bias between Google Earth data and OSM data",
        soft_min=-10.0,
        soft_max=20.0,
        step=0.1,
        precision=1,
        default=float(bpy.types.Scene.project_settings.building_margin) if bpy.types.Scene.project_settings is not None else 8.0,
        update=building_margin_updated
    )
    keep_roads: BoolProperty(
        name="Keep roads 3d data",
        description="Keep roads 3d data",
        default=bpy.types.Scene.project_settings.keep_roads if bpy.types.Scene.project_settings is not None else True,
        update=keep_roads_updated
    )
    keep_constructions: BoolProperty(
        name="Keep construction area 3d data",
        description="Keep construction area 3d data",
        default=bpy.types.Scene.project_settings.keep_constructions if bpy.types.Scene.project_settings is not None else True,
        update=keep_constructions_updated
    )
    keep_residential: BoolProperty(
        name="Keep residential area 3d data",
        description="Keep residential area 3d data",
        default=bpy.types.Scene.project_settings.keep_residential if bpy.types.Scene.project_settings is not None else False,
        update=keep_residential_updated
    )
    force_osm_data_download: BoolProperty(
        name="Force openStreetMap data download",
        description="Force openStreetMap data download",
        default=bpy.types.Scene.project_settings.force_osm_data_download if bpy.types.Scene.project_settings is not None else True,
        update=force_osm_data_download_updated
    )
    process_all: BoolProperty(
        name="Process all the tiles (if unticked, process only the tiles that have not been cleaned)",
        description="Process all the tiles (if unticked, process only the tiles that have not been cleaned)",
        default=bpy.types.Scene.project_settings.process_all if bpy.types.Scene.project_settings is not None else False,
        update=process_all_updated
    )
    flat_water_level: BoolProperty(
        name="Flat water level",
        description="Set the height data of each water body to a flat level, at the Google Earth water surface. The MSFS water surface follows the terrain",
        default=bpy.types.Scene.project_settings.flat_water_level if bpy.types.Scene.project_settings is not None else True,
        update=flat_water_level_updated
    )
    blend_outer_edges: BoolProperty(
        name="Blend the outer edges of the scenery",
        description="Raise the height data up to the tiles ground on the outer border of the scenery, to avoid a step between the tiles and the MSFS terrain. Disable it for sceneries stitched together from several projects",
        default=bpy.types.Scene.project_settings.blend_outer_edges if bpy.types.Scene.project_settings is not None else True,
        update=blend_outer_edges_updated
    )
    high_precision: BoolProperty(
        name="High precision height data generation",
        description="Generate the height data from the ground seen from above on the most detailed tile lods (the ground filter removes the buildings and trees). Off: the coarsest lods, smoothed, nearly a flat plane. Needed for an accurate flat water level. Default: on",
        default=bpy.types.Scene.project_settings.high_precision if bpy.types.Scene.project_settings is not None else True,
        update=high_precision_updated
    )
    ground_filter_size: FloatProperty(
        name="Ground filter size",
        description="Width (in meters) of the filter removing the buildings and trees from the height data, so that the terrain stays under the tiles (0 to disable it)",
        min=0.0,
        soft_max=200.0,
        step=100,
        precision=0,
        default=float(bpy.types.Scene.project_settings.ground_filter_size) if bpy.types.Scene.project_settings is not None else 40.0,
        update=ground_filter_size_updated
    )
    height_adjustment: FloatProperty(
        name="MSFS terrain offset",
        description="Height of the MSFS terrain relative to the ground of the tiles (in meters, 0 or below), keeping the terrain from poking through the tiles: more negative if it shows through, closer to 0 if gaps appear at the edges. Default: -1 m",
        soft_min=-10.0,
        max=0.0,
        step=0.1,
        precision=1,
        default=float(bpy.types.Scene.project_settings.height_adjustment) if bpy.types.Scene.project_settings is not None else 0.0,
        update=height_adjustment_updated
    )
    geocode: StringProperty(
        name="Geocode",
        description="Geocode to search from OSM data (for exclusion or isolation) in the form \"location name, city\", or\"(way|relation), osmid\"",
        default=bpy.types.Scene.project_settings.geocode if bpy.types.Scene.project_settings is not None else str(),
        maxlen=256,
        update=geocode_updated
    )
    geocode_margin: FloatProperty(
        name="Geocode margin",
        description="Margin of the geocode polygon used to exclude or isolate the 3d data",
        soft_min=-10.0,
        soft_max=20.0,
        step=0.1,
        precision=1,
        default=float(bpy.types.Scene.project_settings.geocode_margin) if bpy.types.Scene.project_settings is not None else 0.0,
        update=geocode_margin_updated
    )
    preserve_roads: BoolProperty(
        name="Preserve roads",
        description="Preserve neighborhood roads when excluding 3d data from geocode",
        default=bpy.types.Scene.project_settings.preserve_roads if bpy.types.Scene.project_settings is not None else True,
        update=preserve_roads_updated
    )
    preserve_buildings: BoolProperty(
        name="Preserve buildings",
        description="Preserve neighborhood buildings when excluding 3d data from geocode",
        default=bpy.types.Scene.project_settings.preserve_buildings if bpy.types.Scene.project_settings is not None else True,
        update=preserve_buildings_updated
    )
    landmark_type: EnumProperty(
        name="Landmark type",
        description="Type of the landmark (POI, City, ...)",
        items=[
            (POI_LANDMARK_FORMAT_TYPE, POI_LANDMARK_FORMAT_TYPE, str()),
            (CITY_LANDMARK_FORMAT_TYPE, CITY_LANDMARK_FORMAT_TYPE, str()),
        ],
        default=bpy.types.Scene.project_settings.landmark_type if bpy.types.Scene.project_settings is not None else POI_LANDMARK_FORMAT_TYPE,
        update=landmark_type_updated

    )
    isolate_3d_data: EnumProperty(
        name="OpenStreetMap accuracy",
        description="Accuracy of the OpenStreetMap data",
        items=[
            ("GOOD", "Accurate", str()),
            ("BAD", "Not accurate", str()),
        ],
        default="BAD" if bpy.types.Scene.project_settings is None else ("GOOD" if bpy.types.Scene.project_settings.isolate_3d_data else "BAD"),
        update=isolate_3d_data_updated
    )
    enum_items = (('0', 'Cube', ''), ('1', 'Pyramid', ''))
    bpy.types.Scene.obj_type = bpy.props.EnumProperty(items=enum_items)
    landmark_offset: FloatProperty(
        name="Landmark offset",
        description="Height offset of the landmark",
        soft_min=-100.0,
        soft_max=100.0,
        step=1.0,
        precision=1,
        default=float(bpy.types.Scene.project_settings.landmark_offset) if bpy.types.Scene.project_settings is not None else 0.0,
        update=landmark_offset_updated
    )
    altitude_adjustment: FloatProperty(
        name="Altitude update",
        description="Adjustment of the altitude of the whole scenery components (tiles, objects, colliders, landmarks, height maps)",
        soft_min=-10.0,
        soft_max=20.0,
        step=0.1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.altitude_adjustment) if bpy.types.Scene.project_settings is not None else -1.0,
        update=altitude_adjustment_updated
    )
    add_lights: BoolProperty(
        name="Add lights around the landmark",
        description="Add lights around the geocode landmark",
        default=bpy.types.Scene.project_settings.add_lights if bpy.types.Scene.project_settings is not None else False,
        update=add_lights_updated
    )
    light_guid: EnumProperty(
        name="Add lights around the landmark",
        description="Add lights around the geocode landmark",
        items=[
            (LIGHT_WARM_GUID, LIGHT_WARM_DISPLAY_NAME, str()),
            (LIGHT_COLD_GUID, LIGHT_COLD_DISPLAY_NAME, str()),
            (LIGHT_100_BLUE_GUID, LIGHT_100_BLUE_DISPLAY_NAME, str()),
            (LIGHT_500_BLUE_GUID, LIGHT_500_BLUE_DISPLAY_NAME, str()),
            (LIGHT_1000_BLUE_GUID, LIGHT_1000_BLUE_DISPLAY_NAME, str()),
            (LIGHT_100_GREEN_GUID, LIGHT_100_GREEN_DISPLAY_NAME, str()),
            (LIGHT_500_GREEN_GUID, LIGHT_500_GREEN_DISPLAY_NAME, str()),
            (LIGHT_1000_GREEN_GUID, LIGHT_1000_GREEN_DISPLAY_NAME, str()),
            (LIGHT_100_SOFT_GREEN_GUID, LIGHT_100_SOFT_GREEN_DISPLAY_NAME, str()),
            (LIGHT_500_SOFT_GREEN_GUID, LIGHT_500_SOFT_GREEN_DISPLAY_NAME, str()),
            (LIGHT_1000_SOFT_GREEN_GUID, LIGHT_1000_SOFT_GREEN_DISPLAY_NAME, str()),
            (LIGHT_100_WHITE_GUID, LIGHT_100_WHITE_DISPLAY_NAME, str()),
            (LIGHT_500_WHITE_GUID, LIGHT_500_WHITE_DISPLAY_NAME, str()),
            (LIGHT_1000_WHITE_GUID, LIGHT_1000_WHITE_DISPLAY_NAME, str()),
            (LIGHT_100_MINT_GREEN_GUID, LIGHT_100_MINT_GREEN_DISPLAY_NAME, str()),
            (LIGHT_500_MINT_GREEN_GUID, LIGHT_500_MINT_GREEN_DISPLAY_NAME, str()),
            (LIGHT_1000_MINT_GREEN_GUID, LIGHT_1000_MINT_GREEN_DISPLAY_NAME, str()),
            (LIGHT_100_PINK_GUID, LIGHT_100_PINK_DISPLAY_NAME, str()),
            (LIGHT_500_PINK_GUID, LIGHT_500_PINK_DISPLAY_NAME, str()),
            (LIGHT_1000_PINK_GUID, LIGHT_1000_PINK_DISPLAY_NAME, str()),
            (LIGHT_100_RED_GUID, LIGHT_100_RED_DISPLAY_NAME, str()),
            (LIGHT_500_RED_GUID, LIGHT_500_RED_DISPLAY_NAME, str()),
            (LIGHT_1000_RED_GUID, LIGHT_1000_RED_DISPLAY_NAME, str()),
            (LIGHT_100_SKY_BLUE_GUID, LIGHT_100_SKY_BLUE_DISPLAY_NAME, str()),
            (LIGHT_500_SKY_BLUE_GUID, LIGHT_500_SKY_BLUE_DISPLAY_NAME, str()),
            (LIGHT_1000_SKY_BLUE_GUID, LIGHT_1000_SKY_BLUE_DISPLAY_NAME, str()),
            (LIGHT_100_PURPLE_GUID, LIGHT_100_PURPLE_DISPLAY_NAME, str()),
            (LIGHT_500_PURPLE_GUID, LIGHT_500_PURPLE_DISPLAY_NAME, str()),
            (LIGHT_1000_PURPLE_GUID, LIGHT_1000_PURPLE_DISPLAY_NAME, str()),
            (LIGHT_100_YELLOW_GUID, LIGHT_100_YELLOW_DISPLAY_NAME, str()),
            (LIGHT_500_YELLOW_GUID, LIGHT_500_YELLOW_DISPLAY_NAME, str()),
            (LIGHT_1000_YELLOW_GUID, LIGHT_1000_YELLOW_DISPLAY_NAME, str())
        ],
        default=bpy.types.Scene.project_settings.light_guid if bpy.types.Scene.project_settings is not None else LIGHT_WARM_GUID,
        update=light_guid_updated
    )
    create_forests_vegetation: BoolProperty(
        name="Create MSFS vegetation on forests OSM area",
        description="Create MSFS vegetation on forests OSM area (useful if MSFS forests vegetation is not accurate)",
        default=bpy.types.Scene.project_settings.create_forests_vegetation if bpy.types.Scene.project_settings is not None else False,
        update=create_forests_vegetation_updated
    )
    create_woods_vegetation: BoolProperty(
        name="Create MSFS vegetation on woods OSM area",
        description="Create MSFS vegetation on woods OSM area (useful if MSFS woods vegetation is not accurate)",
        default=bpy.types.Scene.project_settings.create_woods_vegetation if bpy.types.Scene.project_settings is not None else False,
        update=create_woods_vegetation_updated
    )
    resize_ratio: FloatProperty(
        name="Texture resize ratio",
        description="Ratio used to resize the textures of the tiles",
        soft_min=0.1,
        soft_max=1.0,
        step=0.1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.resize_ratio) if bpy.types.Scene.project_settings is not None else 0.5,
        update=resize_ratio_updated
    )
    brightness: FloatProperty(
        name="Brightness",
        description="Brightness of the textures downloaded with TileDownloader (1 = unchanged): use the value of the tiles download",
        soft_min=0.0,
        soft_max=2.0,
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.brightness) if bpy.types.Scene.project_settings is not None else 1.0,
        update=brightness_updated
    )
    contrast: FloatProperty(
        name="Contrast",
        description="Contrast of the textures downloaded with TileDownloader (1 = unchanged): use the value of the tiles download",
        soft_min=0.0,
        soft_max=2.0,
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.contrast) if bpy.types.Scene.project_settings is not None else 1.0,
        update=contrast_updated
    )
    saturation: FloatProperty(
        name="Saturation",
        description="Saturation of the textures downloaded with TileDownloader (1 = unchanged): use the value of the tiles download",
        soft_min=0.0,
        soft_max=2.0,
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.saturation) if bpy.types.Scene.project_settings is not None else 1.0,
        update=saturation_updated
    )
    hue: FloatProperty(
        name="Hue",
        description="Hue of the textures downloaded with TileDownloader (0 = unchanged): use the value of the tiles download",
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.hue) if bpy.types.Scene.project_settings is not None else 0.0,
        update=hue_updated
    )
    red_level: FloatProperty(
        name="Red level",
        description="Red level of the textures downloaded with TileDownloader (1 = unchanged): use the value of the tiles download",
        soft_min=0.0,
        soft_max=2.0,
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.red_level) if bpy.types.Scene.project_settings is not None else 1.0,
        update=red_level_updated
    )
    green_level: FloatProperty(
        name="Green level",
        description="Green level of the textures downloaded with TileDownloader (1 = unchanged): use the value of the tiles download",
        soft_min=0.0,
        soft_max=2.0,
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.green_level) if bpy.types.Scene.project_settings is not None else 1.0,
        update=green_level_updated
    )
    blue_level: FloatProperty(
        name="Blue level",
        description="Blue level of the textures downloaded with TileDownloader (1 = unchanged): use the value of the tiles download",
        soft_min=0.0,
        soft_max=2.0,
        step=1,
        precision=2,
        default=float(bpy.types.Scene.project_settings.blue_level) if bpy.types.Scene.project_settings is not None else 1.0,
        update=blue_level_updated
    )
    wall_gain_cap: FloatProperty(
        name="Wall gain cap",
        description="The most the shaded side of walls, roofs and trees is brightened towards its lit side (300 % = up to 3 times). Default: 300 %",
        subtype="PERCENTAGE",
        min=100.0,
        max=600.0,
        step=100,
        precision=0,
        default=100.0 * float(getattr(bpy.types.Scene.project_settings, "wall_gain_cap", 3.0)) if bpy.types.Scene.project_settings is not None else 300.0,
        update=wall_gain_cap_updated
    )
    vegetation_strength: FloatProperty(
        name="Vegetation strength",
        description="The share of the shaded side correction applied to trees and other vegetation (lumpy meshes). Default: 90 %",
        subtype="PERCENTAGE",
        min=0.0,
        max=100.0,
        step=100,
        precision=0,
        default=100.0 * float(getattr(bpy.types.Scene.project_settings, "vegetation_strength", 0.9)) if bpy.types.Scene.project_settings is not None else 90.0,
        update=vegetation_strength_updated
    )
    shadow_strength: FloatProperty(
        name="Shadow strength",
        description="How much the cast shadows are lifted (100 % = up to the lit surface around them; lower keeps some shadow and fewer artifacts). Default: 60 %",
        subtype="PERCENTAGE",
        min=0.0,
        max=100.0,
        step=100,
        precision=0,
        default=100.0 * float(getattr(bpy.types.Scene.project_settings, "shadow_strength", 0.6)) if bpy.types.Scene.project_settings is not None else 60.0,
        update=shadow_strength_updated
    )
    shadow_color: FloatProperty(
        name="Shadow color",
        description="The share of the bluish color shift of the cast shadows that is removed (0 % = brightness only, 100 % = all, can turn yellowish). Default: 50 %",
        subtype="PERCENTAGE",
        min=0.0,
        max=100.0,
        step=100,
        precision=0,
        default=100.0 * float(getattr(bpy.types.Scene.project_settings, "shadow_color", 0.5)) if bpy.types.Scene.project_settings is not None else 50.0,
        update=shadow_color_updated
    )
    shadow_gain_cap: FloatProperty(
        name="Shadow gain cap",
        description="The most a cast shadow is brightened, before the strength is applied (600 % = up to 6 times). Default: 600 %",
        subtype="PERCENTAGE",
        min=100.0,
        max=1000.0,
        step=100,
        precision=0,
        default=100.0 * float(getattr(bpy.types.Scene.project_settings, "shadow_gain_cap", 6.0)) if bpy.types.Scene.project_settings is not None else 600.0,
        update=shadow_gain_cap_updated
    )
    shadow_vegetation_strength: FloatProperty(
        name="Shadow vegetation strength",
        description="The share of the cast shadow correction applied to vegetation (shadows of trees on trees). Default: 50 %",
        subtype="PERCENTAGE",
        min=0.0,
        max=100.0,
        step=100,
        precision=0,
        default=100.0 * float(getattr(bpy.types.Scene.project_settings, "shadow_vegetation_strength", 0.5)) if bpy.types.Scene.project_settings is not None else 50.0,
        update=shadow_vegetation_strength_updated
    )
    sun_candidates: StringProperty(
        name="Sun candidates",
        description="The sun directions when the imagery was captured, as azimuth/elevation in degrees, separated by commas, e.g. 168/34, 150/40. Empty (default): estimated from the shadows in the tiles",
        default=str(getattr(bpy.types.Scene.project_settings, "sun_candidates", "")) if bpy.types.Scene.project_settings is not None else "",
        update=sun_candidates_updated
    )
    msfs_build_exe_path_readonly: StringProperty(
        name="Path to the MSFS bin exe that builds the MSFS packages",
        description="Select the path to the MSFS bin exe that builds the MSFS packages",
        get=get_msfs_build_path
    )
    build_package_enabled: BoolProperty(
        name="Build package enabled",
        description="Enable the package compilation when the script has finished",
        default=bpy.types.Scene.project_settings.build_package_enabled if bpy.types.Scene.project_settings is not None else False,
        update=build_package_enabled_updated
    )
    compressonator_exe_path_readonly: StringProperty(
        name="Path to the compressonator bin exe that compresses the package texture files",
        description="Select the path to the compressonator bin exe that compresses the package texture file",
        get=get_compressonator_exe_path
    )
    python_reload_modules: BoolProperty(
        name="Reload python modules (for dev purpose)",
        description="Set this to true if you want to reload python modules (mainly for dev purpose)",
        default=bpy.types.Scene.global_settings.reload_modules,
        update=python_reload_modules_updated
    )
    overpass_api_uri: StringProperty(
        name="Uri of the overpass API used by Osmnx to retrieve OSM data",
        description="Set the uri of the overpass API used by Osmnx to retrieve OSM data",
        default=bpy.types.Scene.global_settings.overpass_api_uri,
        update=overpass_api_uri_updated
    )
    overpass_api_uri_readonly: StringProperty(
        name="Uri of the overpass API used by Osmnx to retrieve OSM data",
        description="Set the uri of the overpass API used by Osmnx to retrieve OSM data",
        get=get_overpass_api_uri
    )
