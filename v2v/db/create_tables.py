from v2v.db import models
from v2v.db.models import BASE
from sqlalchemy import create_engine


database_url = 'mysql+pymysql://root:@127.0.0.1/v2v'
engine_args = {
        "echo": True
    }
engine = create_engine(database_url, **engine_args)


def create_all_tables():
    """
    :return:
    """
    BASE.metadata.create_all(engine)


if __name__ == '__main__':
    create_all_tables()
    # from v2v.db.models import License
    # License.__table__.create(engine)
