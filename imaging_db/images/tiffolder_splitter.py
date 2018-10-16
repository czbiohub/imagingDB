import glob
import numpy as np
import os
import tifffile

import imaging_db.images.file_splitter as file_splitter
import imaging_db.metadata.json_validator as json_validator


class TifFolderSplitter(file_splitter.FileSplitter):
    """
    Subclass for reading all tiff files in a folder
    """

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

    def _set_frame_meta_from_name(self, im_path, channel_names):
        """
        Assume file follows naming convention
        img_channelname_t***_p***_z***.tif

        Populates the frames_meta dict keys:
        "channel_idx", "slice_idx", "time_idx", "channel_name",
        "file_name", "pos_idx"
        :param im_path: Path to frame
        :return dict meta_row: Metadata for frame (one row in dataframe)
        """
        im_name = os.path.basename(im_path)[:-4]
        str_split = im_name.split("_")[1:]
        meta_row = dict.fromkeys(file_splitter.DF_NAMES)
        for s in str_split:
            # This is assuming no channel is named e.g. txxx
            if s in channel_names:
                meta_row["channel_name"] = s
                # Index channels by names
                meta_row["channel_idx"] = channel_names.index(s)
            elif s.find("t") == 0 and len(s) == 4:
                meta_row["time_idx"] = int(s[1:])
            elif s.find("p") == 0 and len(s) == 4:
                meta_row["pos_idx"] = int(s[1:])
            elif s.find("z") == 0 and len(s) == 4:
                meta_row["slice_idx"] = int(s[1:])
        meta_row["file_name"] = self._get_imname(meta_row)
        # Make sure meta row is properly filled
        assert None not in meta_row.values(),\
            "meta row has not been populated correctly"
        return meta_row

    def get_frames_and_metadata(self):
        """
        Global metadata dict is assumed to be in the same folder in a file
        named metadata.txt
        Frame metadata is extracted from each frame, and frames are uploaded
        on a file by file basis
        File naming convention is assumed to be:
        img_channelname_t***_p***_z***.tif
        """
        assert os.path.isdir(self.data_path), \
            "Directory doesn't exist: {}".format(self.data_path)

        frame_paths = glob.glob(os.path.join(self.data_path, "*.tif"))
        nbr_frames = len(frame_paths)

        self.global_json = json_validator.read_json_file(
            os.path.join(self.data_path, "metadata.txt"),
        )
        channel_names = self.global_json["Summary"]["ChNames"]
        self.set_frame_info(self.global_json["Summary"])
        # Create empty image stack where last dimension is 1 for upload_frames
        im_stack = np.empty((self.frame_shape[0],
                                  self.frame_shape[1],
                                  self.im_colors,
                                  1),
                                 dtype=self.bit_depth)
        self.frames_meta = file_splitter.make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        # Loop over all the frames to get data and metadata
        for i, frame_path in enumerate(frame_paths):
            imtif = tifffile.TiffFile(frame_path)
            im_stack[..., 0] = np.atleast_3d(imtif.asarray())
            tiftags = imtif.pages[0].tags
            # Get all frame specific metadata
            dict_i = {}
            for t in tiftags.keys():
                dict_i[t] = tiftags[t].value
            self.frames_json.append(dict_i)
            self.frames_meta.loc[i] = self._set_frame_meta_from_name(
                im_path=frame_path,
                channel_names=channel_names,
            )
            self.upload_stack(
                file_names=[self.frames_meta.loc[i, "file_name"]],
                im_stack=im_stack,
            )
        # Set global metadata
        self.set_global_meta(nbr_frames=nbr_frames)