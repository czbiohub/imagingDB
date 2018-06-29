# coding=utf-8

from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, backref

from imaging_db.database.base import Base


class ImageSlices(Base):
    """
    Table for individual 2D slices, which has a many to one mapping
    to image_files (which lists global information for the image stack)

    Local metadata contain the following columns:
    'ChannelIndex',
     'Slice',
     'FrameIndex',
     'Exposure-ms',
     'ChNames',
     'FileName'

    Plus a JSONB object with any additional slice information
    """
    __tablename__ = 'image_slices'

    id = Column(Integer, primary_key=True)
    channel_idx = Column(Integer)
    slice_idx = Column(Integer)
    frame_idx = Column(Integer)
    channel_name = Column(String)
    exposure_ms = Column(Numeric)
    file_name = Column(String)
    metadata_json = Column(JSONB)
    image_id = Column(Integer, ForeignKey('image_file.id'))
    image_file = relationship("ImageFile", backref="image_slices")

    def __init__(self,
                 channel_idx,
                 slice_idx,
                 frame_idx,
                 exposure_ms,
                 channel_name,
                 file_name,
                 metadata_json,
                 image_file):
        self.channel_idx = channel_idx
        self.slice_idx = slice_idx
        self.frame_idx = frame_idx
        self.channel_name = channel_name
        self.exposure_ms = exposure_ms
        self.file_name = file_name
        self.metadata_json = metadata_json
        self.image_file = image_file
