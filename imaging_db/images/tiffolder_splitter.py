import glob
import natsort
import numpy as np
import os
import tifffile

import imaging_db.images.file_splitter as file_splitter
import imaging_db.metadata.json_validator as json_validator
import imaging_db.utils.aux_utils as aux_utils
import imaging_db.utils.meta_utils as meta_utils


class TifFolderSplitter(file_splitter.FileSplitter):
    """
    Subclass for reading all tiff files in a folder
    """
    def __init__(self,
                 data_path,
                 s3_dir,
                 override=False,
                 file_format=".png",
                 nbr_workers=4,
                 int2str_len=3
                 ):
        
        super().__init__(data_path,
                         s3_dir,
                         override=override,
                         file_format=file_format,
                         nbr_workers=nbr_workers,
                         int2str_len=int2str_len)

        self.channel_names = []

    def set_frame_info(self, meta_summary):
        """
        Sets frame shape, im_colors and bit_depth for the class
        Must be called once before setting global metadata
        :param dict meta_summary: Metadata summary
        """
        self.frame_shape = [meta_summary["Height"], meta_summary["Width"]]
        pixel_type = meta_summary["PixelType"]
        self.im_colors = 3
        if pixel_type.find("GRAY") >= 0:
            self.im_colors = 1
        if meta_summary["BitDepth"] == 16:
            self.bit_depth = "uint16"
        elif meta_summary["BitDepth"] == 8:
            self.bit_depth = "uint8"
        else:
            print("Bit depth must be 16 or 8, not {}".format(
                meta_summary["BitDepth"]))
            raise ValueError

    def _set_frame_meta(self, parse_func, file_name):
        """
        Since information is assumed to be contained in the file name,
        dedicated functions to parse file names are in aux_utils.
        This function uses this parse_func to find important information like
        channel name and indices from the file name.

        :param function parse_func: Function in aux_utils
        :param str file_name: File name or path
        :return dict meta_row: Structured metadata for frame
        """
        meta_row = dict.fromkeys(meta_utils.DF_NAMES)
        parse_func(file_name, self.channel_names, meta_row)

        meta_row["file_name"] = self._get_imname(meta_row)
        meta_row["sha256"] = self._generate_hash(self.im_stack)[0]

        # Make sure meta row is properly filled
        assert None not in meta_row.values(), \
            "meta row has not been populated correctly"
        return meta_row

    def get_frames_and_metadata(self, filename_parser=None):
        """
        Global metadata dict is assumed to be in the same folder in a file
        named metadata.txt
        Frame metadata is extracted from each frame, and frames are uploaded
        on a file by file basis
        """
        assert os.path.isdir(self.data_path), \
            "Directory doesn't exist: {}".format(self.data_path)

        frame_paths = natsort.natsorted(
            glob.glob(os.path.join(self.data_path, "*.tif")),
        )
        nbr_frames = len(frame_paths)

        try:
            self.global_json = json_validator.read_json_file(
                os.path.join(self.data_path, "metadata.txt"),
            )
        except FileNotFoundError as e:
            print("can't find metadata.txt file, global json will be empty", e)
            self.global_json = {}

        self.set_frame_info(self.global_json["Summary"])
        # Create empty image stack where last dimension is 1 for upload_frames
        self.im_stack = np.empty((self.frame_shape[0],
                                  self.frame_shape[1],
                                  self.im_colors,
                                  1),
                                 dtype=self.bit_depth)

        self.frames_meta = meta_utils.make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        if filename_parser is not None:
            parse_func = getattr(aux_utils, filename_parser)
        else:
            raise ValueError("File name must be parsed using aux utils function")

        # Loop over all the frames to get data and metadata
        for i, frame_path in enumerate(frame_paths):
            imtif = tifffile.TiffFile(frame_path)
            self.im_stack[..., 0] = np.atleast_3d(imtif.asarray())
            tiftags = imtif.pages[0].tags
            # Get all frame specific metadata
            dict_i = {}
            for t in tiftags.keys():
                dict_i[t] = tiftags[t].value
            self.frames_json.append(dict_i)
            # Get structured frames metadata
            self.frames_meta.loc[i] = self._set_frame_meta(
                parse_func=parse_func,
                file_name=frame_path,
            )
            self.upload_stack(
                file_names=[self.frames_meta.loc[i, "file_name"]],
                im_stack=self.im_stack,
            )
        # Set global metadata
        self.set_global_meta(nbr_frames=nbr_frames)