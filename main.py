import bpy
import json
import os
import sys
import uuid
import zipfile
import logging


def setup_logger():
    """Sets up a logger for the script."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def initialize_paths(base_path):
    """Initializes and returns essential paths."""
    unzipped_assets_dir = os.path.join(base_path, "unzipped_assets")
    blender_files_dir = os.path.join(base_path, "blender_files")
    catalog_file = os.path.join(base_path, "blender_assets.cats.txt")

    # Create directories if they don't exist
    os.makedirs(unzipped_assets_dir, exist_ok=True)
    os.makedirs(blender_files_dir, exist_ok=True)

    return unzipped_assets_dir, blender_files_dir, catalog_file


def initialize_catalog_file(catalog_file):
    """Initializes the catalog file if it doesn't exist."""
    if not os.path.exists(catalog_file):
        with open(catalog_file, 'w') as f:
            f.write("VERSION 1\n")
            logging.info(f"Initialized catalog file at {catalog_file}")


def get_asset_type(json_path):
    """Reads the JSON file and extracts the asset type."""
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)
        asset_categories = data.get("assetCategories", {})
        if asset_categories:
            return next(iter(asset_categories), "Unknown")
        return "Unknown"
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error reading JSON file {json_path}: {e}")
        return "Invalid"


def find_json_file(folder_path, search_term):
    """Searches for a JSON file in the folder containing the given search term."""
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".json") and file_name.strip(".json").lower() in search_term.lower():
            return os.path.join(folder_path, file_name)
    return None


def import_gltf_and_process(gltf_path, asset_name, blend_file_path, catalog_id=None, preview_image_path=None, catalog_file=None):
    """Imports a GLTF file, organizes objects, marks assets, and saves as a blend file."""
    try:
        # Clear the existing scene
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Import the GLTF file
        bpy.ops.import_scene.gltf(filepath=gltf_path)
        print(f"Imported GLTF: {gltf_path}")

        # Create a collection for the asset
        new_collection = bpy.data.collections.new(asset_name)
        bpy.context.scene.collection.children.link(new_collection)

        # Move imported objects to the new collection
        for obj in bpy.context.selected_objects:
            bpy.context.scene.collection.objects.unlink(obj)
            new_collection.objects.link(obj)

            # Apply transforms
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Read the catalog file to gather existing IDs
        existing_catalog_ids = {}
        if os.path.exists(catalog_file):
            with open(catalog_file, 'r') as cf:
                for line in cf:
                    if ':' in line:
                        existing_uuid = line.split(':')[0].strip()
                        existing_id = line.split(':')[-1].strip()
                        existing_catalog_ids[existing_id] = existing_uuid

        # If catalog_id is not in the catalog file, append it
        if catalog_id not in existing_catalog_ids.keys():
            catalog_uuid = str(uuid.uuid4())
            with open(catalog_file, 'a') as cf:
                cf.write(f"{catalog_uuid}:{catalog_id}:{catalog_id}\n")
                print(f"Added new catalog ID: {catalog_id} to {catalog_file}")
            assigned_catalog_uuid = catalog_uuid
        else:
            assigned_catalog_uuid = existing_catalog_ids[catalog_id]

        # Handle marking assets and setting thumbnails for "surface"
        if catalog_id == "surface":
            for obj in new_collection.objects:
                if obj.type == 'MESH' and ("_LOD" not in obj.name or "_LOD0" in obj.name):
                    for material_slot in obj.material_slots:
                        material = material_slot.material
                        if material:  # Ensure the material exists
                            # Rename the material to match the asset name
                            material.name = f"{asset_name}_{material.name}"

                            # Mark material as asset
                            material.asset_mark()
                            material.asset_data.catalog_id = assigned_catalog_uuid
                            print(f"Marked material '{material.name}' as asset with catalog ID {assigned_catalog_uuid}")

                            # Set custom preview image for material
                            if preview_image_path and os.path.exists(preview_image_path):
                                override = bpy.context.copy()
                                override["id"] = material
                                with bpy.context.temp_override(**override):
                                    bpy.ops.ed.lib_id_load_custom_preview(filepath=preview_image_path)
                                print(f"Set custom preview image for material '{material.name}'")
        else:
            # Mark each object as an asset and optionally set custom previews
            for obj in new_collection.objects:
                # Skip objects with "_LOD" in the name unless it's "_LOD0"
                if "_LOD" in obj.name and "_LOD0" not in obj.name:
                    print(f"Skipping marking object '{obj.name}' as asset because it contains '_LOD' but not '_LOD0'")
                    continue

                # Rename the object to match the asset name
                obj.name = f"{asset_name}_{obj.name}"

                # Mark the object as an asset
                obj.asset_mark()
                obj.asset_data.catalog_id = assigned_catalog_uuid
                print(f"Marked object '{obj.name}' as asset with catalog ID {assigned_catalog_uuid}")

                # Set custom preview image for the object
                if preview_image_path and os.path.exists(preview_image_path):
                    override = bpy.context.copy()
                    override["id"] = obj
                    with bpy.context.temp_override(**override):
                        bpy.ops.ed.lib_id_load_custom_preview(filepath=preview_image_path)
                    print(f"Set custom preview image for object '{obj.name}'")

        # Disable .blend1 backup creation
        bpy.context.preferences.filepaths.save_version = 0

        # Save the Blender file
        bpy.ops.wm.save_as_mainfile(filepath=blend_file_path)
        print(f"Saved {blend_file_path}")

    except Exception as e:
        logging.error(f"Failed to process {gltf_path}: {e}")


def process_assets(base_path):
    """Main function to process all assets in the given path."""
    base_path = os.path.expanduser(base_path)
    print(base_path)
    unzipped_assets_dir, blender_files_dir, catalog_file = initialize_paths(base_path)
    initialize_catalog_file(catalog_file)

    for file_name in os.listdir(base_path):
        if file_name.endswith(".zip"):
            zip_path = os.path.join(base_path, file_name)
            asset_name = os.path.splitext(file_name)[0]
            extract_path = os.path.join(unzipped_assets_dir, asset_name)

            # Check if the asset is already unzipped
            if os.path.exists(extract_path) and os.listdir(extract_path):
                print(f"Asset '{asset_name}' is already unzipped. Skipping extraction.")
                continue

            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                logging.info(f"Extracted {file_name} to {extract_path}")
            except zipfile.BadZipFile:
                logging.error(f"{file_name} is not a valid ZIP file.")
                continue

            json_file = find_json_file(extract_path, asset_name)
            if not json_file:
                logging.warning(f"No JSON file found for {asset_name}. Skipping.")
                continue

            asset_type = get_asset_type(json_file)
            for gltf_file_name in os.listdir(extract_path):
                if gltf_file_name.endswith(".gltf"):
                    gltf_path = os.path.join(extract_path, gltf_file_name)
                    blend_file_path = os.path.join(blender_files_dir, f"{asset_name}.blend")
                    preview_image_path = os.path.join(base_path, f"{asset_name}.jpg")
                    if not os.path.exists(preview_image_path):
                        preview_image_path = None

                    import_gltf_and_process(
                        gltf_path, asset_name, blend_file_path, catalog_id=asset_type, preview_image_path=preview_image_path, catalog_file=catalog_file
                    )



setup_logger()
process_assets(str(sys.argv[-1]))

