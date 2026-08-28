import os, sqlite3

def report():
    db = os.getenv('IEA_DB_PATH', 'data/iea.sqlite3')
    if not os.path.exists(db):
        return 'No database yet. Run: python -m iea.cli pull'
    con = sqlite3.connect(db)
    rows = con.execute(
        '''SELECT provider,series_id,date,value,quality,status
           FROM observations ORDER BY date DESC LIMIT 50'''
    ).fetchall()
    lines = ['# IEA Data Health Report', '']
    for r in rows:
        lines.append(f'- {r[0]}:{r[1]} | {r[2]} | value={r[3]} | quality={r[4]} | {r[5]}')
    return '\n'.join(lines)
