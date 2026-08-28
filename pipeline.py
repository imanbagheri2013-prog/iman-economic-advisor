import os, yaml
from .storage import Store
from .providers.fred import FRED
from .providers.bls import BLS

def load_config(path='config/series.yaml'):
    with open(path,encoding='utf-8') as f: return yaml.safe_load(f)

def pull():
    c=load_config()
    s=Store(os.getenv('IEA_DB_PATH','data/iea.sqlite3'))
    for sid in c.get('fred',{}):
        for o in FRED().observations(sid,50): s.upsert(o)
    for sid in c.get('bls',{}):
        for o in BLS().observations(sid,2020,2026): s.upsert(o)
    return s
