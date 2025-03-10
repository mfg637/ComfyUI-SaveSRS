import math

import numpy as np
from PIL import Image
import folder_paths
import os
import json
import pathlib
import tempfile
import subprocess
import io

# by Kaharos94
# https://github.com/Kaharos94/ComfyUI-Saveaswebp
# comfyUI node to save an image in webp format

# fork by mfg637

CL3_SIZE_LIMIT = 2048
CL2_SIZE_LIMIT = 4096

class SaveSRS:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.output_dir_path = pathlib.Path(self.output_dir)
        self.type = "output"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "thumbnail_images": ("IMAGE", ),
                "upscale_images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                "compression":("INT", {"default": 90, "min": 1, "max": 100, "step": 1},),
                "webp_compression_speed": ("INT", {"default": 4, "min": 0, "max": 6, "step": 1},),
                "avif_cpu_used": ("INT", {"default": 6, "min": 0, "max": 10, "step": 1},),
                "subsampling": (["auto", "444", "422", "420", "400"],),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "save_srs"

    OUTPUT_NODE = True

    CATEGORY = "image"

    def save_srs(self, compression, webp_compression_speed, avif_cpu_used, subsampling, thumbnail_images, upscale_images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None, ):
        def map_filename(filename):
            prefix_len = len(os.path.basename(filename_prefix))
            prefix = filename[:prefix_len + 1]
            try:
                digits = int(filename[prefix_len + 1:].split('_')[0])
            except:
                digits = 0
            return (digits, prefix)

        def compute_vars(input):
            input = input.replace("%width%", str(thumbnail_images[0].shape[1]))
            input = input.replace("%height%", str(thumbnail_images[0].shape[0]))
            return input

        filename_prefix = compute_vars(filename_prefix)

        subfolder = os.path.dirname(os.path.normpath(filename_prefix))
        _filename_prefix = os.path.basename(os.path.normpath(filename_prefix))

        full_output_folder_str = os.path.join(self.output_dir, subfolder)
        full_output_folder = pathlib.Path(full_output_folder_str)

        if os.path.commonpath((self.output_dir, os.path.abspath(full_output_folder_str))) != self.output_dir:
            print("Saving image outside the output folder is not allowed.")
            return {}

        try:
            counter = max(filter(lambda a: a[1][:-1] == _filename_prefix and a[1][-1] == "_", map(map_filename, os.listdir(full_output_folder_str))))[0] + 1
        except ValueError:
            counter = 1
        except FileNotFoundError:
            os.makedirs(full_output_folder_str, exist_ok=True)
            counter = 1

        images = zip(thumbnail_images, upscale_images)
        sub_folder = self.output_dir_path.joinpath(pathlib.Path(subfolder))
        webp_results = list()

        def convert_tensor_image_to_pil(image) -> Image.Image:
            tensor_image = image.cpu().numpy()
            intermediate_image = 255. * tensor_image
            img = Image.fromarray(np.clip(intermediate_image, 0, 255).astype(np.uint8))
            del intermediate_image
            return img

        def save_webp(img, file_name):
            workflowmetadata = str()
            promptstr = str()
            imgexif = img.getexif()  # get the (empty) Exif data of the generated Picture

            if prompt is not None:
                promptstr = "".join(json.dumps(prompt))  # prepare prompt String
                imgexif[0x010f] = "Prompt:" + promptstr  # Add PromptString to EXIF position 0x010f (Exif.Image.Make)
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    workflowmetadata += "".join(json.dumps(extra_pnginfo[x]))
            imgexif[
                0x010e] = "Workflow:" + workflowmetadata  # Add Workflowstring to EXIF position 0x010e (Exif.Image.ImageDescription)
            file = f"{file_name}.webp"

            img.save(
                os.path.join(full_output_folder_str, file),
                method=webp_compression_speed,
                exif=imgexif,
                lossless=False,
                quality=compression
            )
            webp_results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            return pathlib.Path(file)

        def save_avif(img, file_name: pathlib.Path, crf, _subsampling=subsampling, cl2_suffix = False):
            commandline = ['avifenc', '-j', 'all', "--speed", str(avif_cpu_used)]

            commandline += [
                '-d', '10',
                '--min', str(max(crf - 5, 1)),
                '--max', str(min(crf + 5, 63)),
                '-a', 'end-usage=q',
                '-a', 'cq-level={}'.format(crf)
            ]

            if _subsampling != "auto":
                commandline += ['--yuv', _subsampling]
            # if avif_enable_advanced_options:
            #     commandline += [
            #         '-a', 'aq-mode=1',
            #         '-a', 'enable-chroma-deltaq=1',
            #     ]

            output_file_name = file_name.with_suffix(".avif")
            if cl2_suffix:
                output_file_name = output_file_name.with_stem(output_file_name.stem + "cl2")

            src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
            img.save(src_tmp_file, format="PNG", compress_level=0)
            src_tmp_file_name = src_tmp_file.name

            commandline += [
                src_tmp_file_name,
                output_file_name
            ]

            subprocess.run(commandline)
            src_tmp_file.close()

            return output_file_name

        def save_srs_file(cl3_level_path, cl2_level_path, cl1_level_path: None | pathlib.Path, file_name: pathlib.Path):
            srs_data = {
                "ftype": "CLSRS",
                "content": {
                    "media-type": 0,
                    "prompt": prompt,
                    "extra_pnginfo": extra_pnginfo
                },
                "streams": {
                    "image": {"levels": dict()}
                }
            }
            srs_data["streams"]["image"]["levels"]["3"] = str(cl3_level_path)
            srs_data["streams"]["image"]["levels"]["2"] = str(cl2_level_path)
            if cl1_file_path is not None:
                srs_data["streams"]["image"]["levels"]["1"] = str(cl1_level_path)

            file_name = file_name.with_suffix(".srs")
            print("srs file name", file_name)

            with file_name.open("w") as f:
                json.dump(srs_data, f)

            return file_name

        for image in images:
            file_name = f"{_filename_prefix}_{counter:05}_"
            thumbnail_image: Image.Image = convert_tensor_image_to_pil(image[0])
            is_thumbnail_cl3: bool = \
                thumbnail_image.width <= CL3_SIZE_LIMIT and thumbnail_image.height <= CL3_SIZE_LIMIT
            is_thumbnail_cl2: bool = \
                thumbnail_image.width <= CL2_SIZE_LIMIT and thumbnail_image.height <= CL2_SIZE_LIMIT
            cl2_image = None
            cl3_image = None
            cl1_image = None
            # cl0_image = None
            if is_thumbnail_cl3:
                cl3_image = thumbnail_image
            elif is_thumbnail_cl2:
                cl3_image = thumbnail_image.copy()
                cl3_image.thumbnail((CL3_SIZE_LIMIT, CL3_SIZE_LIMIT), Image.Resampling.LANCZOS)
                cl2_image = thumbnail_image
            else:
                cl1_image = thumbnail_image
                cl2_image = thumbnail_image.copy()
                cl2_image.thumbnail((CL2_SIZE_LIMIT, CL2_SIZE_LIMIT), Image.Resampling.LANCZOS)
                cl3_image = thumbnail_image.copy()
                cl3_image.thumbnail((CL3_SIZE_LIMIT, CL3_SIZE_LIMIT), Image.Resampling.LANCZOS)
                # CL0 level is disabled, due to risk of DecompressionBombError
                # cl0_image = convert_tensor_image_to_pil(image[1])
            cl3_file_path = save_webp(cl3_image, file_name)
            crf = 100 - compression
            if cl2_image is None:
                upscale_image: Image.Image = convert_tensor_image_to_pil(image[1])
                is_upscale_cl2: bool = \
                    upscale_image.width <= CL2_SIZE_LIMIT and upscale_image.height <= CL2_SIZE_LIMIT
                if is_upscale_cl2:
                    cl2_image = upscale_image
                else:
                    cl1_image = upscale_image
                    scale_factor = min(cl1_image.width / cl3_image.width, cl1_image.height / cl3_image.height)
                    if scale_factor <= 1:
                        raise ValueError("Upscale image must be bigger than thumbnail image")
                    cl2_scale_factor = None
                    if scale_factor >= 4:
                        cl2_scale_factor = math.floor(scale_factor) / 2
                    else:
                        fraction = 1 / scale_factor
                        cl2_scale_factor = (1 - fraction) / 2 + fraction
                    cl2_image = cl1_image.copy()
                    if cl2_scale_factor > 1:
                        cl2_image.thumbnail(
                            (round(cl1_image.width / cl2_scale_factor), round(cl1_image.height / cl2_scale_factor)),
                            Image.Resampling.LANCZOS
                        )
                    else:
                        cl2_image.thumbnail(
                            (round(cl1_image.width * cl2_scale_factor), round(cl1_image.height * cl2_scale_factor)),
                            Image.Resampling.LANCZOS
                        )

            elif cl1_image is None:
                cl1_image = convert_tensor_image_to_pil(image[1])
            cl1_file_path = None
            if cl1_image is not None:
                cl1_file_path = save_avif(cl1_image, sub_folder.joinpath(file_name), crf)
                cl2_subsampling = subsampling
                if subsampling == "auto":
                    cl2_subsampling = "420"
                cl2_file_path = save_avif(cl2_image, sub_folder.joinpath(file_name), crf, cl2_subsampling, True)
            else:
                cl2_file_path = save_avif(cl2_image, sub_folder.joinpath(file_name), crf)
            cl2_relative_file_path = cl2_file_path.relative_to(full_output_folder)
            cl1_relative_file_path = None
            if cl1_file_path is not None:
                cl1_relative_file_path = cl1_file_path.relative_to(full_output_folder)
            save_srs_file(
                cl3_file_path, cl2_relative_file_path, cl1_relative_file_path, full_output_folder.joinpath(file_name)
            )
            counter += 1

        return { "ui": { "images": webp_results } }

NODE_CLASS_MAPPINGS = {
    "SaveSRS": SaveSRS
}
