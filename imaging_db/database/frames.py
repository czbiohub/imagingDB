# coding=utf-8

from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, backref

from imaging_db.database.base import Base


class Frames(Base):
    """
    Table for individual 2D frames, which has a many to one mapping
    to frames_global (which lists global information for the image stack).
    """
    __tablename__ = 'frames'

    id = Column(Integer, primary_key=True)
    channel_idx = Column(Integer)
    slice_idx = Column(Integer)
    time_idx = Column(Integer)
    pos_idx = Column(Integer)
    channel_name = Column(String)
    file_name = Column(String)
    sha256 = Column(String)
    metadata_json = Column(JSONB)
    frames_global_id = Column(Integer, ForeignKey('frames_global.id'))
    frames_global = relationship("FramesGlobal", backref="frames")

    def __init__(self,
                 channel_idx,
                 slice_idx,
                 time_idx,
                 pos_idx,
                 channel_name,
                 file_name,
                 sha256,
                 metadata_json,
                 frames_global):
        self.channel_idx = channel_idx
        self.slice_idx = slice_idx
        self.time_idx = time_idx
        self.pos_idx = pos_idx
        self.channel_name = channel_name
        self.file_name = file_name
        self.sha256 = sha256
        self.metadata_json = metadata_json
        self.frames_global = frames_global
