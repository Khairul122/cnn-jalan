import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    from app.controllers.arsitektur_controller import tandai_training_terputus
    try:
        with app.app_context():
            n = tandai_training_terputus()
        if n:
            print(f'[startup] {n} training yang terputus oleh restart ditandai "gagal".')
    except Exception as e:   # DB belum siap: jangan hentikan server
        print(f'[startup] lewati pemulihan status training: {e}')

    debug = os.environ.get('FLASK_DEBUG') == '1'
    app.run(debug=debug, use_reloader=debug, reloader_type='stat', threaded=True)
