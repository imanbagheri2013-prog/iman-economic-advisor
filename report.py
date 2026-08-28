import os, sqlite3
def report():
    db=os.getenv('IEA_DB_PATH','data/iea.sqlite3')
    if not os.path.exists(db): return 'Database not initialized. Run: python -m iea.cli pull'
    c=sqlite3.connect(db)
    rows=c.execute('''SELECT provider,series_id,date,value,quality,status
                      FROM observations ORDER BY date DESC LIMIT 50''').fetchall()
    return '\n'.join(['# IEA Data Health']+
      [f'- {a}:{b} | {d} | value={v} | Q={q} | {st}' for a,b,d,v,q,st in rows])
