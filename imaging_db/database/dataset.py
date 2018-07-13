# coding=utf-8

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey

from imaging_db.database.base import Base


class DataSet(Base):
    __tablename__ = 'data_set'

    id = Column(Integer, primary_key=True)
    dataset_serial = Column(String)
    description = Column(String)
    microscope = Column(String)
    sliced = Column(Boolean)
    parent_id = Column(Integer, ForeignKey("data_set.id"))

    def __init__(self, dataset_serial, description, microscope, sliced, parent_id):
        self.dataset_serial = dataset_serial
        self.description = description
        self.microscope = microscope
        self.sliced = sliced
        self.parent_id = parent_id
