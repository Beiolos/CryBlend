# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

#------------------------------------------------------------------------------
# Name:        __init__.py
# Purpose:     Primary python file for CryBlend add-on
#
# Author:      Angelo J. Miner
# Extended by: Duo Oratar, Mikołaj Milej, stardidi, Daniel White
#
# Created:     23/02/2012
# Copyright:   (c) Angelo J. Miner 2012
# License:     GPLv2+
#------------------------------------------------------------------------------


bl_info = {
    "name": "CryEngine3 Utilities and Exporter",
    "author": "Angelo J. Miner, Duo Oratar, Mikołaj Milej, stardidi, Daniel White",
    "blender": (2, 70, 0),
    "version": (5, 0, 0),
    "location": "CryBlend Menu",
    "description": "CryEngine3 Utilities and Exporter",
    "warning": "",
    "wiki_url": "https://github.com/travnick/CryBlend/wiki",
    "tracker_url": "https://github.com/travnick/CryBlend/issues?state=open",
    "support": 'OFFICIAL',
    "category": "Import-Export"}

# old wiki url: http://wiki.blender.org/
# index.php/Extensions:2.5/Py/Scripts/Import-Export/CryEngine3

VERSION = '.'.join(str(n) for n in bl_info["version"])


if "bpy" in locals():
    import imp
    imp.reload(add)
    imp.reload(export)
    imp.reload(exceptions)
    imp.reload(utils)
else:
    import bpy
    from io_export_cryblend import add, export, exceptions, utils

from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty, \
    FloatProperty, IntProperty, StringProperty
from bpy.types import Menu, Panel
from bpy_extras.io_utils import ExportHelper
from io_export_cryblend.configuration import Configuration
from io_export_cryblend.outPipe import cbPrint
from xml.dom.minidom import Document, Element, parse, parseString
import bmesh
import bpy.ops
import bpy_extras
import configparser
import os
import os.path
import pickle
import webbrowser
import subprocess


# for help
new = 2  # open in a new tab, if possible

#------------------------------------------------------------------------------
# Configurations
#------------------------------------------------------------------------------

class PathSelectTemplate(ExportHelper):
    check_existing = True

    def execute(self, context):
        self.process(self.filepath)

        Configuration.save()
        return {'FINISHED'}


class FindRC(bpy.types.Operator, PathSelectTemplate):
    '''Select the Resource Compiler executable.'''

    bl_label = "Find The Resource Compiler"
    bl_idname = "file.find_rc"

    filename_ext = ".exe"

    def process(self, filepath):
        Configuration.rc_path = "%s" % filepath
        cbPrint("Found RC at {!r}.".format(Configuration.rc_path), 'debug')

    def invoke(self, context, event):
        self.filepath = Configuration.rc_path

        return ExportHelper.invoke(self, context, event)


class FindRCForTextureConversion(bpy.types.Operator, PathSelectTemplate):
    '''Select if you are using RC from cryengine \
newer than 3.4.5. Provide RC path from cryengine 3.4.5 \
to be able to export your textures as dds files.'''

    bl_label = "Find the Resource Compiler for Texture Conversion"
    bl_idname = "file.find_rc_for_texture_conversion"

    filename_ext = ".exe"

    def process(self, filepath):
        Configuration.rc_for_texture_conversion_path = "%s" % filepath
        cbPrint("Found RC at {!r}.".format(
                        Configuration.rc_for_texture_conversion_path),
                'debug')

    def invoke(self, context, event):
        self.filepath = Configuration.rc_for_texture_conversion_path

        return ExportHelper.invoke(self, context, event)


class SelectTexturesDirectory(bpy.types.Operator, PathSelectTemplate):
    '''This path will be used to create relative path \
for textures in .mtl file.'''

    bl_label = "Select Textures Directory"
    bl_idname = "file.select_textures_directory"

    filename_ext = ""

    def process(self, filepath):
        Configuration.textures_directory = "%s" % os.path.dirname(filepath)
        cbPrint("Textures directory: {!r}.".format(
                                            Configuration.textures_directory),
                'debug')

    def invoke(self, context, event):
        self.filepath = Configuration.textures_directory

        return ExportHelper.invoke(self, context, event)


class SaveCryBlendConfiguration(bpy.types.Operator):
    '''operator: Saves current CryBlend configuration.'''
    bl_label = "Save Config File"
    bl_idname = "config.save"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        Configuration.save()
        return {'FINISHED'}

#------------------------------------------------------------------------------
# Export Tools
#------------------------------------------------------------------------------

class AddCryExportNode(bpy.types.Operator):
    '''Add selected objects to an existing or new CryExportNode'''
    bl_label = "Add Export Node"
    bl_idname = "object.add_cry_export_node"
    bl_options = {"REGISTER", "UNDO"}

    node_type = EnumProperty(
        name="Type",
        items=(
            ("cgf", "CGF",
             "Static Geometry"),
            ("cga", "CGA",
             "Animated Geometry"),
            ("chr", "CHR",
             "Character"),
            ("skin", "SKIN",
             "Skinned Render Mesh"),
            ("anm", "ANM",
             "Geometry Animation"),
            ("i_caf", "I_CAF",
             "Character Animation"),
        ),
        default="cgf",
    )
    node_name = StringProperty(name="Name")

    def execute(self, context):
        if bpy.context.selected_objects:
            scene = bpy.context.scene
            nodename = "{}.{}".format(self.node_name, self.node_type)
            group = bpy.data.groups.get(nodename)
            if group is None:
                bpy.ops.group.create(name=nodename)
            else:
                for object in bpy.context.selected_objects:
                    if object.name not in group.objects:
                        group.objects.link(object)
            message = "Adding Export Node"
        else:
            message = "No Objects Selected"

        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class SelectedToCryExportNodes(bpy.types.Operator):
    '''Add selected objects to individual CryExportNodes.'''
    bl_label = "Nodes from Object Names"
    bl_idname = "object.selected_to_cry_export_nodes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = bpy.context.selected_objects
        bpy.ops.object.select_all(action="DESELECT")
        for object_ in selected:
            object_.select = True
            if (len(object_.users_group) == 0):
                bpy.ops.group.create(name="{}.cgf".format(object_.name))
            object_.select = False

        for object_ in selected:
            object_.select = True

        message = "Adding Selected Objects to Export Nodes"
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label("Confirm...")


class ApplyTransforms(bpy.types.Operator):
    '''Click to apply transforms on selected objects.'''
    bl_label = "Apply Transforms"
    bl_idname = "object.apply_transforms"

    def execute(self, context):
        selected = bpy.context.selected_objects
        if selected:
            message = "Applying object transforms."
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        else:
            message = "No Object Selected."
        self.report({'INFO'}, message)
        return {'FINISHED'}

#------------------------------------------------------------------------------
# Material Tools
#------------------------------------------------------------------------------

class SetMaterialNames(bpy.types.Operator):
    '''Materials will be named after the first CryExportNode the Object is in.'''
    """Set Material Names by heeding the RC naming scheme:
        - CryExportNode group name
        - Strict number sequence beginning with 1 for each CryExportNode (max 999)
        - Physics
    """
    bl_label = "Update material names in CryExportNodes"
    bl_idname = "material.set_material_names"
    physUserInput = StringProperty(name="Physics", default = "physDefault")

    def execute(self, context):
        # Revert all materials to fetch also those that are no longer in a group
        # and store their possible physics properties in a dictionary.
        physicsProperties = getMaterialPhysics()
        removeCryBlendProperties()

        # Create a dictionary with all CryExportNodes to store the current number
        # of materials in it.
        materialCounter = getMaterialCounter()

        for group in bpy.data.groups:
            if utils.is_export_node(group.name):
                for object in group.objects:
                    for slot in object.material_slots:

                        # Skip materials that have been renamed already.
                        if not utils.is_cryblend_material(slot.material.name):
                            materialCounter[group.name] += 1
                            materialOldName = slot.material.name

                            # Load stored Physics if available for that material.
                            if physicsProperties.get(slot.material.name):
                                physics = physicsProperties[slot.material.name]
                            else:
                                physics = self.physUserInput

                            # Rename.
                            slot.material.name = "{}__{:03d}__{}__{}".format(
                                    utils.get_node_name(group.name.replace("CryExportNode_", "")),
                                    materialCounter[group.name],
                                    utils.replace_invalid_rc_characters(materialOldName),
                                    physics)
                            message = "Renamed {} to {}".format(
                                    materialOldName,
                                    slot.material.name)
                            self.report({'INFO'}, message)
                            cbPrint(message)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class RemoveCryBlendProperties(bpy.types.Operator):
    '''Removes all CryBlend properties from material names. This includes \
physics, so they get lost.'''
    bl_label = "Remove CryBlend properties from material names"
    bl_idname = "material.remove_cry_blend_properties"

    def execute(self, context):
        removeCryBlendProperties()
        message = "Removed CryBlend properties from material names"
        self.report({'INFO'}, message)
        cbPrint(message)
        return {'FINISHED'}


def getMaterialCounter():
    """Returns a dictionary with all CryExportNodes."""
    materialCounter = {}
    for group in bpy.data.groups:
        if utils.is_export_node(group.name):
            materialCounter[group.name] = 0
    return materialCounter


def removeCryBlendProperties():
    """Removes CryBlend properties from all material names."""
    for material in bpy.data.materials:
        properties = utils.extract_cryblend_properties(material.name)
        if properties:
            material.name = properties["Name"]


def getMaterialPhysics():
    """Returns a dictionary with the physics of all material names."""
    physicsProperties = {}
    for material in bpy.data.materials:
        properties = utils.extract_cryblend_properties(material.name)
        if properties:
            physicsProperties[properties["Name"]] = properties["Physics"]
    return physicsProperties

#------------------------------------------------------------------------------
# CryEngine-Related Tools
#------------------------------------------------------------------------------

class AddProxy(bpy.types.Operator):
    '''Click to add proxy to selected mesh. The proxy will always display as a box but will \
be converted to the selected shape in CryEngine.'''
    bl_label = "Add Proxy"
    bl_idname = "object.add_proxy"

    type_ = StringProperty()

    def execute(self, context):
        active = bpy.context.active_object

        if (active.type == "MESH"):
            already_exists = False
            for object_ in bpy.data.objects:
                if self.__is_proxy(object_.name):
                    already_exists = True
                    break
            if (not already_exists):
                self.__add_proxy(active)

        message = "Adding %s proxy to active object" % getattr(self, "type_")
        self.report({'INFO'}, message)
        return {'FINISHED'}

    def __is_proxy(self, object_name):
        return object_name.endswith("-proxy")

    def __add_proxy(self, object_):
        old_origin = object_.location.copy()
        old_cursor = bpy.context.scene.cursor_location.copy()
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.mesh.primitive_cube_add()
        bound_box = bpy.context.active_object
        bound_box.name = "{}_{}-proxy".format(object_.name, getattr(self, "type_"))
        bound_box.draw_type = "WIRE"
        bound_box.dimensions = object_.dimensions
        bound_box.location = object_.location
        bound_box.rotation_euler = object_.rotation_euler

        for group in object_.users_group:
            bpy.ops.object.group_link(group=group.name)

        name = "{}__physProxyNone".format(bound_box.name)
        proxy_material = bpy.data.materials.new(name)
        bound_box.data.materials.append(proxy_material)

        if (getattr(self, "type_") == "box"):
            bpy.ops.object.add_box_proxy_property()
        elif (getattr(self, "type_") == "capsule"):
            bpy.ops.object.add_capsule_proxy_property()
        elif (getattr(self, "type_") == "cylinder"):
            bpy.ops.object.add_cylinder_proxy_property()
        else: # sphere proxy
            bpy.ops.object.add_sphere_proxy_property()

        bpy.context.scene.cursor_location = old_origin
        bpy.ops.object.select_all(action="DESELECT")
        object_.select = True
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        object_.select = False
        bound_box.select = True
        bpy.context.scene.objects.active = bound_box
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        bpy.context.scene.cursor_location = old_cursor


class AddBreakableJoint(bpy.types.Operator):
    '''Click to add a pre-broken breakable joint to current selection.'''
    bl_label = "Add Joint"
    bl_idname = "object.add_joint"

    def execute(self, context):
        return add.add_joint(self, context)


class AddBranch(bpy.types.Operator):
    '''Click to add a branch at active vertex or first vertex in a set of vertices.'''
    bl_label = "Add Branch"
    bl_idname = "mesh.add_branch"

    def execute(self, context):
        active_object = bpy.context.scene.objects.active
        bpy.ops.object.mode_set(mode='OBJECT')
        selected_vert_coordinates = get_vertex_data()
        if (selected_vert_coordinates):
            selected_vert = selected_vert_coordinates[0]
            bpy.ops.object.add(type='EMPTY', view_align=False, enter_editmode=False, location=(selected_vert[0], selected_vert[1], selected_vert[2]))
            empty_object = bpy.context.active_object
            empty_object.name = name_branch(True)
            bpy.context.scene.objects.active = active_object
            bpy.ops.object.mode_set(mode='EDIT')

            message = "Adding Branch"
            self.report({'INFO'}, message)
            cbPrint(message)
        return {'FINISHED'}


class AddBranchJoint(bpy.types.Operator):
    '''Click to add a branch joint at selected vertex or first vertex in a set of vertices.'''
    bl_label = "Add Branch Joint"
    bl_idname = "mesh.add_branch_joint"

    def execute(self, context):
        active_object = bpy.context.scene.objects.active
        bpy.ops.object.mode_set(mode='OBJECT')
        selected_vert_coordinates = get_vertex_data()
        if (selected_vert_coordinates):
            selected_vert = selected_vert_coordinates[0]
            bpy.ops.object.add(type='EMPTY', view_align=False, enter_editmode=False, location=(selected_vert[0], selected_vert[1], selected_vert[2]))
            empty_object = bpy.context.active_object
            empty_object.name = name_branch(False)
            bpy.context.scene.objects.active = active_object
            bpy.ops.object.mode_set(mode='EDIT')

            message = "Adding Branch Joint"
            self.report({'INFO'}, message)
            cbPrint(message)
        return {'FINISHED'}


def get_vertex_data():
    selected_vert_coordinates = [i.co for i in bpy.context.active_object.data.vertices if i.select] 
    return selected_vert_coordinates


def name_branch(is_new_branch):
    highest_branch_number = 0
    highest_joint_number = 0
    for object in bpy.context.scene.objects:
        if ((object.type == 'EMPTY') and ("branch" in object.name)):
            branch_components = object.name.split("_")
            if(branch_components):
                branch_name = branch_components[0]
                branch_number = int(branch_name[6:])
                joint_number = int(branch_components[1])
                if (branch_number > highest_branch_number):
                    highest_branch_number = branch_number
                    if (joint_number > highest_joint_number):
                        highest_joint_number = joint_number
    if (highest_branch_number != 0):
        if (is_new_branch):
            return ("branch%s_1" % (highest_branch_number + 1))
        else:
            return ("branch%s_%s" % (highest_branch_number, highest_joint_number + 1))
    else:
        return "branch1_1"

#------------------------------------------------------------------------------
# CryEngine User-Defined Properties
#------------------------------------------------------------------------------

# Rendermesh:
class AddMassProperty(bpy.types.Operator):
    '''Click to add a mass value.'''
    bl_label = "Mass"
    bl_idname = "object.add_mass_property"
    mass = FloatProperty(name="Mass")

    def execute(self, context):
        message = "Adding Mass of %s" % (self.mass)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_mass_property(self, context, self.mass)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddDensityProperty(bpy.types.Operator):
    '''Click to add a density value.'''
    bl_label = "Density"
    bl_idname = "object.add_density_property"
    density = FloatProperty(name="Density")

    def execute(self, context):
        message = "Adding Density of %s" % (self.density)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_density_property(self, context, self.density)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddPiecesProperty(bpy.types.Operator):
    '''Click to add a pieces value.'''
    bl_label = "Pieces"
    bl_idname = "object.add_pieces_property"
    pieces = FloatProperty(name="Pieces")

    def execute(self, context):
        message = "Adding %s Pieces" % (self.pieces)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_pieces_property(self, context, self.pieces)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddEntityProperty(bpy.types.Operator):
    '''Click to add an entity property.'''
    bl_label = "Entity"
    bl_idname = "object.add_entity_property"

    def execute(self, context):
        message = "Adding Entity Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_entity_property(self, context)


class AddDynamicProperty(bpy.types.Operator):
    '''Click to add a dynamic property.'''
    bl_label = "Dynamic"
    bl_idname = "object.add_dynamic_property"

    def execute(self, context):
        message = "Adding Dynamic Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_dynamic_property(self, context)


class AddNoHitRefinementProperty(bpy.types.Operator):
    '''Click to add a no hit refinement property.'''
    bl_label = "No Hit Refinement"
    bl_idname = "object.add_no_hit_refinement_property"

    def execute(self, context):
        message = "Adding No Hit Refinement Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_no_hit_refinement_property(self, context)


# Phys Proxy:
class AddBoxProxyProperty(bpy.types.Operator):
    '''Click to add a box proxy.'''
    bl_label = "Box"
    bl_idname = "object.add_box_proxy_property"

    def execute(self, context):
        message = "Adding Box Proxy Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_box_proxy_property(self, context)


class AddCylinderProxyProperty(bpy.types.Operator):
    '''Click to add a cylinder proxy.'''
    bl_label = "Cylinder"
    bl_idname = "object.add_cylinder_proxy_property"

    def execute(self, context):
        message = "Adding Cylinder Proxy Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_cylinder_proxy_property(self, context)


class AddCapsuleProxyProperty(bpy.types.Operator):
    '''Click to add a capsule proxy.'''
    bl_label = "Capsule"
    bl_idname = "object.add_capsule_proxy_property"

    def execute(self, context):
        message = "Adding Capsule Proxy Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_capsule_proxy_property(self, context)


class AddSphereProxyProperty(bpy.types.Operator):
    '''Click to add a sphere proxy.'''
    bl_label = "Sphere"
    bl_idname = "object.add_sphere_proxy_property"

    def execute(self, context):
        message = "Adding Sphere Proxy Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_sphere_proxy_property(self, context)


class AddNotaprimProxyProperty(bpy.types.Operator):
    '''Click to add a 'not a primitive' proxy property.'''
    bl_label = "Not a Primitive"
    bl_idname = "object.add_notaprim_proxy_property"

    def execute(self, context):
        message = "Adding 'Not a Primitive' Proxy Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_notaprim_proxy_property(self, context)


class AddNoExplosionOcclusionProperty(bpy.types.Operator):
    '''Click to add a no explosion occlusion property.'''
    bl_label = "No Explosion Occlusion"
    bl_idname = "object.add_no_explosion_occlusion_property"

    def execute(self, context):
        message = "Adding No Explosion Occlusion Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_no_explosion_occlusion_property(self, context)


class AddOtherRendermeshProperty(bpy.types.Operator):
    '''Click to add an other rendermesh property.'''
    bl_label = "Other Rendermesh"
    bl_idname = "object.add_other_rendermesh_property"

    def execute(self, context):
        message = "Adding Other Rendermesh Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_other_rendermesh_property(self, context)


class AddColltypePlayerProperty(bpy.types.Operator):
    '''Click to add a colltype player property.'''
    bl_label = "Colltype Player"
    bl_idname = "object.add_colltype_player_property"

    def execute(self, context):
        message = "Adding Colltype Player Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_colltype_player_property(self, context)


# Joint Node:
class AddBendProperty(bpy.types.Operator):
    '''Click to add a bend property.'''
    bl_label = "Bend"
    bl_idname = "object.add_bend_property"
    bendValue = FloatProperty(name="Bend Value")

    def execute(self, context):
        message = "Adding Bend Value of %s" % (self.bendValue)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_bend_property(self, context, self.bendValue)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddTwistProperty(bpy.types.Operator):
    '''Click to add a twist property.'''
    bl_label = "Twist"
    bl_idname = "object.add_twist_property"
    twistValue = FloatProperty(name="Twist Value")

    def execute(self, context):
        message = "Adding Twist Value of %s" % (self.twistValue)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_twist_property(self, context, self.twistValue)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddPullProperty(bpy.types.Operator):
    '''Click to add a pull property.'''
    bl_label = "Pull"
    bl_idname = "object.add_pull_property"
    pullValue = FloatProperty(name="Pull Value")

    def execute(self, context):
        message = "Adding Pull Value of %s" % (self.pullValue)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_pull_property(self, context, self.pullValue)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddPushProperty(bpy.types.Operator):
    '''Click to add a push property.'''
    bl_label = "Push"
    bl_idname = "object.add_push_property"
    pushValue = FloatProperty(name="Push Value")

    def execute(self, context):
        message = "Adding Push Value of %s" % (self.pushValue)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_push_property(self, context, self.pushValue)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddShiftProperty(bpy.types.Operator):
    '''Click to add a shift property.'''
    bl_label = "Shift"
    bl_idname = "object.add_shift_property"
    shiftValue = FloatProperty(name="Shift Value")

    def execute(self, context):
        message = "Adding Shift Value of %s" % (self.shiftValue)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_shift_property(self, context, self.shiftValue)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddGameplayCriticalProperty(bpy.types.Operator):
    '''Click to add a critical property.'''
    bl_label = "Gameplay Critical"
    bl_idname = "object.add_gameplay_critical_property"

    def execute(self, context):
        message = "Adding Gameplay Critical Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_gameplay_critical_property(self, context)


class AddPlayerCanBreakProperty(bpy.types.Operator):
    '''Click to add a breakable property.'''
    bl_label = "Player Can Break"
    bl_idname = "object.add_player_can_break_property"

    def execute(self, context):
        message = "Adding Player Can Break Property"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_player_can_break_property(self, context)


# Constraints:
class AddLimitConstraint(bpy.types.Operator):
    '''Click to add a limit constraint.'''
    bl_label = "Limit"
    bl_idname = "object.add_limit_constraint"
    limit = FloatProperty(name="Limit")

    def execute(self, context):
        message = "Adding Limit of %s" % (self.limit)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_limit_constraint(self, context, self.limit)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddMinAngleConstraint(bpy.types.Operator):
    '''Click to add a min angle constraint.'''
    bl_label = "Min Angle"
    bl_idname = "object.add_min_angle_constraint"
    minAngle = FloatProperty(name="Min Angle")

    def execute(self, context):
        message = "Adding Min Angle of %s" % (self.minAngle)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_min_angle_constraint(self, context, self.minAngle)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class AddMaxAngleConstraint(bpy.types.Operator):
    '''Click to add a max angle constraint.'''
    bl_label = "Max Angle"
    bl_idname = "object.add_max_angle_constraint"
    maxAngle = FloatProperty(name="Max Angle")

    def execute(self, context):
        message = "Adding Max Angle of %s" % (self.maxAngle)
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_max_angle_constraint(self, context, self.maxAngle)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddDampingConstraint(bpy.types.Operator):
    '''Click to add a damping constraint.'''
    bl_label = "Damping"
    bl_idname = "object.add_damping_constraint"

    def execute(self, context):
        message = "Adding Damping Constraint"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_damping_constraint(self, context)


class AddCollisionConstraint(bpy.types.Operator):
    '''Click to add a collision constraint.'''
    bl_label = "Collision"
    bl_idname = "object.add_collision_constraint"

    def execute(self, context):
        message = "Adding Collision Constraint"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_collision_constraint(self, context)


# Deformables:
class AddDeformableProperties(bpy.types.Operator):
    '''Click to add a deformable mesh property.'''
    bl_label = "Deformable"
    bl_idname = "object.add_deformable_properties"
    mass = FloatProperty(name="Mass")
    stiffness = FloatProperty(name="Stiffness")
    hardness = FloatProperty(name="Hardness")
    max_stretch = FloatProperty(name="Max Stretch")
    max_impulse = FloatProperty(name="Max Impulse")
    skin_dist = FloatProperty(name="Skin Distance")
    thickness = FloatProperty(name="Thickness")
    explosion_scale = FloatProperty(name="Explosion Scale")
    is_primitive = EnumProperty(
        name="Primitive?",
        description="",
        items=(
            ("Yes", "Yes", "Is a primitive"),
            ("No", "No", "Not a primitive"),
        ),
        default="No",
    )

    def execute(self, context):
        message = "Adding Deformable Properties"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_deformable_properties(self, context, self.mass, self.stiffness, self.hardness,
        self.max_stretch, self.max_impulse, self.skin_dist, self.thickness, self.explosion_scale, self.is_primitive)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


# Vehicles:
class AddWheelProperty(bpy.types.Operator):
    '''Click to add a wheels property.'''
    bl_label = "Add Wheel Properties"
    bl_idname = "object.add_wheel_property"

    def execute(self, context):
        message = "Adding Wheel Properties"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_wheel_property(self, context)


class FixWheelTransforms(bpy.types.Operator):
    bl_label = "Fix Wheel Transforms"
    bl_idname = "object.fix_wheel_transforms"

    def execute(self, context):
        ob = bpy.context.active_object
        ob.location.x = (ob.bound_box[0][0] + ob.bound_box[1][0]) / 2.0
        ob.location.y = (ob.bound_box[2][0] + ob.bound_box[3][0]) / 2.0
        ob.location.z = (ob.bound_box[4][0] + ob.bound_box[5][0]) / 2.0

        return {'FINISHED'}

#------------------------------------------------------------------------------
# Material Physics
#------------------------------------------------------------------------------

class AddMaterialPhysDefault(bpy.types.Operator):
    '''__physDefault will be added to the material name.'''
    bl_label = "__physDefault"
    bl_idname = "material.add_phys_default"

    def execute(self, context):
        message = "Adding __physDefault"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_phys_default(self, context)


class AddMaterialPhysProxyNoDraw(bpy.types.Operator):
    '''__physProxyNoDraw will be added to the material name.'''
    bl_label = "Add __physProxyNoDraw to Material Name"
    bl_idname = "material.add_phys_proxy_no_draw"

    def execute(self, context):
        message = "Adding __physProxyNoDraw"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_phys_proxy_no_draw(self, context)


class AddMaterialPhysNone(bpy.types.Operator):
    '''__physNone will be added to the material name.'''
    bl_label = "__physNone"
    bl_idname = "material.add_phys_none"

    def execute(self, context):
        message = "Adding __physNone"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_phys_none(self, context)


class AddMaterialPhysObstruct(bpy.types.Operator):
    '''__physObstruct will be added to the material name.'''
    bl_label = "__physObstruct"
    bl_idname = "material.add_phys_obstruct"

    def execute(self, context):
        return add.add_phys_obstruct(self, context)


class AddMaterialPhysNoCollide(bpy.types.Operator):
    '''__physNoCollide will be added to the material name.'''
    bl_label = "__physNoCollide"
    bl_idname = "material.add_phys_no_collide"

    def execute(self, context):
        message = "Adding __physNoCollide"
        self.report({'INFO'}, message)
        cbPrint(message)
        return add.add_phys_no_collide(self, context)

#------------------------------------------------------------------------------
# Mesh Repair Tools
#------------------------------------------------------------------------------

class FindDegenerateFaces(bpy.types.Operator):
    '''Select the object to test in object mode with nothing selected in \
it's mesh before running this.'''
    bl_label = "Find Degenerate Faces"
    bl_idname = "object.find_degenerate_faces"

    # Minimum face area to be considered non-degenerate
    area_epsilon = 0.000001

    def execute(self, context):
        # Deselect any vertices prevously selected in Edit mode
        saved_mode = bpy.context.object.mode
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action = 'DESELECT')

        ''' Vertices data should be actually manipulated in Object mode
            to be displayed in Edit mode correctly.'''
        bpy.ops.object.mode_set(mode='OBJECT')
        me = bpy.context.active_object

        vert_list = [vert for vert in me.data.vertices]
        context.tool_settings.mesh_select_mode = (True, False, False)
        cbPrint("Locating degenerate faces.")
        degenerate_count = 0



        for poly in me.data.polygons:
            if poly.area < self.area_epsilon:
                cbPrint("Found a degenerate face.")
                degenerate_count += 1

                for v in poly.vertices:
                    cbPrint("Selecting face vertices.")
                    vert_list[v].select = True

        if degenerate_count > 0:
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'WARNING'},
                        "Found %i degenerate faces" % degenerate_count)
        else:
            self.report({'INFO'}, "No degenerate faces found")
            # Restore the original mode
            bpy.ops.object.mode_set(mode=saved_mode)

        return {'FINISHED'}


# Duo Oratar
class FindMultifaceLines(bpy.types.Operator):
    '''Select the object to test in object mode with nothing selected in \
it's mesh before running this.'''
    bl_label = "Find Lines with 3+ Faces."
    bl_idname = "mesh.find_multiface_lines"

    def execute(self, context):
        me = bpy.context.active_object
        vert_list = [vert for vert in me.data.vertices]
        context.tool_settings.mesh_select_mode = (True, False, False)
        bpy.ops.object.mode_set(mode='OBJECT')
        cbPrint("Locating degenerate faces.")
        for i in me.data.edges:
            counter = 0
            for polygon in me.data.polygons:
                if (i.vertices[0] in polygon.vertices
                    and i.vertices[1] in polygon.vertices):
                    counter += 1
            if counter > 2:
                cbPrint('Found a multi-face line')
                for v in i.vertices:
                    cbPrint('Selecting line vertices.')
                    vert_list[v].select = True
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class FindWeightless(bpy.types.Operator):
    '''Select the object in object mode with nothing in its mesh selected \
before running this'''
    bl_label = "Find Weightless Vertices"
    bl_idname = "mesh.find_weightless"

    # Minimum net weight to be considered non-weightless
    weight_epsilon = 0.0001

    # Weightless: a vertex not belonging to any groups or with a net weight of 0
    def execute(self, context):
        obj = bpy.context.active_object
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        if obj.type == "MESH":
            for v in obj.data.vertices:
                if (not v.groups):
                    v.select = True
                else:
                    weight = 0
                    for g in v.groups:
                        weight += g.weight
                    if (weight < self.weight_epsilon):
                        v.select = True
        obj.data.update()
        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}


class RemoveAllWeight(bpy.types.Operator):
        '''Select vertices from which to remove weight in edit mode.'''
        bl_label = "Remove All Weight from Selected Vertices"
        bl_idname = "mesh.remove_weight"

        def execute(self, context):
            obj = bpy.context.active_object
            if obj.type == 'MESH':
                verts = []
                for v in obj.data.vertices:
                    if v.select:
                        verts.append(v)
                for v in verts:
                    for g in v.groups:
                        g.weight = 0
            return {'FINISHED'}


class FindNoUVs(bpy.types.Operator):
        '''Use this with no objects selected in object mode \
to find all items without UVs.'''
        bl_label = "Find All Objects with No UV's"
        bl_idname = "scene.find_no_uvs"

        def execute(self, context):
            for obj in bpy.data.objects:
                obj.select = False

            for obj in bpy.context.selectable_objects:
                if obj.type == 'MESH':
                    a = False
                    # TODO: WTF?
                    for i in obj.data.uv_textures:
                        a = True
                        break
                    if not a:
                        obj.select = True
            return {'FINISHED'}


class AddUVTexture(bpy.types.Operator):
        '''Add UVs to all meshes without UVs.'''
        bl_label = "Add UV's to Objects"
        bl_idname = "mesh.add_uv_texture"

        def execute(self, context):
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    uv = False
                    for i in obj.data.uv_textures:
                        uv = True
                        break
                    if not uv:
                        bpy.context.scene.objects.active = obj
                        bpy.ops.mesh.uv_texture_add()
                        message = "Added UV map to {}".format(obj.name)
                        self.report({'INFO'}, message)
                        cbPrint(message)
            return {'FINISHED'}

#------------------------------------------------------------------------------
# Bone Utilities
#------------------------------------------------------------------------------

class AddRootBone(bpy.types.Operator):
    '''Click to add a root bone to the active armature.'''
    bl_label = "Add Root Bone"
    bl_idname = "armature.add_root_bone"

    def execute(self, context):
        active = bpy.context.active_object
        if active is not None:
            if active.type == "ARMATURE":
                if utils.count_root_bones(active) == 1:
                    root_bone = utils.get_root_bone(active)
                    loc = root_bone.head
                    if loc.x == 0 and loc.y == 0 and loc.z == 0:
                        message = "Root bone already exists."
                        self.report({'INFO'}, message)
                        return {'FINISHED'}
                message = "Adding root bone to armature."
                old_mode = bpy.context.object.mode
                bpy.ops.object.mode_set(mode="EDIT")
                edit_bones = active.data.edit_bones
                bpy.ops.armature.bone_primitive_add(name="root")
                root_bone = edit_bones["root"]
                bpy.ops.armature.select_all(action="DESELECT")
                for edit_bone in edit_bones:
                    if edit_bone.parent is None:
                        edit_bone.parent = root_bone
                bpy.ops.object.mode_set(mode="OBJECT")
            else:
                message = "Object is not an armature."
        else:
            message = "No Object Selected."
        self.report({'INFO'}, message)
        return {'FINISHED'}


class AddBoneGeometry(bpy.types.Operator):
    '''Add BoneGeometry for bones in selected armatures.'''
    bl_label = "Add BoneGeometry"
    bl_idname = "armature.add_bone_geometry"
    bl_options = {'REGISTER', 'UNDO'}

    view_align = BoolProperty(
            name="Align to View",
            default=False,
            )
    location = FloatVectorProperty(
            name="Location",
            subtype='TRANSLATION',
            )
    rotation = FloatVectorProperty(
            name="Rotation",
            subtype='EULER',
            )

    def draw(self, context):
        col = self.col
        col.label(text="Add boneGeometry")

    def execute(self, context):
        verts_loc, faces = add_bone_geometry()

        nameList = []
        for obj in bpy.context.scene.objects:
            nameList.append(obj.name)

        for obj in bpy.context.scene.objects:
            if obj.type == 'ARMATURE' and obj.select:

                physBonesList = []
                if "%s_Phys" % obj.name in nameList:
                    for bone in bpy.data.objects["%s_Phys" % obj.name].data.bones:
                        physBonesList.append(bone.name)

                for bone in obj.data.bones:
                    if ((not "%s_boneGeometry" % bone.name in nameList
                            and not "%s_Phys" % obj.name in nameList)
                        or ("%s_Phys" % obj.name in nameList
                            and "%s_Phys" % bone.name in physBonesList
                            and not "%s_boneGeometry" % bone.name in nameList)
                        ):
                        mesh = bpy.data.meshes.new(
                                    "%s_boneGeometry" % bone.name
                        )
                        bm = bmesh.new()

                        for v_co in verts_loc:
                            bm.verts.new(v_co)

                        for f_idx in faces:
                            bm.faces.new([bm.verts[i] for i in f_idx])

                        bm.to_mesh(mesh)
                        mesh.update()
                        bmatrix = bone.head_local
                        # loc, rotation, scale = bmatrix.decompose()
                        self.location[0] = bmatrix[0]
                        self.location[1] = bmatrix[1]
                        self.location[2] = bmatrix[2]
                        # add the mesh as an object into the scene
                        # with this utility module
                        from bpy_extras import object_utils
                        object_utils.object_data_add(
                            context, mesh, operator=self
                        )
                        bpy.ops.mesh.uv_texture_add()

        return {'FINISHED'}


def add_bone_geometry():
    """
    This function takes inputs and returns vertex and face arrays.
    No actual mesh data creation is done here.
    """

    verts = [(-0.5, -0.5, -0.5),
             (-0.5, 0.5, -0.5),
             (0.5, 0.5, -0.5),
             (0.5, -0.5, -0.5),
             (-0.5, -0.5, 0.5),
             (-0.5, 0.5, 0.5),
             (0.5, 0.5, 0.5),
             (0.5, -0.5, 0.5),
             ]

    faces = [(0, 1, 2, 3),
             (4, 7, 6, 5),
             (0, 4, 5, 1),
             (1, 5, 6, 2),
             (2, 6, 7, 3),
             (4, 0, 3, 7),
            ]

    return verts, faces


class RemoveBoneGeometry(bpy.types.Operator):
    '''Remove BoneGeometry for bones in selected armatures'''
    bl_label = "Remove BoneGeometry"
    bl_idname = "armature.remove_bone_geometry"
    bl_options = {'REGISTER', 'UNDO'}

    view_align = BoolProperty(
            name="Align to View",
            default=False,
            )
    location = FloatVectorProperty(
            name="Location",
            subtype='TRANSLATION',
            )
    rotation = FloatVectorProperty(
            name="Rotation",
            subtype='EULER',
            )

    def draw(self, context):
        col = self.col
        col.label(text="Remove boneGeometry")

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')

        armatureList = []  # Get list of armatures requiring attention
        for obj in bpy.context.scene.objects:
            if obj.type == 'ARMATURE' and obj.select:  # Get selected armatures
                armatureList.append(obj.name)

        nameList = []  # Get list of objects
        for obj in bpy.context.scene.objects:
            nameList.append(obj.name)
            obj.select = False

        for name in armatureList:
            obj = bpy.context.scene.objects[name]
            physBonesList = []
            # Get list of phys bones in matching phys skel
            if "%s_Phys" % obj.name in nameList:
                for bone in bpy.data.objects["%s_Phys" % obj.name].data.bones:
                    physBonesList.append(bone.name)

            for bone in obj.data.bones:  # For each bone
                if "%s_boneGeometry" % bone.name in nameList:
                    bpy.data.objects["%s_boneGeometry" % bone.name].select = True

            bpy.ops.object.delete()

        return {'FINISHED'}


# Duo Oratar
class RenamePhysBones(bpy.types.Operator):
    '''Renames bones with _Phys extension.'''
    bl_label = "Rename Phys Bones"
    bl_idname = "armature.rename_phys_bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in bpy.context.scene.objects:
            if ('_Phys' == obj.name[-5:]
                and obj.type == 'ARMATURE'):
                for bone in obj.data.bones:
                    bone.name = "%s_Phys" % bone.name

        return {'FINISHED'}

#------------------------------------------------------------------------------
# Scripting Module
#------------------------------------------------------------------------------

class SelectScriptEditor(bpy.types.Operator, PathSelectTemplate):
    '''Select a text editor of your choice to open scripts (i.e., notepad++.exe)'''

    bl_label = "Select Script/Text Editor"
    bl_idname = "file.select_script_editor"

    filename_ext = ".exe"
    filter_glob = StringProperty(default="*.exe", options={'HIDDEN'})

    def process(self, filepath):
        Configuration.script_editor = filepath

    def invoke(self, context, event):
        self.filepath = Configuration.script_editor

        return ExportHelper.invoke(self, context, event)


class GenerateScript(bpy.types.Operator, PathSelectTemplate):
    bl_label = "Generate Script"
    bl_idname = "wm.generate_script"

    filename_ext = ""
    filter_glob = StringProperty(options={'HIDDEN'})

    type_ = StringProperty(options={'HIDDEN'})
    entries = IntProperty(name="Entries", min=1, default=1)

    def process(self, filepath):
        if (getattr(self, "type_") == "CHRPARAMS"):
            self.generate_chrparams(filepath, self.entries)
        elif (getattr(self, "type_") == "CDF"):
            self.generate_cdf(filepath, self.entries)
        elif (getattr(self, "type_") == "ENT"):
            self.generate_ent(filepath)
        elif (getattr(self, "type_") == "LUA"):
            self.generate_lua(filepath)

    def invoke(self, context, event):
        if (getattr(self, "type_") == "CHRPARAMS"):
            self.filename_ext = ".chrparams"
            self.filter_glob = "*.chrparams"
        elif (getattr(self, "type_") == "CDF"):
            self.filename_ext = ".cdf"
            self.filter_glob = "*.cdf"
        elif (getattr(self, "type_") == "ENT"):
            self.filename_ext = ".ent"
            self.filter_glob = "*.ent"
        elif (getattr(self, "type_") == "LUA"):
            self.filename_ext = ".lua"
            self.filter_glob = "*.lua"
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        if (getattr(self, "type_") == "CHRPARAMS" or
                getattr(self, "type_") == "CDF"):
            layout.prop(self, "entries")

    def generate_chrparams(self, filepath, entries):
        contents = """<Params>\
<AnimationList>\
</AnimationList>\
</Params>"""
        script = parseString(contents)

        animation_list = script.getElementsByTagName("AnimationList")[0]
        animation = parseString("""<Animation name="???" path="???.caf"/>""").getElementsByTagName("Animation")[0]
        for index in range(0, entries):
            animation_list.appendChild(animation.cloneNode(deep=False))
        contents = script.toprettyxml(indent="\t")

        self.generate_file(filepath, contents)

    def generate_cdf(self, filepath, entries):
        contents = """<CharacterDefinition>\
<Model File="???.chr" Material="???"/>\
<AttachmentList>\
</AttachmentList>\
<ShapeDeformation COL0="0" COL1="0" COL2="0" COL3="0" COL4="0" COL5="0" COL6="0" COL7="0"/>\
</CharacterDefinition>"""

        script = parseString(contents)

        attachment_list = script.getElementsByTagName("AttachmentList")[0]
        attachment = parseString("""<Attachment AName="???" Type="CA_SKIN" Rotation="1,0,0,0" Position="0,0,0" \
                                    BoneName="" Binding="???.chr" Flags="0"/>""").getElementsByTagName("Attachment")[0]
        for index in range(0, entries):
            attachment_list.appendChild(attachment.cloneNode(deep=False))
        contents = script.toprettyxml(indent="\t")

        self.generate_file(filepath, contents)

    def generate_ent(self, filepath):
        contents = """<?xml version="1.0" ?>
<Entity
\tName="???"
\tScript="Scripts/Entities/???.lua"
/>
"""

        self.generate_file(filepath, contents)

    def generate_lua(self, filepath):
        contents = ""

        self.generate_file(filepath, contents)

    def generate_file(self, filepath, contents):
        file = open(filepath, "w")
        file.write(contents)
        file.close()

        message="Please select a text editor .exe such as Notepad or Notepad++.\n\
This will be used as the default program for opening scripts."
        if (len(Configuration.script_editor) == 0):
            try:
                os.startfile(filepath)
            except:
                bpy.ops.screen.display_error('INVOKE_DEFAULT', message=message)
        else:
            try:
                process = subprocess.Popen([Configuration.script_editor, filepath])
            except:
                bpy.ops.screen.display_error('INVOKE_DEFAULT', message=message)

#------------------------------------------------------------------------------
# Export Handler
#------------------------------------------------------------------------------

class Export(bpy.types.Operator, ExportHelper):
    '''Select to export to game.'''
    bl_label = "Export to Game"
    bl_idname = "scene.export_to_game"
    filename_ext = ".dae"
    filter_glob = StringProperty(default="*.dae", options={'HIDDEN'})

    apply_modifiers = BoolProperty(
            name="Apply Modifiers",
            description="Apply all modifiers before exporting.",
            default=True,
            )
    donot_merge = BoolProperty(
            name="Do Not Merge Nodes",
            description="Generally a good idea.",
            default=True,
            )
    do_materials = BoolProperty(
            name="Do Materials",
            description="Create MTL files for materials.",
            default=True,
            )
    convert_source_image_to_dds = BoolProperty(
            name="Convert Textures to DDS",
            description="Converts source textures to DDS while exporting materials.",
            default=False,
            )
    save_tiff_during_conversion = BoolProperty(
            name="Save TIFF During Conversion",
            description="Saves TIFF images that are generated during conversion to DDS.",
            default=False,
            )
    make_chrparams = BoolProperty(
            name="Make CHRPARAMS File",
            description="Create a base CHRPARAMS file for character animations.",
            default=False,
            )
    make_cdf = BoolProperty(
            name="Make CDF File",
            description="Create a base CDF file for character attachments.",
            default=False,
            )
    include_ik = BoolProperty(
            name="Include IK in Character",
            description="Add IK to the physics skeleton upon export.",
            default=False,
            )
    fix_weights = BoolProperty(
            name="Fix Weights",
            description="For use with .chr files. Generally a good idea.",
            default=True,
            )
    average_planar = BoolProperty(
            name="Average Planar Face Normals",
            description="Align face normals within 1 degree of each other.",
            default=False,
            )
    make_layer = BoolProperty(
            name="Make LYR File",
            description="Makes a LYR to reassemble your scene in CryEngine.",
            default=False,
            )
    disable_rc = BoolProperty(
            name="Disable RC",
            description="Do not run the resource compiler.",
            default=False,
            )
    save_dae = BoolProperty(
            name="Save DAE File",
            description="Save the DAE file for developing purposes.",
            default=False,
            )
    run_in_profiler = BoolProperty(
            name="Profile CryBlend",
            description="Select only if you want to profile CryBlend.",
            default=False,
            )

    class Config:
        def __init__(self, config):
            attributes = (
                'filepath',
                'apply_modifiers',
                'donot_merge',
                'do_materials',
                'convert_source_image_to_dds',
                'save_tiff_during_conversion',
                'make_chrparams',
                'make_cdf',
                'include_ik',
                'fix_weights',
                'average_planar',
                'make_layer',
                'disable_rc',
                'save_dae',
                'run_in_profiler'
            )

            for attribute in attributes:
                setattr(self, attribute, getattr(config, attribute))

            setattr(self, 'cryblend_version', VERSION)
            setattr(self, 'rc_path', Configuration.rc_path)
            setattr(self, 'rc_for_textures_conversion_path',
                    Configuration.rc_for_texture_conversion_path)
            setattr(self, 'textures_dir', Configuration.textures_directory)

    def execute(self, context):
        cbPrint(Configuration.rc_path, 'debug')
        try:
            config = Export.Config(config=self)

            if self.run_in_profiler:
                import cProfile
                cProfile.runctx('export.save(config)', {},
                                {'export': export, 'config': config})
            else:
                export.save(config)

            self.filepath = '//'

        except exceptions.CryBlendException as exception:
            cbPrint(exception.what(), 'error')
            bpy.ops.screen.display_error('INVOKE_DEFAULT', message=exception.what())

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        box = col.box()
        box.label("General", icon="WORLD")
        box.prop(self, "apply_modifiers")
        box.prop(self, "donot_merge")

        box = col.box()
        box.label("Image and Material", icon="TEXTURE")
        box.prop(self, "do_materials")
        box.prop(self, "convert_source_image_to_dds")
        box.prop(self, "save_tiff_during_conversion")

        box = col.box()
        box.label("Character", icon="ARMATURE_DATA")
        box.prop(self, "make_chrparams")
        box.prop(self, "make_cdf")
        box.prop(self, "include_ik")

        box = col.box()
        box.label("Corrective", icon="BRUSH_DATA")
        box.prop(self, "fix_weights")
        box.prop(self, "average_planar")

        box = col.box()
        box.label("CryEngine Editor", icon="OOPS")
        box.prop(self, "make_layer")

        box = col.box()
        box.label("Developer Tools", icon="MODIFIER")
        box.prop(self, "disable_rc")
        box.prop(self, "save_dae")
        box.prop(self, "run_in_profiler")


class ErrorHandler(bpy.types.Operator):
    bl_label = "Error:"
    bl_idname = "screen.display_error"

    message = bpy.props.StringProperty()

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(self.bl_label, icon='ERROR')
        col.split()
        multiline_label(col, self.message)
        col.split()
        col.split(0.2)


def multiline_label(col, text):
    for line in text.splitlines():
        row = col.split()
        row.label(line)

#------------------------------------------------------------------------------
# CryBlend Tab
#------------------------------------------------------------------------------

class PropPanel():
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render_layer"
    COMPAT_ENGINES = {"BLENDER_RENDER"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene and (scene.render.engine in cls.COMPAT_ENGINES)


class View3DPanel():
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "CryBlend"


class ExportUtilitiesPanel(View3DPanel, Panel):
    bl_label = "Export Utilities"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label("ExportNodes", icon="GROUP")
        col.separator()
        row = col.row(align=True)
        row.operator("object.add_cry_export_node", text="Add ExportNode")
        col.operator("object.selected_to_cry_export_nodes", text="ExportNodes from Objects")
        col.separator()
        col.operator("object.apply_transforms", text="Apply All Transforms")


class CryUtilitiesPanel(View3DPanel, Panel):
    bl_label = "Cry Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label("Materials", icon="MATERIAL")
        col.separator()
        col.operator("material.set_material_names", text="Do Material Convention")
        col.operator("material.remove_cry_blend_properties", text="Undo Material Convention")
        col.separator()

        col.label("Add Physics Proxy", icon="ROTATE")
        col.separator()
        row = col.row(align=True)
        add_box_proxy = row.operator("object.add_proxy", text="Box")
        add_box_proxy.type_ = "box"
        add_capsule_proxy = row.operator("object.add_proxy", text="Capsule")
        add_capsule_proxy.type_ = "capsule"

        row = col.row(align=True)
        add_cylinder_proxy = row.operator("object.add_proxy", text="Cylinder")
        add_cylinder_proxy.type_ = "cylinder"
        add_sphere_proxy = row.operator("object.add_proxy", text="Sphere")
        add_sphere_proxy.type_ = "sphere"
        col.separator()

        col.label("Breakables:", icon="PARTICLES")
        col.separator()
        col.operator("object.add_joint", text="Add Joint")
        col.separator()

        col.label("Touch Bending:", icon="OUTLINER_OB_EMPTY")
        col.separator()
        col.operator("mesh.add_branch", text="Add Branch")
        col.operator("mesh.add_branch_joint", text="Add Branch Joint")


class BoneUtilitiesPanel(View3DPanel, Panel):
    bl_label = "Bone Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label("Skeleton", icon="BONE_DATA")
        col.separator()
        col.operator("armature.add_root_bone", text="Add Root Bone")
        col.separator()
        col.label("Physics", icon="PHYSICS")
        col.separator()
        col.operator("armature.add_bone_geometry", text="Add BoneGeometry")
        col.operator("armature.remove_bone_geometry", text="Remove BoneGeometry")
        col.operator("armature.rename_phys_bones", text="Rename Phys Bones")


class MeshUtilitiesPanel(View3DPanel, Panel):
    bl_label = "Mesh Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label(text="Weight Repair", icon="WPAINT_HLT")
        col.separator()
        col.operator("mesh.find_weightless", text="Find Weightless")
        col.operator("mesh.remove_weight", text="Remove Weight")
        col.separator()

        col.label(text="Mesh Repair", icon='ZOOM_ALL')
        col.separator()
        col.operator("object.find_degenerate_faces", text="Find Degenerate")
        col.operator("mesh.find_multiface_lines", text="Find Multi-face")
        col.separator()

        col.label(text="UV Repair", icon="UV_FACESEL")
        col.separator()
        col.operator("scene.find_no_uvs", text="Find All Objects with No UV's")
        col.operator("mesh.add_uv_texture", text="Add UV's to Objects")


class CustomPropertiesPanel(View3DPanel, Panel):
    bl_label = "Custom Properties"

    def draw(self, context):
        layout = self.layout

        layout.label("Properties:", icon="SCRIPT")
        layout.menu("menu.add_property", text="Add Property")


class ConfigurationsPanel(View3DPanel, Panel):
    bl_label = "Configurations"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label("Configure", icon="NEWFOLDER")
        col.separator()
        col.operator("file.find_rc", text="Find RC")
        col.operator("file.find_rc_for_texture_conversion", text="Find Texture RC")
        col.separator()
        col.operator("file.select_textures_directory", text="Select Textures Folder")

#------------------------------------------------------------------------------
# CryBlend Menus
#------------------------------------------------------------------------------

class CryBlendMainMenu(bpy.types.Menu):
    bl_label = 'CryBlend'
    bl_idname = 'view3d.cryblend_main_menu'

    def draw(self, context):
        layout = self.layout

        # version number
        layout.label(text='v%s' % VERSION)
        # layout.operator("open_donate.wp", icon='FORCE_DRAG')
        layout.operator("object.add_cry_export_node", text="Add ExportNode", icon="GROUP")
        layout.operator("object.selected_to_cry_export_nodes", text="ExportNodes from Objects")
        layout.separator()
        layout.operator("material.set_material_names", text="Do Material Convention", icon="MATERIAL")
        layout.operator("material.remove_cry_blend_properties", text="Undo Material Convention")
        layout.separator()
        layout.operator("object.apply_transforms", text="Apply All Transforms", icon="MESH_DATA")
        layout.separator()

        layout.menu("menu.add_physics_proxy", icon="ROTATE")
        layout.separator()
        layout.menu(BoneUtilitiesMenu.bl_idname, icon='BONE_DATA')
        layout.separator()
        layout.menu(BreakablesMenu.bl_idname, icon='PARTICLES')
        layout.separator()
        layout.menu(TouchBendingMenu.bl_idname, icon='OUTLINER_OB_EMPTY')
        layout.separator()
        layout.menu(MeshUtilitiesMenu.bl_idname, icon='MESH_CUBE')
        layout.separator()
        layout.menu(CustomPropertiesMenu.bl_idname, icon='SCRIPT')
        layout.separator()
        layout.menu(GenerateScriptMenu.bl_idname, icon='TEXT')
        layout.separator()
        layout.menu(ConfigurationsMenu.bl_idname, icon='NEWFOLDER')

        layout.separator()
        layout.separator()
        layout.operator("scene.export_to_game", icon="GAME")


class AddPhysicsProxyMenu(bpy.types.Menu):
    bl_label = "Add Physics Proxy"
    bl_idname = "menu.add_physics_proxy"

    def draw(self, context):
        layout = self.layout

        layout.label("Proxies")
        add_box_proxy = layout.operator("object.add_proxy", text="Box", icon="META_CUBE")
        add_box_proxy.type_ = "box"
        add_capsule_proxy = layout.operator("object.add_proxy", text="Capsule", icon="META_ELLIPSOID")
        add_capsule_proxy.type_ = "capsule"
        add_cylinder_proxy = layout.operator("object.add_proxy", text="Cylinder", icon="META_CAPSULE")
        add_cylinder_proxy.type_ = "cylinder"
        add_sphere_proxy = layout.operator("object.add_proxy", text="Sphere", icon="META_BALL")
        add_sphere_proxy.type_ = "sphere"


class BoneUtilitiesMenu(bpy.types.Menu):
    bl_label = "Bone Utilities"
    bl_idname = "view3d.bone_utilities"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Skeleton")
        layout.operator("armature.add_root_bone", text="Add Root Bone", icon="BONE_DATA")
        layout.separator()

        layout.label(text="Physics")
        layout.operator("armature.add_bone_geometry", text="Add BoneGeometry", icon="PHYSICS")
        layout.operator("armature.remove_bone_geometry", text="Remove BoneGeometry", icon="PHYSICS")
        layout.operator("armature.rename_phys_bones", text="Rename Phys Bones", icon="PHYSICS")


class BreakablesMenu(bpy.types.Menu):
    bl_label = "Breakables"
    bl_idname = "view3d.breakables"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Breakables")
        layout.operator("object.add_joint", text="Add Joint", icon="PROP_ON")


class TouchBendingMenu(bpy.types.Menu):
    bl_label = "Touch Bending"
    bl_idname = "view3d.touch_bending"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Touch Bending")
        layout.operator("mesh.add_branch", text="Add Branch", icon='MOD_SIMPLEDEFORM')
        layout.operator("mesh.add_branch_joint", text="Add Branch Joint", icon='EMPTY_DATA')


class MeshUtilitiesMenu(bpy.types.Menu):
    bl_label = "Mesh Utilities"
    bl_idname = "view3d.mesh_utilities"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Weight Repair")
        layout.operator("mesh.find_weightless", text="Find Weightless", icon="WPAINT_HLT")
        layout.operator("mesh.remove_weight", text="Remove Weight", icon="WPAINT_HLT")
        layout.separator()

        layout.label(text="Mesh Repair")
        layout.operator("object.find_degenerate_faces", text="Find Degenerate", icon='ZOOM_ALL')
        layout.operator("mesh.find_multiface_lines", text="Find Multi-face", icon='ZOOM_ALL')
        layout.separator()

        layout.label(text="UV Repair")
        layout.operator("scene.find_no_uvs", text="Find All Objects with No UV's", icon="UV_FACESEL")
        layout.operator("mesh.add_uv_texture", text="Add UV's to Objects", icon="UV_FACESEL")


class CustomPropertiesMenu(bpy.types.Menu):
    bl_label = "Add Property"
    bl_idname = "menu.add_property"

    def draw(self, context):
        layout = self.layout

        row = layout.row()

        sub = row.column()
        sub.label("Rendermesh")
        sub.operator("object.add_mass_property", text="Mass", icon="FORCE_LENNARDJONES")
        sub.operator("object.add_density_property", text="Density", icon="BBOX")
        sub.operator("object.add_pieces_property", text="Pieces", icon="STICKY_UVS_DISABLE")
        sub.label(" ")
        sub.label(" ")
        sub.separator()
        sub.operator("object.add_entity_property", text="Entity", icon="FILE_TICK")
        sub.operator("object.add_dynamic_property", text="Dynamic", icon="FILE_TICK")
        sub.operator("object.add_no_hit_refinement_property", text="No Hit Refinement", icon="FILE_TICK")

        sub = row.column()
        sub.label("Physics Proxy")
        sub.operator("object.add_box_proxy_property", text="Box", icon="META_CUBE")
        sub.operator("object.add_cylinder_proxy_property", text="Cylinder", icon="META_CAPSULE")
        sub.operator("object.add_capsule_proxy_property", text="Capsule", icon="META_ELLIPSOID")
        sub.operator("object.add_sphere_proxy_property", text="Sphere", icon="META_BALL")
        sub.operator("object.add_notaprim_proxy_property", text="Not a Primitive", icon="X")
        sub.separator()
        sub.operator("object.add_no_explosion_occlusion_property", text="No Explosion Occlusion", icon="FILE_TICK")
        sub.operator("object.add_other_rendermesh_property", text="Other Rendermesh", icon="FILE_TICK")
        sub.operator("object.add_colltype_player_property", text="Colltype Player", icon="FILE_TICK")

        sub = row.column()
        sub.label("Joint Node")
        sub.operator("object.add_bend_property", text="Bend", icon="LINCURVE")
        sub.operator("object.add_twist_property", text="Twist", icon="MOD_SCREW")
        sub.operator("object.add_pull_property", text="Pull", icon="FULLSCREEN_ENTER")
        sub.operator("object.add_push_property", text="Push", icon="FULLSCREEN_EXIT")
        sub.operator("object.add_shift_property", text="Shift", icon="NEXT_KEYFRAME")
        sub.separator()
        sub.operator("object.add_gameplay_critical_property", text="Gameplay Critical", icon="FILE_TICK")
        sub.operator("object.add_player_can_break_property", text="Player Can Break", icon="FILE_TICK")

        sub = row.column()
        sub.label("Constraints")
        sub.operator("object.add_limit_constraint", text="Limit", icon="CONSTRAINT")
        sub.operator("object.add_min_angle_constraint", text="Min Angle", icon="ZOOMIN")
        sub.operator("object.add_max_angle_constraint", text="Max Angle", icon="ZOOMOUT")
        sub.label(" ")
        sub.label(" ")
        sub.separator()
        sub.operator("object.add_damping_constraint", text="Damping", icon="FILE_TICK")
        sub.operator("object.add_collision_constraint", text="Collision", icon="FILE_TICK")

        sub = row.column()
        sub.label("Other")
        sub.operator("object.add_deformable_properties", text="Deformable", icon="MOD_SIMPLEDEFORM")
        sub.operator("object.add_wheel_property", text="Wheel", icon="ROTATECOLLECTION")
        sub.label(" ")
        sub.label(" ")
        sub.label(" ")
        sub.separator()


class GenerateScriptMenu(bpy.types.Menu):
    bl_label = "Generate Script"
    bl_idname = "menu.generate_script"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Generate")
        layout.separator()
        chrparams_generator = layout.operator("wm.generate_script", text="CHRPARAMS", icon="SPACE2")
        chrparams_generator.type_ = "CHRPARAMS"
        cdf_generator = layout.operator("wm.generate_script", text="CDF", icon="SPACE2")
        cdf_generator.type_ = "CDF"
        ent_generator = layout.operator("wm.generate_script", text="ENT", icon="SPACE2")
        ent_generator.type_ = "ENT"
        lua_generator = layout.operator("wm.generate_script", text="LUA", icon="SPACE2")
        lua_generator.type_ = "LUA"
        layout.separator()
        layout.operator("file.select_script_editor", icon="TEXT")


class ConfigurationsMenu(bpy.types.Menu):
    bl_label = "Configurations"
    bl_idname = "view3d.configurations"

    def draw(self, context):
        layout = self.layout

        layout.label("Configure")
        layout.operator("file.find_rc", text="Find RC", icon="SPACE2")
        layout.operator("file.find_rc_for_texture_conversion", text="Find Texture RC", icon="SPACE2")
        layout.separator()
        layout.operator("file.select_textures_directory", text="Select Textures Folder", icon="FILE_FOLDER")


class AddMaterialPhysicsMenu(bpy.types.Menu):
    bl_label = "Add Material Physics"
    bl_idname = "menu.add_material_physics"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Add Material Physics")
        layout.separator()
        layout.operator("material.add_phys_default", text="__physDefault", icon='PHYSICS')
        layout.operator("material.add_phys_proxy_no_draw", text="__physProxyNoDraw", icon='PHYSICS')
        layout.operator("material.add_phys_none", text="__physNone", icon='PHYSICS')
        layout.operator("material.add_phys_obstruct", text="__physObstruct", icon='PHYSICS')
        layout.operator("material.add_phys_no_collide", text="__physNoCollide", icon='PHYSICS')


class CryBlendReducedMenu(bpy.types.Menu):
    bl_label = 'CryBlend'
    bl_idname = 'view3d.cryblend_reduced_menu'

    def draw(self, context):
        layout = self.layout

        layout.operator("object.apply_transforms", text="Apply All Transforms", icon="MESH_DATA")
        layout.separator()
        layout.menu("menu.add_physics_proxy", icon="ROTATE")
        layout.separator()
        layout.menu(BoneUtilitiesMenu.bl_idname, icon='BONE_DATA')
        layout.separator()
        layout.menu(BreakablesMenu.bl_idname, icon='PARTICLES')
        layout.separator()
        layout.menu(TouchBendingMenu.bl_idname, icon='OUTLINER_OB_EMPTY')
        layout.separator()
        layout.menu(MeshUtilitiesMenu.bl_idname, icon='MESH_CUBE')
        layout.separator()
        layout.menu(CustomPropertiesMenu.bl_idname, icon='SCRIPT')
        layout.separator()
 
#------------------------------------------------------------------------------
# Registration
#------------------------------------------------------------------------------

def get_classes_to_register():
    classes = (
        FindRC,
        FindRCForTextureConversion,
        SelectTexturesDirectory,
        SaveCryBlendConfiguration,

        AddCryExportNode,
        SelectedToCryExportNodes,
        SetMaterialNames,
        RemoveCryBlendProperties,
        AddRootBone,
        ApplyTransforms,
        AddProxy,
        AddBreakableJoint,
        AddBranch,
        AddBranchJoint,

        AddMassProperty,
        AddDensityProperty,
        AddPiecesProperty,
        AddEntityProperty,
        AddNoHitRefinementProperty,
        AddDynamicProperty,

        AddBoxProxyProperty,
        AddCylinderProxyProperty,
        AddCapsuleProxyProperty,
        AddSphereProxyProperty,
        AddNotaprimProxyProperty,
        AddNoExplosionOcclusionProperty,
        AddOtherRendermeshProperty,
        AddColltypePlayerProperty,

        AddBendProperty,
        AddTwistProperty,
        AddPullProperty,
        AddPushProperty,
        AddShiftProperty,
        AddGameplayCriticalProperty,
        AddPlayerCanBreakProperty,

        AddLimitConstraint,
        AddMinAngleConstraint,
        AddMaxAngleConstraint,
        AddDampingConstraint,
        AddCollisionConstraint,

        AddDeformableProperties,
        AddWheelProperty,
        FixWheelTransforms,

        AddMaterialPhysDefault,
        AddMaterialPhysProxyNoDraw,
        AddMaterialPhysNone,
        AddMaterialPhysObstruct,
        AddMaterialPhysNoCollide,

        FindDegenerateFaces,
        FindMultifaceLines,
        FindWeightless,
        RemoveAllWeight,
        FindNoUVs,
        AddUVTexture,

        RenamePhysBones,
        AddBoneGeometry,
        RemoveBoneGeometry,

        Export,
        ErrorHandler,

        ExportUtilitiesPanel,
        CryUtilitiesPanel,
        BoneUtilitiesPanel,
        MeshUtilitiesPanel,
        CustomPropertiesPanel,
        ConfigurationsPanel,

        CryBlendMainMenu,
        AddPhysicsProxyMenu,
        BoneUtilitiesMenu,
        BreakablesMenu,
        TouchBendingMenu,
        MeshUtilitiesMenu,
        CustomPropertiesMenu,
        GenerateScriptMenu,
        ConfigurationsMenu,

        AddMaterialPhysicsMenu,
        CryBlendReducedMenu,

        SelectScriptEditor,
        GenerateScript,
    )

    return classes


def draw_item(self, context):
    layout = self.layout
    layout.menu(CryBlendMainMenu.bl_idname)


def physics_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.label("CryBlend")
    layout.menu("menu.add_material_physics", icon="PHYSICS")
    layout.separator()


def register():
    for classToRegister in get_classes_to_register():
        bpy.utils.register_class(classToRegister)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('wm.call_menu', 'Q', 'PRESS', ctrl = False, shift = True)
        kmi.properties.name = "view3d.cryblend_reduced_menu"

    bpy.types.INFO_HT_header.append(draw_item)
    bpy.types.MATERIAL_MT_specials.append(physics_menu)


def unregister():
    # you guys already know this but for my reference,
    # unregister your classes or when you do new scene
    # your script wont import other modules properly.
    for classToRegister in get_classes_to_register():
        bpy.utils.unregister_class(classToRegister)
        wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps['3D View']
        for kmi in km.keymap_items:
            if kmi.idname == 'wm.call_menu':
                if kmi.properties.name == "view3d.cryblend_reduced_menu":
                    km.keymap_items.remove(kmi)
                    break

    bpy.types.INFO_HT_header.remove(draw_item)
    bpy.types.MATERIAL_MT_specials.remove(physics_menu)


if __name__ == "__main__":
    register()

    # The menu can also be called from scripts
    bpy.ops.wm.call_menu(name=ExportUtilitiesPanel.bl_idname)
