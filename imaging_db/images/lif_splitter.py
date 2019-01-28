import numpy as np
import os
import pims

import imaging_db.images.file_splitter as file_splitter
import imaging_db.utils.meta_utils as meta_utils


class LifSplitter(file_splitter.FileSplitter):
    """
    Subclass for reading and splitting Leica Lif files into frames and
    metadata. It relies on PIMS, which in turn uses jpype to bridge
    to Bioformats which is written in Java.
    """
    def set_frame_info(self, meta, im):
        """
        Sets frame shape, im_colors and bit_depth for the class
        Must be called once before setting global metadata
        Assumes shapes and types are same across acquisition

        :param bioformats meta: Metadata
        :param array im: First frame so we don't have to rely on
            guessing Lif's image dimension definitions
        """
        # Encode color channel information
        self.im_colors = 1
        im_shape = im.shape
        if len(im_shape) > 2:
            self.im_colors = im_shape[2]
        # Assuming lif has same
        self.frame_shape = [im_shape[0],
                            im_shape[1]]

        self.bit_depth = meta.PixelsType(0)
        assert self.bit_depth in {'uint8', 'uint16'},\
            "Only support uint8 and uint16, not {}".format(self.bit_depth)


    def get_frames_and_metadata(self):
        """
        Reads lif files into memory and separates image frames and metadata.
        """
        assert os.path.isfile(self.data_path), \
            "File doesn't exist: {}".format(self.data_path)

        reader = pims.bioformats.BioformatsReader(self.data_path)
        # Get metadata
        meta = reader.metadata
        # Assuming images are acquired as "series" and meta contains count
        nbr_frames = meta.ImageCount()
        self.set_frame_info(meta, reader[0])

        # Create image stack with image bit depth 16 or 8
        self.im_stack = np.empty((self.frame_shape[0],
                                  self.frame_shape[1],
                                  self.im_colors,
                                  nbr_frames),
                                 dtype=self.bit_depth)

        # Get global json metadata
        self.global_json = {"file_origin": self.data_path}

        # Convert frames to numpy stack and collect metadata
        self.frames_meta = meta_utils.make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        # Loop over all the frames to get data and metadata
        # I don't know what index that is increasing so I'll update pos
        for i in range(nbr_frames):
            reader.series = i
            try:
                im = reader[0]
            except ValueError as e:
                raise("Can't read page {} in {}. {}",
                      i, self.data_path, e)

            self.im_stack[..., i] = np.atleast_3d(im)

            meta = reader.metadata
            # Get all frame specific metadata
            dict_i = {}
            for meta_field in meta.fields:
                # Some meta fields you can access with series index
                # the other ones I don't know what to do with
                try:
                    str_eval = 'meta.' + meta_field + '(0)'
                    dict_i[meta_field] = eval(str_eval)
                except TypeError as e:
                    # Try no args
                    try:
                        str_eval = 'meta.' + meta_field + '()'
                        dict_i[meta_field] = eval(str_eval)
                    except TypeError as e:
                        try:
                            str_eval = 'meta.' + meta_field + '(0, 0)'
                            dict_i[meta_field] = eval(str_eval)
                        except TypeError as e:
                            print("Can't read {}".format(meta_field))
            # TODO: You can also loop through dir(reader) :-(
            self.frames_json.append(dict_i)

            meta_row = dict.fromkeys(meta_utils.DF_NAMES)
            meta_row["channel_name"] = None
            meta_row["channel_idx"] = 0
            meta_row["time_idx"] = 0
            meta_row["pos_idx"] = i
            meta_row["slice_idx"] = 0
            meta_row["file_name"] = self._get_imname(meta_row)
            self.frames_meta.loc[i] = meta_row

        # Set global metadata
        self.set_global_meta(nbr_frames=nbr_frames)
        # self.upload_stack(
        #     file_names=self.frames_meta["file_name"],
        #     im_stack=self.im_stack,
        # )
