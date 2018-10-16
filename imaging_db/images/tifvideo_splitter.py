import itertools
import numpy as np
import os
import tifffile

import imaging_db.images.file_splitter as file_splitter


class TifVideoSplitter(file_splitter.FileSplitter):
    """
    Subclass for reading and splitting tif videos
    """
    def set_frame_info(self, page):
        """
        Sets frame shape, im_colors and bit_depth for the class
        Must be called once before setting global metadata

        :param page page: Page read from tifffile
        :return bool float2uint: True if bit depth is 32
        """
        # Encode color channel information
        self.im_colors = page.tags["SamplesPerPixel"].value
        self.frame_shape = [page.tags["ImageLength"].value,
                            page.tags["ImageWidth"].value]

        bits_val = page.tags["BitsPerSample"].value
        float2uint = False
        if bits_val == 16:
            self.bit_depth = "uint16"
        elif bits_val == 8:
            self.bit_depth = "uint8"
        elif bits_val == 32:
            # Convert 32 bit float to uint16, the values seem to be ints anyway
            self.bit_depth = "uint16"
            float2uint = True
        else:
            print("Bit depth must be 16 or 8, not {}".format(bits_val))
            raise ValueError
        return float2uint

    def _get_params_from_str(self, im_description):
        """
        Get channels and timepoints from ImageJ tag encoded as string with line
        breaks.

        :param str im_description: ImageJ tag
        :return int nbr_channels: Number of channels
        :return int nbr_timepoints: Number of timepoints
        """
        # Split on new lines
        str_split = im_description.split("\n")
        nbr_channels = 1
        nbr_timepoints = 1
        for s in str_split:
            # Haven't seen an example of pos and slices so can't encode them
            if s.find("channels") == 0:
                nbr_channels = int(s.split("=")[1])
            if s.find("frames") == 0:
                nbr_timepoints = int(s.split("=")[1])
        return nbr_channels, nbr_timepoints

    def get_frames_and_metadata(self):
        """
        reads tif videos into memory and separates image frames and metadata.
        It assumes channel and frame info is in the ImageDescription tag
        It also assumes order aquired is channel followed by frames since it's
        a time series.
        """
        assert os.path.isfile(self.data_path), \
            "File doesn't exist: {}".format(self.data_path)

        frames = tifffile.TiffFile(self.data_path)
        # Get global metadata
        page = frames.pages[0]
        nbr_frames = len(frames.pages)
        float2uint = self.set_frame_info(page)

        # Create image stack with image bit depth 16 or 8
        self.im_stack = np.empty((self.fframe_shape[0],
                                  self.frame_shape[1],
                                  self.im_colors,
                                  nbr_frames),
                                 dtype=self.bit_depth)

        # Get what little channel info there is from image description
        nbr_channels, nbr_timepoints = self._get_params_from_str(
            page.tags["ImageDescription"].value,
        )
        self.global_json = {"file_origin": self.data_path}

        # Convert frames to numpy stack and collect metadata
        self.frames_meta = file_splitter.make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        # Loop over all the frames to get data and metadata
        variable_iterator = itertools.product(
            range(nbr_timepoints),
            range(nbr_channels),
        )
        for i, (time_idx, channel_idx) in enumerate(variable_iterator):
            page = frames.pages[i]
            im = page.asarray()
            if float2uint:
                assert im.max() < 65536, "Im > 16 bit, max: {}".format(im.max())
                im = im.astype(np.uint16)

            self.im_stack[..., i] = np.atleast_3d(im)

            tiftags = page.tags
            # Get all frame specific metadata
            dict_i = {}
            for t in tiftags.keys():
                dict_i[t] = tiftags[t].value
            self.frames_json.append(dict_i)

            meta_row = dict.fromkeys(DF_NAMES)
            meta_row["channel_name"] = None
            meta_row["channel_idx"] = channel_idx
            meta_row["time_idx"] = time_idx
            meta_row["pos_idx"] = 0
            meta_row["slice_idx"] = 0
            meta_row["file_name"] = self._get_imname(meta_row)
            self.frames_meta.loc[i] = meta_row

        # Set global metadata
        self.set_global_meta(nbr_frames=nbr_frames)
        self.upload_stack(
            file_names=self.frames_meta["file_name"],
            im_stack=self.im_stack,
        )