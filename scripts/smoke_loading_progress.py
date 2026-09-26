"""End-to-end smoke: POST run → poll progres → halaman hasil + flash muncul.

Dijalankan manual, bukan bagian suite unittest biasa karena menyentuh MySQL dan
menulis file di app/static/uploads/preprocessed/.
"""
import json
import time

from app import create_app
from app.models.hasil_preprocessing import HasilPreprocessing
from app.models.pengguna import Pengguna
from app.models.preprocessing_config import PreprocessingConfig

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    uid = Pengguna.query.first().id
    kecil = PreprocessingConfig(nama_config='SMOKE e2e', target_width=64, target_height=64,
                               crop_width=64, crop_height=64, denoise_method='gaussian',
                               denoise_ksize=3, pengguna_id=uid)
    from app import db
    db.session.add(kecil)
    db.session.commit()
    cid = kecil.id
print('config uji', cid)

c = app.test_client()
with c.session_transaction() as s:
    s['_user_id'] = str(uid)
    s['_fresh'] = True

print('POST run ->', c.post(f'/preprocessing/run/{cid}').status_code)
d = {'status': 'running'}
for i in range(200):
    time.sleep(2)
    d = c.get(f'/preprocessing/progress/{cid}').get_json()
    if d.get('status') != 'running':
        print(f'SELESAI setelah {(i + 1) * 2}s ->', json.dumps(d))
        break
assert d.get('status') == 'selesai', f'proses tidak selesai: {d}'
assert d.get('reload', '').endswith('proses=selesai'), d

with app.app_context():
    total = HasilPreprocessing.query.count()
    sukses = HasilPreprocessing.query.filter_by(status='selesai').count()
    print('hasil', sukses, '/', total)

r = c.get(d['reload'])
print('GET', d['reload'], '->', r.status_code)
assert 'Preprocessing selesai' in r.data.decode('utf8', 'ignore'), 'flash tidak muncul'
print('OK: progres + redirect + flash berfungsi')
