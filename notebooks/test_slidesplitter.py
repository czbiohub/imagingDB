import glob
import os

from imaging_db.images.slide_explorer_splitter import SlideExplorerSplitter
import imaging_db.utils.aux_utils as aux_utils


FRAME_FOLDER_NAME = "raw_frames"
FRAME_FILE_FORMAT = ".png"

dataset_serial = 'ISP-2019-10-08-00-00-00-0001'
file_name = "Z:\Darmanis Group\Ashley\LungRNAscope\TH239_E4_B1_assay1_20191008_1"
storage_dir = "/".join([FRAME_FOLDER_NAME, dataset_serial])
storage_class = aux_utils.get_storage_class(storage_type='local')
storage_access = "Y:\\czbiohub-imaging"
schema_filename = "metadata_schema.json"
overwrite=False
nbr_workers = None

frames_inst = SlideExplorerSplitter(
                data_path=file_name,
                storage_dir=storage_dir,
                storage_class=storage_class,
                storage_access=storage_access,
                overwrite=overwrite,
                file_format=FRAME_FILE_FORMAT,
                nbr_workers=nbr_workers,
            )

positions = [1, 2]
roi = 1
path = os.path.join(file_name, "*.ome.tif")
file_paths = glob.glob(path)

frames_inst.get_frames_and_metadata(schema_filename, positions='all', roi=2)


