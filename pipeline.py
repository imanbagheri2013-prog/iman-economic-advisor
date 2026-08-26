import os, yaml
from .providers.fred import FRED
from .providers.bls import BLS
from .storage import Store

def load_config(path='config/series.yaml'):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)

def pull():
    cfg = load_config()
    store = Store(os.getenv('IEA_DB_PATH', 'data/iea.sqlite3'))
    for sid in cfg.get('fred', {}):
        for obs in FRED().observations(sid, limit=20):
            store.upsert(obs)
    for sid in cfg.get('bls', {}):
        for obs in BLS().observations(sid, 2020, 2026):
            store.upsert(obs)
    return store
