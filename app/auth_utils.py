from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def require_admin():
    """Untuk route yang melayani GET (lihat) dan POST (ubah) sekaligus: panggil di jalur POST."""
    if not current_user.is_admin():
        abort(403)


def admin_required(view):
    """Login wajib + role admin. Viewer hanya boleh membaca data."""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        require_admin()
        return view(*args, **kwargs)
    return wrapper
