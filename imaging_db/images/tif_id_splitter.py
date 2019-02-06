import itertools
import numpy as np
import os
import tifffile

import imaging_db.images.file_splitter as file_splitter
import imaging_db.utils.aux_utils as aux_utils
import imaging_db.utils.meta_utils as meta_utils


class TifIDSplitter(file_splitter.FileSplitter):
    """
    Subclass for reading and splitting tif files that are missing MicroManager
    metadata. It relies on the ImageDescription tag, which is assumed to
    be a sting encoding 'nchannels', ''nslices' etc.
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
        indices = {
            'nbr_channels': 1,
            'nbr_timepoints': 1,
            'nbr_slices': 1,
            'nbr_positions': 1,
        }
        for s in str_split:
            # Haven't seen an example of pos and slices so can't encode them
            if s.find("channels") == 0:
                indices['nbr_channels'] = int(s.split("=")[1])
            if s.find("frames") == 0:
                indices['nbr_timepoints'] = int(s.split("=")[1])
            if s.find("slices") == 0:
                indices['nbr_slices'] = int(s.split("=")[1])
            if s.find("positions") == 0:
                indices['nbr_positions'] = int(s.split("=")[1])
        return indices

    def get_frames_and_metadata(self, filename_parser=None):
        """
        Reads tif files into memory and separates image frames and metadata.
        Use this class if no MicroManagerMetadata tag is present, but you
        have an ImageDescription tag.
        It assumes that if there are any information number of channels,
        slices, timepoints or positions, the info is embedded as a string in
        the ImageDescription tag of the first frame.
        It assumes the acquisition order is:
         1) channels, 2) slices, 3) positions, 4) frames.
        There is no way of validating the order because only the number
        of each is specified, so use at your own risk.

        :param str filename_parser: Optional function name that will
            generate global json metadata from file name.
        """
        assert os.path.isfile(self.data_path), \
            "File doesn't exist: {}".format(self.data_path)

        frames = tifffile.TiffFile(self.data_path)
        # Get global metadata
        page = frames.pages[0]
        nbr_frames = len(frames.pages)
        float2uint = self.set_frame_info(page)
        # Create image stack with image bit depth 16 or 8
        self.im_stack = np.empty((self.frame_shape[0],
                                  self.frame_shape[1],
                                  self.im_colors,
                                  nbr_frames),
                                 dtype=self.bit_depth)

        # Get what little channel info there is from image description
        indices = self._get_params_from_str(
            page.tags["ImageDescription"].value,
        )
        # Get global json metadata
        if filename_parser is not None:
            parse_func = getattr(aux_utils, filename_parser)
            self.global_json = parse_func(self.data_path)
        else:
            self.global_json = {}
        self.global_json["file_origin"] = self.data_path

        # Convert frames to numpy stack and collect metadata
        self.frames_meta = meta_utils.make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        # Loop over all the frames to get data and metadata
        variable_iterator = itertools.product(
            range(indices['nbr_timepoints']),
            range(indices['nbr_positions']),
            range(indices['nbr_slices']),
            range(indices['nbr_channels']),
        )
        for i, (time_idx, pos_idx, slice_idx, channel_idx) in \
                enumerate(variable_iterator):
            page = frames.pages[i]
            try:
                im = page.asarray()
            except ValueError as e:
                print("Can't read page ", i, self.data_path)
                raise e

            if float2uint:
                assert im.max() < 65536, "Im > 16 bit, max: {}".format(im.max())
                im = im.astype(np.uint16)

            self.im_stack[..., i] = np.atleast_3d(im)

            tiftags = page.tags
            # Get all frame specific metadata
            dict_i = {}
            for t in tiftags.keys():
                # IJMeta often contain an ndarray LUT which is not serializable
                if t != 'IJMetadata':
                    dict_i[t] = tiftags[t].value
            self.frames_json.append(dict_i)

            meta_row = dict.fromkeys(meta_utils.DF_NAMES)
            meta_row["channel_name"] = None
            meta_row["channel_idx"] = channel_idx
            meta_row["time_idx"] = time_idx
            meta_row["pos_idx"] = pos_idx
            meta_row["slice_idx"] = slice_idx
            meta_row["file_name"] = self._get_imname(meta_row)
            self.frames_meta.loc[i] = meta_row


        sha = self._generate_hash(self.im_stack)
        self.frames_meta['sha256'] = sha

        # Set global metadata
        self.set_global_meta(nbr_frames=nbr_frames)
        self.upload_stack(
            file_names=self.frames_meta["file_name"],
            im_stack=self.im_stack,
        )