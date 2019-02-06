import numpy as np
import os
import sys

import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.database.db_session as db_session
import imaging_db.utils.meta_utils as meta_utils

# Edit this depending on where your database credential file is stored
# This assumes it's stored in dir above imagingDB
dir_name = os.path.abspath(os.path.join('..'))
credentials_filename = os.path.join(dir_name, 'db_credentials.json')
dest_dir = os.path.join(dir_name, 'temp_downloads')
os.makedirs(dest_dir, exist_ok=True)

# Get files and compute checksums
with db_session.session_scope(credentials_filename) as session:
    files = session.query(db_session.FileGlobal)
    for file in files:
        if file.sha256 is None:
            data_loader = s3_storage.DataStorage(
                s3_dir=file.s3_dir,
            )
            file_name = file.metadata_json["file_origin"]
            file_name = file_name.split("/")[-1]
            dest_path = os.path.join(dest_dir, file_name)
            data_loader.download_file(
                file_name=file_name,
                dest_path=dest_path,
            )
            checksum = meta_utils.gen_sha256(dest_path)
            file.sha256 = checksum

# Get frames and compute checksums
with db_session.session_scope(credentials_filename) as session:
    frames = session.query(db_session.Frames)
    for frame in frames:
        if frame.sha256 is None:
            data_loader = s3_storage.DataStorage(
                s3_dir=frame.frames_global.s3_dir,
            )
            im = data_loader.get_im(frame.file_name)
            checksum = meta_utils.gen_sha256(im)
            frame.sha256 = checksum
