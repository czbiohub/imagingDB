import concurrent.futures
import cv2
import os
import shutil

import imaging_db.filestorage.data_storage as data_storage


class LocalStorage(data_storage.DataStorage):
    """Class for handling image and file transfers to local storage"""

    def __init__(self,
                 storage_dir,
                 nbr_workers=None,
                 access_point=None):
        """
        Local storage is assumed to be mounted at STORAGE_MOUNT_POINT
        unless otherwise specified.

        Main directories for both S3 and local storage are

        raw_frames: For datasets that have been parsed into individual
            2D frames with indices channels, timepoints, slices and positions.
        raw_files: For files that have not been separated into frames + metadata.
            They're copied to storage as is.

        :param str storage_dir: Directory name (dataset ID) in raw_frames or
        raw_files (e.g. raw_frames/ID-YYYY-MM-DD-HH-MM-SS-SSSS)
        :param int nbr_workers: Number of workers for uploads/downloads
        :param str/None access_point: Path to where local storage is mounted.
            Default mount point: /Volumes/data_lg/czbiohub-imaging
        """
        super().__init__(storage_dir=storage_dir,
                         nbr_workers=nbr_workers,
                         access_point=access_point)

        if self.access_point is None:
            self.mount_point = data_storage.STORAGE_MOUNT_POINT
        else:
            self.mount_point = self.access_point
        assert os.path.exists(self.mount_point),\
            "Make sure local storage is mounted, dir {} doesn't exist".format(
                self.mount_point,
            )
        # Path to dataset ID directory in storage
        # mount point + raw files/frames + dataset ID
        self.id_storage_path = os.path.join(self.mount_point, self.storage_dir)

    def assert_unique_id(self):
        """
        Makes sure directory with dataset ID doesn't already exist in storage

        :raise AssertionError: if directory exists
        """
        assert os.path.exists(self.id_storage_path) is False,\
            "ID {} already exists in storage".format(self.id_storage_path)

    def nonexistent_storage_path(self, storage_path):
        """
        Checks that a given path to a file in storage doesn't already exist.

        :param str storage_path: Path in local storage
        :return bool: True if file doesn't exist in storage, False otherwise
        """
        dir_path = os.path.join(self.mount_point, storage_path)
        if not os.path.exists(dir_path):
            return True
        else:
            return False

    def get_storage_path(self, file_name):
        """
        Given a file name without path, return full storage path,
        given mount point and storage directory.

        :param str file_name: File name with extension, no path
        :return str storage_path: Full path to file in storage
        """
        storage_path = os.path.join(
            self.id_storage_path,
            file_name,
        )
        return storage_path

    def upload_frames(self, file_names, im_stack, file_format=".png"):
        """
        Writes all frames to storage using threading or multiprocessing

        :param list file_names: Image file names (str), with extension, no path
        :param np.array im_stack: all 2D frames from file converted to stack
        :param str file_format: file format for frames to be written in storage
        """
        # Create directory if it doesn't exist already
        os.makedirs(self.id_storage_path, exist_ok=True)
        # Make sure number of file names matches stack shape
        assert len(file_names) == im_stack.shape[-1], \
            "Number of file names {} doesn't match frames {}".format(
                len(file_names), im_stack.shape[-1])

        path_im_tuples = []
        for i, file_name in enumerate(file_names):
            storage_path = self.get_storage_path(file_name)
            path_im_tuples.append((storage_path, im_stack[..., i]))

        with concurrent.futures.ProcessPoolExecutor(self.nbr_workers) as ex:
            ex.map(self.upload_im_tuple, path_im_tuples)

    def upload_im_tuple(self, path_im_tuple):
        """
        Save image to storage after checking that the path to file doesn't
        already exist in storage.

        :param tuple path_im_tuple: (File name str and image np.array)
        """
        (im_path, im) = path_im_tuple
        if self.nonexistent_storage_path(im_path):
            os.makedirs(self.id_storage_path, exist_ok=True)
            check = cv2.imwrite(im_path, im)
        else:
            print("File {} already exists.".format(im_path))

    def upload_im(self, im_name, im, file_format='.png'):
        """
        Save image to storage after checking that the path to file doesn't
        already exist in storage.

        :param str im_name: File name for image, with extension, no path
        :param np.array im: 2D image
        :param str file_format: File format for writing image
        """
        im_path = self.get_storage_path(im_name)
        if self.nonexistent_storage_path(im_path):
            os.makedirs(self.id_storage_path, exist_ok=True)
            cv2.imwrite(im_path, im)
        else:
            print("File {} already exists.".format(im_path))

    def upload_file(self, file_path):
        """
        Upload a single file to storage by copying (file is not opened).

        :param str file_path: full path to local file to be moved to storage
        """
        # ID should be unique, make sure it doesn't already exist
        self.assert_unique_id()
        # Create directory for file
        os.makedirs(self.id_storage_path, exist_ok=True)

        file_name = os.path.basename(file_path)
        save_path = self.get_storage_path(file_name)
        shutil.copy(file_path, save_path)

    def get_im(self, file_name):
        """
        Given file name, fetch 2D image (frame) from storage.
        File name consists of raw_files/raw_frames + dataset ID +
        image name (im_c***_z***_t***_p***.png)

        :param str file_name: File name of 2D image (frame)
        :return np.array im: 2D image
        """
        im_path = self.get_storage_path(file_name)
        im = cv2.imread(im_path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
        return im

    def download_file(self, file_name, dest_dir):
        """
        Downloads/copies a single file from storage to local destination without
        reading it.

        :param str file_name: File name
        :param str dest_dir: Destination directory name
        """
        storage_path = self.get_storage_path(file_name)
        dest_path = os.path.join(dest_dir, file_name)
        shutil.copy(storage_path, dest_path)
