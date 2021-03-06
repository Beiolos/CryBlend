#------------------------------------------------------------------------------
# Name:        utils.py
# Purpose:     Utility functions for use throughout the add-on
#
# Author:      Angelo J. Miner
#
# Created:     23/02/2012
# Copyright:   (c) Angelo J. Miner 2012
# Licence:     GPLv2+
#------------------------------------------------------------------------------

# <pep8-80 compliant>


if "bpy" in locals():
    import imp
    imp.reload(exceptions)
else:
    import bpy
    from io_export_cryblend import exceptions


from io_export_cryblend.outPipe import cbPrint
from mathutils import Matrix, Vector
from xml.dom.minidom import Document, parseString
import bpy
import fnmatch
import math
import os
import random
import re
import subprocess
import sys
import xml.dom.minidom


# globals
toDegrees = 180.0 / math.pi


def color_to_string(r, g, b, a):
    return "{:f} {:f} {:f} {:f}".format(r, g, b, a)


def convert_time(frame):
    fps_base = bpy.context.scene.render.fps_base
    fps = bpy.context.scene.render.fps
    return (fps_base * frame) / fps


# the following func is from
# http://ronrothman.com/
#    public/leftbraned/xml-dom-minidom-toprettyxml-and-silly-whitespace/
# modified to use the current ver of shipped python
def fix_write_xml(self, writer, indent="", addindent="", newl=""):
    # indent = current indentation
    # addindent = indentation to add to higher levels
    # newl = newline string
        writer.write(indent + "<" + self.tagName)
        attrs = self._get_attributes()
        for a_name in sorted(attrs.keys()):
            writer.write(" %s=\"" % a_name)
            xml.dom.minidom._write_data(writer, attrs[a_name].value)
            writer.write("\"")
        if self.childNodes:
            if (len(self.childNodes) == 1
                and self.childNodes[0].nodeType
                    == xml.dom.minidom.Node.TEXT_NODE):
                writer.write(">")
                self.childNodes[0].writexml(writer, "", "", "")
                writer.write("</%s>%s" % (self.tagName, newl))
                return
            writer.write(">%s" % (newl))
            for node in self.childNodes:
                node.writexml(writer, indent + addindent, addindent, newl)
            writer.write("%s</%s>%s" % (indent, self.tagName, newl))
        else:
            writer.write("/>%s" % (newl))


def get_guid():
    GUID = "{%s-%s-%s-%s-%s}" % (random_hex_sector(8),
                                 random_hex_sector(4),
                                 random_hex_sector(4),
                                 random_hex_sector(4),
                                 random_hex_sector(12))
    return GUID


def random_hex_sector(length):
    fixed_length_hex_format = "%0" + str(length) + "x"
    return fixed_length_hex_format % random.randrange(16 ** length)


# borrowed from obj exporter
# modified by angelo j miner
def veckey3d(v):
    return (round(v.x / 32767.0),
            round(v.y / 32767.0),
            round(v.z / 32767.0))


def veckey3d2(v):
    return (v.x,
            v.y,
            v.z)


def veckey3d21(v):
    return [round(v.x, 6),
            round(v.y, 6),
            round(v.z, 6)]


def veckey3d3(vn, fn):
    return (round((fn.x * vn.x) / 2),
            round((fn.y * vn.y) / 2),
            round((fn.z * vn.z) / 2))


def matrix_to_string(matrix):
    rows = []
    for row in matrix:
        rows.append(" ".join("%s" % column for column in row))

    return " ".join(rows)


def floats_to_string(floats, separator=" ", precision="%.6f"):
    return separator.join(precision % x for x in floats)


def strings_to_string(strings, separator=" "):
    return separator.join(string for string in strings)


def matrix_to_array(matrix):
    array = []
    for row in matrix:
        array.extend(row)

    return array

def write_matrix(matrix, node):
    doc = Document()
    for row in matrix:
        row_string = floats_to_string(row)
        node.appendChild(doc.createTextNode(row_string))

def get_absolute_path(file_path):
    [is_relative, file_path] = strip_blender_path_prefix(file_path)

    if is_relative:
        blend_file_path = os.path.dirname(bpy.data.filepath)
        file_path = "%s/%s" % (blend_file_path, file_path)

    return os.path.abspath(file_path)


def get_absolute_path_for_rc(file_path):
    # 'z:' is for wine (linux, mac) path
    # there should be better way to determine it
    WINE_DEFAULT_DRIVE_LETTER = "z:"

    file_path = get_absolute_path(file_path)

    if not sys.platform == 'win32':
        file_path = "%s%s" % (WINE_DEFAULT_DRIVE_LETTER, file_path)

    return file_path


def get_relative_path(filepath, start=None):
    blend_file_directory = os.path.dirname(bpy.data.filepath)
    [is_relative_to_blend_file, filepath] = strip_blender_path_prefix(filepath)

    if not start:
        if is_relative_to_blend_file:
            return filepath

        # path is not relative, so create path relative to blend file.
        start = blend_file_directory

        if not start:
            raise exceptions.BlendNotSavedException

    else:
        # make absolute path to be able make relative to 'start'
        if is_relative_to_blend_file:
            filepath = os.path.normpath(os.path.join(blend_file_directory,
                                                     filepath))

    return make_relative_path(filepath, start)


def strip_blender_path_prefix(path):
    is_relative = False
    BLENDER_RELATIVE_PATH_PREFIX = "//"
    prefix_length = len(BLENDER_RELATIVE_PATH_PREFIX)

    if path.startswith(BLENDER_RELATIVE_PATH_PREFIX):
        path = path[prefix_length:]
        is_relative = True

    return (is_relative, path)


def make_relative_path(filepath, start):
    try:
        relative_path = os.path.relpath(filepath, start)
        return relative_path

    except ValueError:
        raise exceptions.TextureAndBlendDiskMismatchException(start, filepath)


def get_mtl_files_in_directory(directory):
    MTL_MATCH_STRING = "*.{!s}".format("mtl")

    mtl_files = []
    for file in os.listdir(directory):
        if fnmatch.fnmatch(file, MTL_MATCH_STRING):
            filepath = "{!s}/{!s}".format(directory, file)
            mtl_files.append(filepath)

    return mtl_files


def run_rc(rc_path, files_to_process, params=None):
    cbPrint(rc_path)
    process_params = [rc_path]

    if isinstance(files_to_process, list):
        process_params.extend(files_to_process)
    else:
        process_params.append(files_to_process)

    process_params.extend(params)

    cbPrint(params)
    cbPrint(files_to_process)

    try:
        run_object = subprocess.Popen(process_params)
    except:
        raise exceptions.NoRcSelectedException

    return run_object


def get_path_with_new_extension(image_path, extension):
    return "%s.%s" % (os.path.splitext(image_path)[0], extension)


def get_extension_from_path(image_path):
    return "%s" % (os.path.splitext(image_path)[1])


def extract_cryblend_properties(materialname):
    """Returns the CryBlend properties of a materialname as dict or
    None if name is invalid.
    """
    if is_cryblend_material(materialname):
        groups = re.findall("(.+)__([0-9]+)__(.*)__(phys[A-Za-z0-9]+)", materialname)
        properties = {}
        properties["ExportNode"] = groups[0][0]
        properties["Number"] = int(groups[0][1])
        properties["Name"] = groups[0][2]
        properties["Physics"] = groups[0][3]
        return properties
    return None


def is_cryblend_material(materialname):
    if re.search(".+__[0-9]+__.*__phys[A-Za-z0-9]+", materialname):
        return True
    else:
        return False


def clean_file():
    for texture in get_type("textures"):
        try:
            texture.image.name = replace_invalid_rc_characters(texture.image.name)
        except AttributeError:
            pass
    for material in get_type("materials"):
        material.name = replace_invalid_rc_characters(material.name)
    for node in get_type("nodes"):
        node.name = replace_invalid_rc_characters(node.name)
        try:
            node.data.name = replace_invalid_rc_characters(node.data.name)
        except AttributeError:
            pass
        if node.type == "ARMATURE":
            for bone in node.data.bones:
                bone.name = replace_invalid_rc_characters(bone.name)
    for node in get_export_nodes():
        nodename = get_node_name(node.name)
        nodetype = get_node_type(node.name)
        nodename = replace_invalid_rc_characters(nodename)
        node.name = "{}.{}".format(nodename, nodetype)


def replace_invalid_rc_characters(string):
    # Remove leading and trailing spaces.
    string.strip()

    # Replace remaining white spaces with underscores.
    string = "_".join(string.split())

    character_map = {
        "a":  "àáâå",
        "c":  "ç",
        "e":  "èéêë",
        "i":  "ìíîï",
        "l":  "ł",
        "n":  "ñ",
        "o":  "òóô",
        "u":  "ùúû",
        "y":  "ÿ",
        "ss": "ß",
        "ae": "äæ",
        "oe": "ö",
        "ue": "ü"
    } # Expand with more individual replacement rules.

    # Individual replacement.
    for good, bad in character_map.items():
        for char in bad:
            string = string.replace(char, good)
            string = string.replace(char.upper(), good.upper())

    # Remove all remaining non alphanumeric characters except underscores.
    string = re.sub("[^_0-9A-Za-z]", "", string)

    return string


def get_type(type_):
    dispatch = {
        "nodes": __get_nodes,
        "geometry": __get_geometry,
        "controllers": __get_controllers,
        "skins": __get_skins,
        "fakebones": __get_fakebones,
        "bone_geometry": __get_bone_geometry,
        "materials": __get_materials,
        "texture_slots": __get_texture_slots,
        "textures": __get_textures
    }
    return list(set(dispatch[type_]()))

def __get_nodes():
    items = []
    for group in get_export_nodes():
        items.extend(group.objects)

    return items

def __get_geometry():
    items = []
    allowed = {"MESH"}
    for object_ in get_type("nodes"):
        if object_.type in allowed and not is_fakebone(object_):
           items.append(object_)

    return items

def __get_controllers():
    items = []
    for object_ in get_type("nodes"):
        if not ("_boneGeometry" in object_.name or
                is_fakebone(object_)):
            if object_.parent is not None:
                if object_.parent.type == "ARMATURE":
                    items.append(object_.parent)

    return items

def __get_skins():
    items = []
    allowed = {"MESH"}
    for object_ in get_type("nodes"):
        if object_.type in allowed:
            if not ("_boneGeometry" in object_.name or
                    is_fakebone(object_)):
                if object_.parent is not None:
                    if object_.parent.type == "ARMATURE":
                        items.append(object_)

    return items

def __get_fakebones():
    items = []
    allowed = {"MESH"}
    for object_ in bpy.data.objects:
        if is_fakebone(object_):
            items.append(object_)

    return items

def __get_bone_geometry():
    items = []
    allowed = {"MESH"}
    for object_ in get_type("nodes"):
        if (object_.type in allowed and
                "_boneGeometry" in object_.name):
            items.append(object_)

    return items

def __get_materials():
    items = []
    allowed = {"MESH"}
    for object_ in get_type("nodes"):
        if object_.type in allowed:
            for material_slot in object_.material_slots:
                items.append(material_slot.material)

    return items

def __get_texture_slots():
    items = []
    for material in get_type("materials"):
        items.extend(get_texture_slots_for_material(material))

    return items

def __get_textures():
    items = []
    texture_slots = get_type("texture_slots")
    items.append(texture_slot.texture for texture_slot in texture_slots)

    return items


def get_export_nodes():
    export_nodes = []
    for group in bpy.context.blend_data.groups:
        if is_export_node(group.name) and len(group.objects) > 0:
            export_nodes.append(group)

    return export_nodes


def get_texture_slots_for_material(material):
    texture_slots = []
    for texture_slot in material.texture_slots:
        if texture_slot and texture_slot.texture.type == 'IMAGE':
            texture_slots.append(texture_slot)

    validate_texture_slots(texture_slots)

    return texture_slots


def validate_texture_slots(texture_slots):
    texture_types = count_texture_types(texture_slots)
    raise_exception_if_textures_have_same_type(texture_types)


def count_texture_types(texture_slots):
    texture_types = {
        'DIFFUSE': 0,
        'SPECULAR': 0,
        'NORMAL MAP': 0
    }

    for texture_slot in texture_slots:
        if texture_slot.use_map_color_diffuse:
            texture_types['DIFFUSE'] += 1
        if texture_slot.use_map_color_spec:
            texture_types['SPECULAR'] += 1
        if texture_slot.use_map_normal:
            texture_types['NORMAL MAP'] += 1

    return texture_types


def raise_exception_if_textures_have_same_type(texture_types):
    ERROR_TEMPLATE = "There is more than one texture of type {!r}."
    error_messages = []

    for type_name, type_count in  texture_types.items():
        if type_count > 1:
            error_messages.append(ERROR_TEMPLATE.format(type_name.lower()))

    if error_messages:
        raise exceptions.CryBlendException("\n".join(error_messages) + "\n"
                                    + "Please correct that and try again.")


def is_valid_image(image):
    return image.has_data and image.filepath


def get_material_color(material, type_):
    if type_ == "emission":
        r = b = g = material.emit
    elif type_ == "ambient":
        r = b = g = material.ambient
    elif type_ == "diffuse":
        r = material.diffuse_color.r
        g = material.diffuse_color.g
        b = material.diffuse_color.b
    elif type_ == "specular":
        r = material.specular_color.r
        g = material.specular_color.g
        b = material.specular_color.b

    col = color_to_string(r, g, b, 1.0)
    return col

def get_material_attribute(material, type_):
    if type_ == "shininess":
        float = material.specular_hardness
    elif type_ == "index_refraction":
        float = material.alpha

    return str(float)


def get_bounding_box(object_):
    box = object_.bound_box
    vmin = Vector([box[0][0], box[0][1], box[0][2]])
    vmax = Vector([box[6][0], box[6][1], box[6][2]])

    return vmin[0], vmin[1], vmin[2], vmax[0], vmax[1], vmax[2]


def parent(children, parent):
    for object_ in children:
        object_.parent = parent

    return


def is_export_node(nodename):
    extensions = [".cgf", ".cga", ".chr", ".skin", ".anm", ".i_caf"]
    for extension in extensions:
        if nodename.endswith(extension):
            return True

    return False


def are_duplicate_nodes():
    nodenames = []
    for group in get_export_nodes():
        nodenames.append(get_node_name(group.name))
    unique_nodenames = set(nodenames)
    if len(unique_nodenames) < len(nodenames):
        return True

def get_node_type(groupname):
    node_components = groupname.split(".")
    return node_components[-1]


def get_node_name(groupname):
    node_type = get_node_type(groupname)
    return groupname[:-(len(node_type)+1)]


def generate_file_contents(type_):
    if type_ == "chrparams":
        return """<Params>\
<AnimationList>\
<Animation name="???" path="???.caf"/>\
</AnimationList>\
</Params>"""

    elif type_ == "cdf":
        return """<CharacterDefinition>\
<Model File="???.chr" Material="???"/>\
<AttachmentList>\
<Attachment Type="CA_BONE" AName="???" Rotation="1,0,0,0" Position="0,0,0" BoneName="???" Flags="0"/>\
<Attachment Type="CA_SKIN" AName="???" Binding="???.skin" Flags="0"/>\
</AttachmentList>\
<ShapeDeformation COL0="0" COL1="0" COL2="0" COL3="0" COL4="0" COL5="0" COL6="0" COL7="0"/>\
</CharacterDefinition>"""


def generate_file(filepath, contents):
    if not os.path.exists(filepath):
        file = open(filepath, "w")
        file.write(contents)
        file.close()


def generate_xml(filepath, contents):
    if not os.path.exists(filepath):
        script = parseString(contents)
        contents = script.toprettyxml(indent="    ")
        generate_file(filepath, contents)


def get_armature_for_object(object_):
    if object_.parent is not None:
        if object_.parent.type == "ARMATURE":
            return object_.parent


def get_armature():
    for object_ in get_type("controllers"):
        return object_


def get_bones(armature):
    return [bone for bone in armature.data.bones]


def is_fakebone(object_):
    fakebone = 0
    for prop in object_.rna_type.id_data.items():
        if prop:
            if prop[1] == "fakebone":
                fakebone = 1
                break

    return fakebone


def remove_unused_meshes():
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def tag_fakebone(pose_bone):
    for object_ in bpy.context.scene.objects:
        if object_.name == pose_bone.name:
            object_["fakebone"] = "fakebone"

def deselect_all():
    for object_ in bpy.context.scene.objects:
        object_.select = False


def find_fakebone(bonename):
    for object_ in bpy.context.scene.objects:
        if object_.name == bonename:
            return object_


def find_bone_geometry(bonename):
    for object_ in bpy.context.scene.objects:
        if object_.name == "{!s}_boneGeometry".format(bonename):
            return object_

def add_fakebones():
    '''Add helpers to track bone transforms.'''
    scene = bpy.context.scene
    remove_unused_meshes()
    armature = get_armature()
    if armature is None:
        return

    deselect_all()
    scene.frame_set(scene.frame_start)
    for pose_bone in armature.pose.bones:
        bmatrix = pose_bone.bone.head_local
        bpy.ops.mesh.primitive_cube_add(radius=.1, location=bmatrix)
        fakebone = bpy.context.active_object
        for group in armature.users_group:
            group.objects.link(fakebone)
        fakebone.name = pose_bone.name
        fakebone["fakebone"] = "fakebone"
        scene.objects.active = armature
        armature.data.bones.active = pose_bone.bone
        bpy.ops.object.parent_set(type='BONE')

    keyframe_fakebones(armature)


def remove_fakebones():
    '''Select to remove all fakebones from the scene.'''
    deselect_all()
    for object_ in bpy.context.scene.objects:
        is_fakebone = False
        try:
            throwaway = object_['fakebone']
            is_fakebone = True
        except:
            pass
        if (is_fakebone):
            object_.select = True
            bpy.ops.object.delete(use_global=False)


def keyframe_fakebones(armature):
    scene = bpy.context.scene

    keyframes = get_keyframes(armature)
    if keyframes is None:
        return

    locations, rotations = calculate_fakebone_transforms(armature, keyframes)
    i = 0
    for frame in keyframes:
        scene.frame_set(frame)
        for bone in armature.pose.bones:
            fakebone = scene.objects.get(bone.name)
            fakebone.location = locations[i]
            fakebone.rotation_euler = rotations[i]
            fakebone.keyframe_insert(data_path="location")
            fakebone.keyframe_insert(data_path="rotation_euler")
            i += 1
            
    scene.frame_set(scene.frame_start)


def get_keyframes(armature):
    keyframes = []
    animation_data = armature.animation_data
    if (animation_data is None or animation_data.action is None):
        return
    action = animation_data.action
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe_entry = int(keyframe.co.x)
            if (keyframe_entry not in keyframes):
                keyframes.append(keyframe_entry)
    return keyframes


def calculate_fakebone_transforms(armature, keyframes):
    scene = bpy.context.scene
    locations = rotations = []
    for frame in keyframes:
        scene.frame_set(frame)
        for bone in armature.pose.bones:
            fakebone = scene.objects.get(bone.name)
            if (fakebone is None):
                return {"FINISHED"}
            bonecm = fakebone.matrix_local
            if (bone.parent and bone.parent.parent):
                bonepm = scene.objects.get(bone.parent.name).matrix_local
                # Relative to parent = inverse parent bone matrix * bone matrix
                animatrix = bonepm.inverted() * bonecm
            else:
                # Root bone or bones connected directly to root
                animatrix = bonecm
            lm, rm, sm = animatrix.decompose()
            locations.append(lm)
            rotations.append(rm.to_euler())
    return locations, rotations

def get_object_children(parent):
    return [object_ for object_ in parent.children
            if object_.type in {'ARMATURE', 'EMPTY', 'MESH'}]


def get_root_bone(armature_object):
    for bone in get_bones(armature_object):
        if bone.parent is None:
            return bone


def count_root_bones(armature_object):
    count = 0
    for bone in get_bones(armature_object):
        if bone.parent is None:
            count += 1

    return count

def negate_z_axis_of_matrix(matrix_local):
    for i in range(0, 3):
        matrix_local[i][3] = -matrix_local[i][3]


def fix_weights():
    for object_ in get_type("skins"):
        override = get_3d_context(object_)
        try:
            bpy.ops.object.vertex_group_normalize_all(override, lock_active=False)
        except:
            raise exceptions.CryBlendException("Please fix weightless vertices first.")
    cbPrint("Weights Corrected.")


def get_3d_context(object_):
    window = bpy.context.window
    screen = window.screen
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area3d = area
            break
    for region in area3d.regions:
        if region.type == "WINDOW":
            region3d = region
            break
    override = {
        "window": window,
        "screen": screen,
        "area": area3d,
        "region": region3d,
        "object": object_
    }

    return override


def apply_modifiers():
    for object_ in bpy.data.objects:
        for mod in object_.modifiers:
            if mod.type != "ARMATURE":
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError:
                    pass


def write_source(id_, type_, array, params, doc):
    length = len(array)
    if type_ == "float4x4":
        stride = 16
    elif len(params) == 0:
        stride = 1
    else:
        stride = len(params)
    count = int(length / stride)

    source = doc.createElement("source")
    source.setAttribute("id", id_)

    if type_ == "float4x4":
        source_data = doc.createElement("float_array")
    else:
        source_data = doc.createElement("{!s}_array".format(type_))
    source_data.setAttribute("id", "{!s}-array".format(id_))
    source_data.setAttribute("count", str(length))
    try:
        source_data.appendChild(doc.createTextNode(floats_to_string(array)))
    except TypeError:
        source_data.appendChild(doc.createTextNode(strings_to_string(array)))
    technique_common = doc.createElement("technique_common")
    accessor = doc.createElement("accessor")
    accessor.setAttribute("source", "#{!s}-array".format(id_))
    accessor.setAttribute("count", str(count))
    accessor.setAttribute("stride", str(stride))
    for param in params:
        param_node = doc.createElement("param")
        param_node.setAttribute("name", param)
        param_node.setAttribute("type", type_)
        accessor.appendChild(param_node)
    if len(params) == 0:
        param_node = doc.createElement("param")
        param_node.setAttribute("type", type_)
        accessor.appendChild(param_node)
    technique_common.appendChild(accessor)

    source.appendChild(source_data)
    source.appendChild(technique_common)

    return source


def write_input(name, offset, type_, semantic):
    doc = Document()
    id_ = "{!s}-{!s}".format(name, type_)
    input = doc.createElement("input")

    if offset is not None:
        input.setAttribute("offset", str(offset))
    input.setAttribute("semantic", semantic)
    if semantic == "TEXCOORD":
        input.setAttribute("set", "0")
    input.setAttribute("source", "#{!s}".format(id_))

    return input


def join(*items):
    strings = []
    for item in items:
        strings.append(str(item))
    return "".join(strings)


# this is needed if you want to access more than the first def
if __name__ == "__main__":
    register()
