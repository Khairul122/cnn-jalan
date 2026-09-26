"""End-to-end smoke augmentasi: POST run → poll progres → halaman + flash muncul."""
import json
import time

from app import create_app, db
from app.models.augmentasi_config import AugmentasiConfig
from app.models.pengguna import Pengguna

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    uid = Pengguna.query.first().id
    cfg = AugmentasiConfig(nama_config='SMOKE aug', n_salinan=1, seed=42, pengguna_id=uid,
                           parameter=json.dumps({}))
    db.session.add(cfg)
    db.session.commit()
    cid = cfg.id
print('config uji', cid)

c = app.test_client()
with c.session_transaction() as s:
    s['_user_id'] = str(uid)
    s['_fresh'] = True

print('POST run ->', c.post(f'/augmentasi/run/{cid}').status_code)
d = {}
for i in range(300):
    time.sleep(2)
    d = c.get(f'/augmentasi/progress/{cid}').get_json()
    if i % 10 == 0:
        print('  poll', i, json.dumps(d)[:130])
    if d.get('status') not in (None, 'running', 'idle'):
        break
print('AKHIR ->', json.dumps(d))
assert d.get('status') == 'selesai', d

r = c.get(d['reload'])
ok = 'Augmentasi selesai' in r.data.decode('utf8', 'ignore')
print('GET', d['reload'], '->', r.status_code, '| flash:', ok)
assert ok
print('OK: augmentasi progres + flash berfungsi')
