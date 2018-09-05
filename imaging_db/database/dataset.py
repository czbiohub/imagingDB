# coding=utf-8

from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime

from imaging_db.database.base import Base


def _serial_to_date_time(dataset_serial):
    substrs = dataset_serial.split("-")
    date_time = datetime(int(substrs[1]),  # year
                         int(substrs[2]),  # month
                         int(substrs[3]),  # day
                         int(substrs[4]),  # hour
                         int(substrs[5]),  # minute
                         int(substrs[6]),  # second
                         )
    return date_time


class DataSet(Base):
    __tablename__ = 'data_set'

    id = Column(Integer, primary_key=True)
    dataset_serial = Column(String)
    description = Column(String)
    microscope = Column(String)
    frames = Column(Boolean)
    date_time = Column(DateTime)
    parent_id = Column(Integer, ForeignKey("data_set.id"))

    def __init__(self, dataset_serial, description, microscope, frames, parent_id):
        self.dataset_serial = dataset_serial
        self.description = description
        self.microscope = microscope
        self.frames = frames
        self.date_time = _serial_to_date_time(dataset_serial)
        self.parent_id = parent_id
