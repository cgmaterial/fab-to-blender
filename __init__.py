import bpy
import os
import subprocess


bl_info = {
    "name": "Fab to Blender",
    "description": "Process assets from fab and add it as an Asset Library",
    "author": "cgmaterial",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Asset Browser > Sidebar",
    "category": "Asset Management",
}


class ASSET_OT_RunProcessor(bpy.types.Operator):
    """Run the asset processing script"""
    bl_idname = "asset_processor.run_processor"
    bl_label = "Process Assets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get addon preferences
        prefs = context.preferences.addons[__name__].preferences
        blender_path = prefs.blender_executable_path
        asset_path = prefs.asset_folder_path

        if not blender_path or not os.path.isfile(blender_path):
            self.report({"ERROR"}, "Invalid Blender executable path!")
            return {'CANCELLED'}

        if not asset_path or not os.path.isdir(asset_path):
            self.report({"ERROR"}, "Invalid Asset Folder path!")
            return {'CANCELLED'}

        # Run the script using subprocess
        try:
            subprocess.run(
                [blender_path, "-b", "--factory-startup", "-P", os.path.join(os.path.dirname(__file__), "main.py"), "--", asset_path],
                check=True,
            )
            self.report({"INFO"}, "Assets processed successfully!")

            # Add Asset Library after processing
            self.add_asset_library(asset_path)

        except subprocess.CalledProcessError as e:
            self.report({"ERROR"}, f"Failed to process assets: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def add_asset_library(self, library_path):
        """Adds the folder as an Asset Library if it doesn't already exist."""
        existing_libraries = bpy.context.preferences.filepaths.asset_libraries

        # Normalize the provided library path for consistent comparison
        normalized_library_path = os.path.normpath(library_path)

        # Check if the normalized path already exists in asset libraries
        for lib in existing_libraries:
            if os.path.normpath(lib.path) == normalized_library_path:
                self.report({"INFO"}, "Asset Library already exists.")
                return

        # Add the new library
        bpy.ops.preferences.asset_library_add(directory=normalized_library_path)
        self.report({"INFO"}, f"Added Asset Library: {normalized_library_path}")



class ASSET_PT_Panel(bpy.types.Panel):
    """UI Panel for the Asset Processor"""
    bl_label = "Asset Processor"
    bl_idname = "ASSET_PT_processor_panel"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_context = "ASSET"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Asset Processor:")
        layout.operator("asset_processor.run_processor", text="Process Assets")


class AssetProcessorPreferences(bpy.types.AddonPreferences):
    """Preferences for the Asset Processor addon"""
    bl_idname = __name__

    blender_executable_path: bpy.props.StringProperty(
        name="Blender Executable Path",
        description="Path to the Blender executable",
        subtype='FILE_PATH',
        default="",
    )

    asset_folder_path: bpy.props.StringProperty(
        name="Asset Folder Path",
        description="Path to the folder containing assets",
        subtype='DIR_PATH',
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "blender_executable_path")
        layout.prop(self, "asset_folder_path")


classes = [ASSET_OT_RunProcessor, ASSET_PT_Panel, AssetProcessorPreferences]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
