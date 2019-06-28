import concurrent.futures
import glob
import json
import natsort
import os
import tifffile

import imaging_db.images.file_splitter as file_splitter
import imaging_db.images.filename_parsers as file_parsers
import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.metadata.json_operations as json_ops
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
                 int2str_len=3):
        
        super().__init__(data_path,
                         s3_dir,
                         override=override,
                         file_format=file_format,
                         nbr_workers=nbr_workers,
                         int2str_len=int2str_len)

        self.channel_names = []

        global data_uploader
        data_uploader = s3_storage.DataStorage(
            s3_dir=self.s3_dir,
            nbr_workers=self.nbr_workers,
        )
        if not override:
            data_uploader.assert_unique_id()

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
        dedicated functions to parse file names are in filename_parsers.
        This function uses this parse_func to find important information like
        channel name and indices from the file name.

        :param function parse_func: Function in filename_parsers
        :param str file_name: File name or path
        :return dict meta_row: Structured metadata for frame
        """
        meta_row = dict.fromkeys(meta_utils.DF_NAMES)
        parse_func(file_name, meta_row, self.channel_names)

        meta_row["file_name"] = self._get_imname(meta_row)
        return meta_row

    def serialize_upload(self, frame_file_tuple):
        """
        Given a path for a tif file and its database file name,
        read the file, serialize it and upload it. Extract file metadata.

        :param tuple frame_file_tuple: Path to tif file and S3 + DB file name
        :return str sha256: Checksum for image
        :return dict dict_i: JSON metadata for frame
        """
        frame_path, file_name = frame_file_tuple
        im = tifffile.TiffFile(frame_path)
        tiftags = im.pages[0].tags
        # Get all frame specific metadata
        dict_i = {}
        for t in tiftags.keys():
            dict_i[t] = tiftags[t].value

        im = im.asarray()
        sha256 = meta_utils.gen_sha256(im)
        # Upload to S3 with global client
        data_uploader.upload_im(
            file_name=file_name,
            im=im,
            file_format=self.file_format,
        )
        # Do a json dumps otherwise some metadata won't pickle
        return sha256, json.dumps(dict_i)

    def get_frames_and_metadata(self, filename_parser='parse_idx_from_name'):
        """
        Frame metadata is extracted from each frame, and frames are uploaded
        on a file by file basis.
        Since metadata is separated from files, the file name must contain the
        required indices channel_idx, slice_idx, time and pos_idx. By default,
        it will assume that the file name contains 4 integers corresponding to
        these 4 indices. If that's not the case, you can specify a custom parser
        in filename_parsers.
        Global metadata dict is assumed to be in the same folder in a file
        named metadata.txt (optional).

        :param str filename_parser:
        """
        assert os.path.isdir(self.data_path), \
            "Directory doesn't exist: {}".format(self.data_path)

        try:
            parse_func = getattr(file_parsers, filename_parser)
        except AttributeError as e:
            raise AttributeError(
                "Must use filename_parsers function for file name. {}".format(e))

        frame_paths = natsort.natsorted(
            glob.glob(os.path.join(self.data_path, "*.tif")),
        )
        nbr_frames = len(frame_paths)

        try:
            self.global_json = json_ops.read_json_file(
                os.path.join(self.data_path, "metadata.txt"),
            )
        except FileNotFoundError as e:
            raise FileNotFoundError("Can't find metadata.txt file in directory", e)

        self.set_frame_info(self.global_json["Summary"])

        self.frames_meta = meta_utils.make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        # Loop over all the frames to get metadata
        for i, frame_path in enumerate(frame_paths):
            # Get structured frames metadata
            self.frames_meta.loc[i] = self._set_frame_meta(
                parse_func=parse_func,
                file_name=frame_path,
            )
        # Use multiprocessing for more efficient file read and upload
        file_names = self.frames_meta['file_name']
        with concurrent.futures.ProcessPoolExecutor(self.nbr_workers) as ex:
            res = ex.map(self.serialize_upload, zip(frame_paths, file_names))
        # Collect metadata for each uploaded file
        for i, (sha256, dict_i) in enumerate(res):
            self.frames_json.append(json.loads(dict_i))
            self.frames_meta.loc[i, 'sha256'] = sha256
        # Set global metadata
        self.set_global_meta(nbr_frames=nbr_frames)
