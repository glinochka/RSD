from ..alembic.models import Base

def convert_to_dict(obj: Base) -> dict:
    res = {}
    for key, value in obj.__dict__.items():
        if not key.startswith('_'): res[key] = value
    return res