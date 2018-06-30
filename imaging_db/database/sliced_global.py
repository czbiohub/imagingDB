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
    bit_depth = Column(String)
    # Add potential to throw whatever metadata they want
    # in a JSONB object
    metadata_json = Column(JSONB)
    # Map project id
    project_id = Column(Integer, ForeignKey('project.id'))
    # Provide one to one mapping with project
    project = relationship("Project",
                           backref=backref("sliced_global", uselist=False))

    def __init__(self,
                 nbr_frames,
                 im_width,
                 im_height,
                 bit_depth,
                 metadata_json,
                 project):
        self.nbr_frames = nbr_frames
        self.im_width = im_width
        self.im_height = im_height
        self.bit_depth = bit_depth
        self.metadata_json = metadata_json
        self.project = project

