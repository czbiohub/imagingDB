# coding=utf-8

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, backref

from imaging_db.database.base import Base


class FileGlobal(Base):
    """
    Table for files that are uploaded to S3 as is, without being read
    or have its contents verified in any way
    """
    __tablename__ = 'file_global'

    id = Column(Integer, primary_key=True)
    s3_dir = Column(String)
    file_name = Column(String)
    # Add potential to throw whatever metadata they want
    # in a JSONB object
    metadata_json = Column(JSONB)
    dataset_id = Column(Integer, ForeignKey('data_set.id'))
    sha256 = Column(String)
    # Provide one to one mapping with dataset
    data_set = relationship("DataSet",
                            backref=backref("file_global", uselist=False))

    def __init__(self, s3_dir, file_name, metadata_json, data_set, sha256):
        self.s3_dir = s3_dir
        self.file_name = file_name
        self.metadata_json = metadata_json
        self.data_set = data_set
        self.sha256 = sha256
