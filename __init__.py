import shutil
import folder_paths
import os, sys, subprocess
import filecmp



print("### Loading: Save SRS")

comfy_path = os.path.dirname(folder_paths.__file__)

def setup_js():
   node_root = os.path.dirname(__file__)
   js_dest_path = os.path.join(comfy_path, "web", "extensions", "save_clsrs")
   js_src_path = os.path.join(node_root, "nodeinfo.js")
     
   ## Creating folder if it's not present, then Copy. 
   print("Copying JS files for Workflow loading")
   if (os.path.isdir(js_dest_path)==False):
     os.mkdir(js_dest_path)
     shutil.copy(js_src_path, js_dest_path)
   else:
     shutil.copy(js_src_path, js_dest_path)
           

                     
setup_js()

from .SaveSRS import NODE_CLASS_MAPPINGS

__all__ = ['NODE_CLASS_MAPPINGS']