import uuid
from oslo_utils import timeutils
from oslo_db.sqlalchemy import models
from sqlalchemy import Column, DateTime, String, Integer
from sqlalchemy.ext.declarative import declarative_base


BASE = declarative_base()
ARGS = {'mysql_charset': "utf8"}


class V2VDBBase(models.TimestampMixin, models.ModelBase):
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), default=str(uuid.uuid4()), index=True)
    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime, default=timeutils.utcnow, onupdate=timeutils.utcnow)


class Openstack(BASE, V2VDBBase):
    """Openstack cloud table"""

    __tablename__ = 'openstack'

    name = Column(String(128))
    platform = Column(String(128))
    auth_url = Column(String(128))
    username = Column(String(128))
    password = Column(String(255))
    project_name = Column(String(128))
    project_domain_name = Column(String(128))
    user_domain_name = Column(String(128))


class VMware(BASE, V2VDBBase):
    """VMware cloud table"""

    __tablename__ = 'vmware'

    name = Column(String(128))
    platform = Column(String(128))
    ip = Column(String(128))
    user = Column(String(255))
    password = Column(String(255))
    uri = Column(String(255))

class Task(BASE, V2VDBBase):
    """task table"""

    __tablename__ = 'task'

    src_cloud = Column(String(36), nullable=False)
    src_server = Column(String(255), nullable=False)
    dest_cloud = Column(String(36), nullable=False)
    dest_server = Column(String(255), nullable=False)
    state = Column(String(36))
    percent = Column(Integer)


class License(BASE, V2VDBBase):
    """license table"""

    __tablename__ = 'license'

    license = Column(String(2048))
