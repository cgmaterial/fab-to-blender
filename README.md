# fab-to-blender

## Steps to follow:

- Go to https://www.fab.com/sellers/Quixel

- Click on any asset you want to download.

- Download 'gltf' format.

- Download the thumbnail image and name it same as the downloaded zip file.

- Put them in a folder. In blender make an asset library from same path.

- Run script as follows: 
path_to_blender_executable -b --factory-startup -P main.py -- "path_to_asset_folder"
