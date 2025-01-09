import bpy
import bpy.utils.previews
import json
import os
import queue
import subprocess
import sys
import threading
import time

current_file_path = bpy.context.space_data.text.filepath
current_file_dir = os.sep.join(current_file_path.split(os.sep)[:-1])
utils_path = os.path.join(current_file_dir, "utils.py")

asset_queue = queue.Queue()
loading_thread = None

system_python = "/usr/bin/python3"
data_dir = "/tmp/fab_data"
thumbnail_dir = os.path.join(data_dir, "thumbnails")
env_dir = "/tmp/tmp-env"
python_path = os.path.join(env_dir, "bin", "python")

if not os.path.exists(data_dir):
    os.mkdir(data_dir)
if not os.path.exists(thumbnail_dir):
    os.mkdir(thumbnail_dir)

cursors = {"curr_cursor" : "0", "next_cursor" : "0"}

def setup_env():
    if not os.path.exists(env_dir):
        print(f"Creating virtual environment at {env_dir}")
        subprocess.check_call([system_python, "-m", "venv", env_dir])
        subprocess.check_call([python_path, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([python_path, "-m", "pip", "install", "requests", "zstandard", "pillow"])


def load_assets_in_background(file_path,asset_type):
    pcoll = bpy.utils.previews.new()

    with open(file_path, 'r') as f:
        data = json.load(f)

    cursor_data = data.get("cursors", {})
    # cursors["prev_cursor"] = cursor_data.get("previous")
    cursors["next_cursor"] = cursor_data.get("next")

    results_data = data.get("results", [])

    for item in results_data:
        title = item.get("title", "")
        uid = item.get("uid", "")
        asset_name = f"{title}_{uid}"
        # img_url = item["thumbnails"][0]["mediaUrl"]
        img_url = next((img["url"] for img in item["thumbnails"][0]["images"] if img["height"] == 180), None)
        # img_name = item["thumbnails"][0]["name"]
        img_name = os.path.basename(img_url)
        img_path = os.path.join(thumbnail_dir, img_name)

        # Download the image if not already present
        if not os.path.exists(img_path):
            subprocess.check_call(["wget", "-nc", "-P", thumbnail_dir, img_url])
            if asset_type in ('material', 'decal'):
                print(f"Running {utils_path} inside the virtual environment...")
                command = [python_path, utils_path, "--function", "crop_thumbnails", img_path,]
                result = subprocess.run(command, capture_output=True, text=True)

        # Load the asset into the preview collection
        if os.path.exists(img_path):
            pcoll.load(asset_name, img_path, 'IMAGE')
            # Add the asset to the queue
            asset_queue.put((asset_name, pcoll[asset_name]))
        else:
            print(f"Image path {img_path} does not exist.")

    # Signal completion
    asset_queue.put(None)


def update_ui_from_queue():
    while not asset_queue.empty():
        item = asset_queue.get()
        if item is None:
            print("Asset loading complete.")
            return None  # Stop the timer

        asset_name, asset = item
        if FILEBROWSER_PT_assets.assets is None:
            FILEBROWSER_PT_assets.assets = bpy.utils.previews.new()
        FILEBROWSER_PT_assets.assets[asset_name] = asset

    return 0.5  # Check the queue again in 0.2 seconds


class FILEBROWSER_PT_assets(bpy.types.Panel):
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_context = "ASSET_BROWSER"
    bl_label = "Assets"
    bl_idname = "FILEBROWSER_PT_assets"

    assets = None

    def draw(self, context):
        layout = self.layout
        layout.alignment = "CENTER"

        # Combo box for selecting asset type
        row = layout.row()
        row.prop(context.scene, "asset_type", text="")

        # Search box and search button
        row = layout.row()
        row.prop(context.scene, "asset_search", text="")
        row.operator("filebrowser.search_assets", text="", icon='VIEWZOOM')

        if self.assets:
            row = layout.row()
            # Calculate the number of columns based on the panel's width
            min_width = 120  # Minimum width for a single column
            if context.region.width < min_width:
                columns_count = 1
            else:
                columns_count = min(int(context.region.width / min_width), len(self.assets))

            column_list = [row.column(align=True) for _ in range(columns_count)]

            for i, (asset_name, asset) in enumerate(self.assets.items()):
                # col = col1 if i % 2 == 0 else col2
                col = column_list[i % columns_count]
                asset_box = col.box()
                asset_box.scale_x = 1.0
                asset_box.scale_y = 1.0
                asset_box.template_icon(asset.icon_id, scale=5)
                asset_box.label(text=asset_name.split("_")[0], icon='BLANK1')
                asset_box.operator("dummy.operator", text="Import")

        row = layout.row()
        row.operator("filebrowser.load_more", text="Load More")


class DUMMY_OP_dummy_operator(bpy.types.Operator):
    bl_idname = "dummy.operator"
    bl_label = "Import"

    def execute(self, context):
        self.report({'INFO'}, "Dummy operator executed")
        return {'FINISHED'}


class FILEBROWSER_OT_search_assets_modal(bpy.types.Operator):
    """Detect Enter Key Press for Search"""
    bl_idname = "filebrowser.search_assets_modal"
    bl_label = "Search Assets Modal"

    def modal(self, context, event):
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            bpy.ops.filebrowser.search_assets()
            return {'FINISHED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class FILEBROWSER_OT_search_assets(bpy.types.Operator):
    bl_idname = "filebrowser.search_assets"
    bl_label = "Search Assets"

    def execute(self, context):
        cursor = "0"
        FILEBROWSER_PT_assets.assets = None
        update_assets(context, cursor)
        return {'FINISHED'}


class FILEBROWSER_OT_load_more(bpy.types.Operator):
    bl_idname = "filebrowser.load_more"
    bl_label = "Load More"

    def execute(self, context):
        if cursors["next_cursor"] is not None:
            cursors["curr_cursor"] = cursors["next_cursor"]
            self.report({'INFO'}, "Loading more assets")
            update_assets(context, cursors["curr_cursor"])
        return {'FINISHED'}


def update_assets(context, cursor):
    global loading_thread

    asset_type_mapping = {
        '3D_MODEL': "3d-model",
        'MATERIAL': "material",
        'DECAL': "decal"
    }
    asset_type = str(asset_type_mapping.get(context.scene.asset_type, "material")).strip()
    query = context.scene.asset_search.strip()
    # cursor = cursors["curr_cursor"].strip()
    file_path = os.path.join(data_dir, f"output_{asset_type}_{query}_{cursor}.json")

    if not os.path.exists(file_path):
        url = "https://www.fab.com/i/listings/search"
        referer = "https://www.fab.com/sellers/Quixel"

        print(f"Running {utils_path} inside the virtual environment...")
        command = [python_path, utils_path, "--function", "fetch_asset_details", url, referer, asset_type, query, cursor,]
        result = subprocess.run(command, capture_output=True, text=True)

    # Stop any existing thread
    if loading_thread and loading_thread.is_alive():
        print("Stopping existing loading thread...")
        loading_thread.join()

    # Clear old assets and start a new thread
    # FILEBROWSER_PT_assets.assets = None
    loading_thread = threading.Thread(target=load_assets_in_background, args=(file_path,asset_type,))
    loading_thread.start()

    # Start UI timer to process the queue
    bpy.app.timers.register(update_ui_from_queue)


def register():
    bpy.utils.register_class(FILEBROWSER_PT_assets)
    bpy.utils.register_class(FILEBROWSER_OT_load_more)
    bpy.utils.register_class(DUMMY_OP_dummy_operator)
    bpy.utils.register_class(FILEBROWSER_OT_search_assets)
    bpy.utils.register_class(FILEBROWSER_OT_search_assets_modal)

    # bpy.types.Scene.asset_search = bpy.props.StringProperty(name="Search Assets")
    bpy.types.Scene.asset_search = bpy.props.StringProperty(
        name="Search Assets",
        update=FILEBROWSER_OT_search_assets.execute
    )

    bpy.types.Scene.asset_type = bpy.props.EnumProperty(
        name="Asset Type",
        description="Type of asset",
        items=[
            ('3D_MODEL', "3d-model", ""),
            ('MATERIAL', "material", ""),
            ('DECAL', "decal", "")
        ],
        update=FILEBROWSER_OT_search_assets.execute  # Update assets when the type changes
    )

    bpy.ops.filebrowser.search_assets_modal()
    setup_env()


def unregister():
    bpy.utils.unregister_class(FILEBROWSER_PT_assets)
    bpy.utils.unregister_class(FILEBROWSER_OT_load_more)
    bpy.utils.unregister_class(DUMMY_OP_dummy_operator)
    bpy.utils.unregister_class(FILEBROWSER_OT_search_assets)
    bpy.utils.unregister_class(FILEBROWSER_OT_search_assets_modal)

    del bpy.types.Scene.asset_search
    del bpy.types.Scene.asset_type


if __name__ == "__main__":
    register()
