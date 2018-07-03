# coding=utf-8

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, backref

from imaging_db.database.base import Base


class SlicedGlobal(Base):
    """
    Table for files that have been decomposed into 2D slices
    """
    __tablename__ = 'sliced_global'

    id = Column(Integer, primary_key=True)
    nbr_frames = Column(Integer)
    im_width = Column(Integer)
    im_height = Column(Integer)
    im_colors = Column(Integer)
    bit_depth = Column(String)
    folder_name = Column(String)
    # Add potential to throw whatever metadata they want
    # in a JSONB object
    metadata_json = Column(JSONB)
    # Map project id
    dataset_id = Column(Integer, ForeignKey('data_set.id'))
    # Provide one to one mapping with dataset
    data_set = relationship("DataSet",
                           backref=backref("sliced_global", uselist=False))

    def __init__(self,
                 nbr_frames,
                 im_width,
                 im_height,
                 im_colors,
                 bit_depth,
                 folder_name,
                 metadata_json,
                 data_set):
        self.nbr_frames = nbr_frames
        self.im_width = im_width
        self.im_height = im_height
        self.im_colors = im_colors
        self.bit_depth = bit_depth
        self.folder_name = folder_name
        self.metadata_json = metadata_json
        self.data_set = data_set
