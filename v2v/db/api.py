import threading

from oslo_db import exception as db_exc
from oslo_db import options
from oslo_db.sqlalchemy import session as db_session
from oslo_log import log as logging
from dateutil import tz
from datetime import datetime

import v2v.conf
from v2v.db import models
from v2v.db.models import BASE
from v2v.i18n import _

CONF = v2v.conf.CONF
LOG = logging.getLogger(__name__)

options.set_defaults(CONF,
                     connection='mysql+pymysql://root:secret@localhost/v2v')

_LOCK = threading.Lock()
_FACADE = None


def _create_facade_lazily():
    global _LOCK
    with _LOCK:
        global _FACADE
        if _FACADE is None:
            _FACADE = db_session.EngineFacade(
                CONF.database.connection,
                **dict(CONF.database)
            )
        return _FACADE


def get_engine():
    facade = _create_facade_lazily()
    return facade.get_engine()


def get_session(**kwargs):
    facade = _create_facade_lazily()
    return facade.get_session(**kwargs)


def dispose_engine():
    get_engine().dispose()


def is_user_context(context):
    """Indicates if the request context is a normal user."""
    if not context:
        return False
    if context.is_admin:
        return False
    if not context.user_id or not context.project_id:
        return False
    return True


def register_models():
    # NOTE(lhx): register all models before invoking db api functions
    engine = get_engine()
    BASE.metadata.create_all(engine)


def unregister_models():
    engine = get_engine()
    BASE.metadata.drop_all(engine)


def model_query(context, model, *args, **kwargs):
    """Query helper that accounts for context's `read_deleted` field.

    :param context: context to query under
    :param session: if present, the session to use
    :param read_deleted: if present, overrides context's read_deleted field.
    """
    session = kwargs.get('session') or get_session()
    read_deleted = kwargs.get('read_deleted') or context.read_deleted

    query = session.query(model, *args)

    if read_deleted == 'no':
        query = query.filter_by(deleted=False)
    elif read_deleted == 'yes':
        pass  # omit the filter to include deleted and active
    elif read_deleted == 'only':
        query = query.filter_by(deleted=True)
    elif read_deleted == 'int_no':
        query = query.filter_by(deleted=0)
    else:
        raise Exception(
            _("Unrecognized read_deleted value '%s'") % read_deleted)

    return query


#########################
def create(obj):
    session = get_session()
    try:
        with session.begin():
            session.add(obj)
    except db_exc.DBDuplicateEntry:
        raise
    return obj


def get_all(model, to_dict=True):
    session = get_session()
    datas = session.query(model).order_by(model.id.desc()).all()
    if to_dict:
        return [data_to_dict(model, d) for d in datas]
    return datas


def task_get_all_by_filter(filters):
    session = get_session()
    if 'state' in filters:
        state = filters.pop('state')
        query = session.query(models.Task)
        return query.filter(models.Task.state.in_(state)).all()
    if 'dest_cloud' in filters:
        dest_cloud = filters.pop('dest_cloud')
        query = session.query(models.Task)
        return query.filter(models.Task.dest_cloud == dest_cloud).all()
    if 'src_cloud' in filters:
        src_cloud = filters.pop('src_cloud')
        query = session.query(models.Task)
        return query.filter(models.Task.src_cloud == src_cloud).all()


def get_by_uuid(model, uuid, to_dict=True):
    session = get_session()
    query = session.query(model)
    data = query.filter_by(uuid=uuid).first()
    if to_dict:
        return data_to_dict(model, data)
    return data


def delete_by_uuid(model, uuid):
    session = get_session()
    with session.begin():
        query = session.query(model)
        data = query.filter_by(uuid=uuid).first()
        if data is not None:
            session.delete(data)


def transfer_to_local_time(utc_time):
    # UTC Zone
    from_zone = tz.gettz('UTC')
    # China Zone
    to_zone = tz.gettz('CST')

    # Tell the datetime object that it's in UTC time zone
    utc = utc_time.replace(tzinfo=from_zone)

    # Convert time zone
    local = utc.astimezone(to_zone)
    local_time = datetime.strftime(local, "%Y-%m-%d %H:%M:%S")
    return local_time


def data_to_dict(model, data):
    dict_ = dict()
    all = {c.name: getattr(data, c.name, None) for c in model.__table__.columns}
    for k, v in all.items():
        if isinstance(v, datetime):
            dict_[k] = transfer_to_local_time(v)
        else:
            dict_[k] = v
    return dict_


#########################
def task_update_state_by_uuid(uuid, state):
    session = get_session()
    with session.begin():
        query = session.query(models.Task)
        task = query.filter_by(uuid=uuid).first()
        task.state = state
    return task


def task_update_percent_by_uuid(uuid, percent=0):
    session = get_session()
    with session.begin():
        query = session.query(models.Task)
        task = query.filter_by(uuid=uuid).first()
        task.percent = percent
    return task


def license_update_by_uuid(uuid, data):
    session = get_session()
    with session.begin():
        query = session.query(models.License)
        license = query.filter_by(uuid=uuid).first()
        license.license = data
    return license