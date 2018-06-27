# coding=utf-8

from sqlalchemy import Column, String, Integer, Boolean

from imaging_db.database.base import Base


class Project(Base):
    __tablename__ = 'project'

    id = Column(Integer, primary_key=True)
    project_serial = Column(String)
    file_format = Column(String)
    sliced = Column(Boolean)

    def __init__(self, project_serial, file_format, sliced):
        self.project_serial = project_serial
        self.file_format = file_format
        self.sliced = sliced
