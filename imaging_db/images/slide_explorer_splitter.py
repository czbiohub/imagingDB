import glob
import numpy as np
import os
import tifffile
from tqdm import tqdm

from imaging_db.images.ometif_splitter import OmeTiffSplitter
import imaging_db.metadata.json_operations as json_ops
import imaging_db.utils.meta_utils as meta_utils


class SlideExplorerSplitter(OmeTiffSplitter):
    """
    Subclass for reading and splitting ome tiff files
    """
    def __init__(self,
                 data_path,
                 storage_dir,
                 storage_class,
                 storage_access=None,
                 overwrite=False,
                 file_format=".png",
                 nbr_workers=4,
                 int2str_len=3):

        super().__init__(data_path=data_path,
                         storage_dir=storage_dir,
                         storage_class=storage_class,
                         storage_access=storage_access,
                         overwrite=overwrite,
                         file_format=file_format,
                         nbr_workers=nbr_workers,
                         int2str_len=int2str_len)

    def _validate_file_paths(self, roi, positions, glob_paths):
        """
        Get only the file paths found by glob that correspond to the input
        parameter positions.

        :param list of ints positions: Positions to be uploaded
        :param list of strs glob_paths: Paths to files found in directory
        :return list of strs file_paths: Paths that exist in directory and
            in positions
        """
        position_list = self.global_json["IJMetadata"]["InitialPositionList"]

        roi_label = 'roi' + str(roi)
        position_labels = [p["Label"] for p in position_list if roi_label in p["Label"]]

        file_paths = []
        for label in position_labels:

            # Check if the value is in positions
            if positions == "all":
                file_path = next((s for s in glob_paths if label in s), None)
                if file_path is not None:
                    file_paths.append(file_path)
            elif int(label.split('_')[1][4:]) in positions:
                file_path = next((s for s in glob_paths if label in s), None)
                if file_path is not None:
                    file_paths.append(file_path)                                
        
        assert len(file_paths) > 0, \
            "No positions correspond with IJMetadata PositionList"
        return file_paths

    def get_frames_and_metadata(self, schema_filename, positions=None, roi=1):
        """
        Reads ome.tiff file into memory and separates image frames and metadata.
        Workaround in case I need to read ome-xml:
        https://github.com/soft-matter/pims/issues/125
        It is assumed that all metadata lives as dicts inside tiff frame tags.
        NOTE: It seems like the IJMetadata Info field is a dict converted into
        string, and it's only present in the first frame.

        :param str schema_filename: Full path to metadata json schema file
        :param [None, list of ints] positions: Position files to upload.
            If None,
        """
        if isinstance(positions, type(None)):
            positions = []
        if os.path.isfile(self.data_path):
            # Run through processing only once
            file_paths = [self.data_path]
            # Only one file so don't consider positions
            positions = []
        else:
            # Get position files in the folder
            file_paths = glob.glob(os.path.join(self.data_path, "*.ome.tif"))
            assert len(file_paths) > 0,\
                "Can't find ome.tifs in {}".format(self.data_path)
            # Parse positions
            if isinstance(positions, str):
                if positions != 'all':
                    positions = json_ops.str2json(positions)
                    if isinstance(positions, int):
                        print('is int')
                        positions = [positions]

        # Read first file to find available positions
        frames = tifffile.TiffFile(file_paths[0])
        # Get global metadata
        page = frames.pages[0]
        # Set frame info. This should not vary between positions
        self.set_frame_info(page)
        # IJMetadata only exists in first frame, so that goes into global json
        self.global_json = json_ops.get_global_json(
            page=page,
            file_name=self.data_path,
        )
        # Validate given positions
        if len(positions) > 0:
            file_paths = self._validate_file_paths(
                roi=roi,
                positions=positions,
                glob_paths=file_paths,
            )

        self.frames_meta = meta_utils.make_dataframe()
        self.frames_json = []

        pos_prog_bar = tqdm(file_paths, desc='Position')

        for file_path in pos_prog_bar:
            file_meta, im_stack = self.split_file(
                file_path,
                schema_filename,
            )

            sha = self._generate_hash(im_stack)
            file_meta['sha256'] = sha

            self.frames_meta = self.frames_meta.append(
                file_meta,
                ignore_index=True,
            )
            # Upload frames in file to S3
            self.data_uploader.upload_frames(
                file_names=list(file_meta["file_name"]),
                im_stack=im_stack,
            )
        # Finally, set global metadata from frames_meta
        self.set_global_meta(nbr_frames=self.frames_meta.shape[0])
