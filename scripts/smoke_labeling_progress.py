"""End-to-end smoke labeling: POST run → poll progres → halaman review muncul."""
import json
import time

from app import create_app, db
from app.models.labeling_config import LabelingConfig
from app.models.pengguna import Pengguna

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    uid = Pengguna.query.first().id
    cfg = LabelingConfig.query.first()
    cid = cfg.id
print('config uji', cid)

c = app.test_client()
with c.session_transaction() as s:
    s['_user_id'] = str(uid)
    s['_fresh'] = True

print('POST run ->', c.post(f'/label/config/{cid}/run').status_code)
d = {}
for i in range(400):
    time.sleep(2)
    d = c.get(f'/label/progress/{cid}').get_json()
    if i % 10 == 0:
        print('  poll', i, json.dumps(d)[:140])
    if d.get('status') not in (None, 'running', 'idle'):
        break
print('AKHIR ->', json.dumps(d))
assert d.get('status') == 'selesai', d

r = c.get(d['reload'])
ok = r.status_code == 200
print('GET', d['reload'], '->', r.status_code)
assert ok
print('OK: labeling progres + redirect berfungsi')
