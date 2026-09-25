"""Build a test app that is genuinely bound to a throwaway SQLite file.

`Config.SQLALCHEMY_DATABASE_URI` is a class attribute evaluated when `config.py`
is first imported, so assigning `os.environ['DATABASE_URL']` after that import
has no effect. `create_app()` reads the class attribute via
`app.config.from_object(Config)`, so a test that only sets the environment
variable silently keeps whatever database the shell points at — which means the
test writes to the real database and its `tearDown` deletes an unused temp file.

Patching the attribute before `create_app()` is the only override that takes
effect. Always pair it with `release_isolated_app` so the real value comes back.
"""
import os
import tempfile

from config import Config

_saved = {}


def make_isolated_app(secret_key='isolated-test-secret'):
    handle = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
    handle.close()
    _saved[handle.name] = (
        Config.SQLALCHEMY_DATABASE_URI,
        Config.SECRET_KEY,
    )
    Config.SQLALCHEMY_DATABASE_URI = f'sqlite:///{handle.name}'
    Config.SECRET_KEY = secret_key

    from app import create_app
    return create_app(), handle.name


def release_isolated_app(app, path):
    from app import db
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    uri, key = _saved.pop(path, (None, None))
    if uri is not None:
        Config.SQLALCHEMY_DATABASE_URI = uri
        Config.SECRET_KEY = key
    try:
        os.unlink(path)
    except OSError:
        pass
