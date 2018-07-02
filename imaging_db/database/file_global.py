# coding=utf-8

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, backref

from imaging_db.database.base import Base


class FileGlobal(Base):
    """
    Table for files that are uploaded to S3 as is, most likely
    as a stack in some proprietary microscopy file format
    """
    __tablename__ = 'file_global'

    id = Column(Integer, primary_key=True)
    # Add potential to throw whatever metadata they want
    # in a JSONB object
    metadata_json = Column(JSONB)
    project_id = Column(Integer, ForeignKey('project.id'))
    # Provide one to one mapping with project
    project = relationship("Project",
                           backref=backref("file_global", uselist=False))

    def __init__(self, metadata_json, project):
        self.metadata_json = metadata_json
        self.project = project
