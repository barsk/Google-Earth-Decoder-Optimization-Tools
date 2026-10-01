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

import json
import os
import shutil

from utils import Settings
from utils.install_lib import get_pref_value

from constants import ENCODING, INI_FILE, XML_FILE_EXT, CONFIG_TEMPLATES_FOLDER, GLOBAL_SETTINGS_TEMPLATE_FILE, DEFAULT_OVERPASS_API_URI


class GlobalSettings(Settings):
    sources_path: str
    projects_path: str
    project_name: str
    author_name: str
    definition_file: str
    nb_parallel_blender_tasks: float
    reload_modules: str
    sources_path: str
    sections: list
    decoder_output_path: str
    overpass_api_uri: str

    LODS_SECTION = "LODS"
    TARGET_MIN_SIZE_VALUES_SETTING = "target_min_size_values"

    def __init__(self, path):
        self.file_name = INI_FILE
        self.projects_path = str()
        self.project_name = str()
        self.author_name = str()
        self.definition_file = str()
        self.nb_parallel_blender_tasks = 4.0
        self.reload_modules = "False"
        self.sections = []
        self.decoder_output_path = str()
        self.overpass_api_uri = DEFAULT_OVERPASS_API_URI

        if not os.path.isfile(os.path.join(path, self.file_name)):
            config_template_path = os.path.join(path, CONFIG_TEMPLATES_FOLDER)
            shutil.copyfile(os.path.join(config_template_path, GLOBAL_SETTINGS_TEMPLATE_FILE), os.path.join(path, self.file_name))

        super().__init__(path)

        if self.definition_file == str() and self.project_name != str():
            self.definition_file = self.project_name.capitalize() + XML_FILE_EXT

        # check if modules have to be reloaded (mostly for blender dev purpose)
        self.reload_modules = json.loads(self.reload_modules.lower())

        # ensure to convert float settings values
        self.nb_parallel_blender_tasks = int(self.nb_parallel_blender_tasks)

        # the ini file stores the Overpass uri as "overpass_api", but the scripts use overpass_api_uri.
        # A uri changed in the addon preferences wins, otherwise use the one from the ini file
        ini_overpass_api_uri = getattr(self, "overpass_api", str()).strip() or DEFAULT_OVERPASS_API_URI
        self.overpass_api_uri = get_pref_value("overpass_api_uri", DEFAULT_OVERPASS_API_URI)
        if self.overpass_api_uri == DEFAULT_OVERPASS_API_URI:
            self.overpass_api_uri = ini_overpass_api_uri

    def save(self):
        config = super().set_config(self.path, self.file_name)

        with open(os.path.join(self.path, self.file_name), "w", encoding=ENCODING) as configfile:
            config.write(configfile)
