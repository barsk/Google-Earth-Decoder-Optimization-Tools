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

import xml.etree.ElementTree as Et

from utils import Xml


class MsfsPackageDefinitionsXml(Xml):
    ASSETS_GROUP_TAG = "AssetGroups"
    ASSET_GROUP_TAG = "AssetGroup"
    ASSET_DIR_TAG = "AssetDir"
    OUTPUT_DIR_TAG = "OutputDir"
    FLAGS_TAG = "Flags"
    PACKAGE_ORDER_HINT_TAG = "PackageOrderHint"
    TYPE_TAG = "Type"
    NAME_ATTR = "Name"
    VERSION_ATTR = "Version"
    # MSFS 2020 type of the model libraries in the GEDOT template, upgraded by MSFS 2024 to ModelLib version 1
    ART_PROJ_TYPE = "ArtProj"
    MODEL_LIB_TYPE = "ModelLib"
    MODEL_LIB_VERSION = "1"
    DEFAULT_TYPE_VERSION = "0"

    ASSETS_GROUP_SEARCH_PATTERN = "./ASSETS_GROUP"
    SCENERY_OBJECT_LOD_MODEL_FILE_SEARCH_PATTERN = "./" + ASSETS_GROUP_TAG + "/" + ASSET_GROUP_TAG
    
    def __init__(self, file_folder, file_name):
        super().__init__(file_folder, file_name)

    def find_model_lib_asset_group(self, model_lib_folder):
        assets_group = self.root.findall(self.SCENERY_OBJECT_LOD_MODEL_FILE_SEARCH_PATTERN)
        for asset_group in assets_group:
            if model_lib_folder in asset_group.find(self.ASSET_DIR_TAG).text:
                return asset_group.find(self.OUTPUT_DIR_TAG).text.replace("/", "\\")

        return str()

    def convert_to_msfs_2024(self):
        # the asset groups as upgraded by the MSFS 2024 project editor, which otherwise asks to upgrade them
        self.root.attrib.pop(self.NAME_ATTR, None)
        for asset_group in self.root.findall(self.SCENERY_OBJECT_LOD_MODEL_FILE_SEARCH_PATTERN):
            type_element = asset_group.find(self.TYPE_TAG)
            if type_element is None:
                continue
            if type_element.text == self.ART_PROJ_TYPE:
                type_element.text = self.MODEL_LIB_TYPE
                type_element.set(self.VERSION_ATTR, self.MODEL_LIB_VERSION)
            elif type_element.get(self.VERSION_ATTR) is None:
                type_element.set(self.VERSION_ATTR, self.MODEL_LIB_VERSION if type_element.text == self.MODEL_LIB_TYPE else self.DEFAULT_TYPE_VERSION)
        self.save()

    def set_package_order_hint(self, package_order_hint):
        # add the package order hint after the flags, if the definition doesn't have one yet
        if self.root.find(self.PACKAGE_ORDER_HINT_TAG) is not None:
            return

        package_order_hint_element = Et.Element(self.PACKAGE_ORDER_HINT_TAG)
        package_order_hint_element.text = package_order_hint
        flags = self.root.find(self.FLAGS_TAG)
        self.root.insert(list(self.root).index(flags) + 1 if flags is not None else len(self.root), package_order_hint_element)
        self.save()


