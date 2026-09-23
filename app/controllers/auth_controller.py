from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.pengguna import Pengguna

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

MIN_PASSWORD = 8


def _safe_next(target):
    """Terima hanya path internal ('/x'); tolak URL absolut, '//host', dan backslash."""
    if not target or not target.startswith('/') or target.startswith('//') or '\\' in target:
        return None
    parts = urlparse(target)
    return target if not parts.scheme and not parts.netloc else None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        pengguna = Pengguna.query.filter_by(email=email).first()

        if pengguna and pengguna.check_password(password):
            login_user(pengguna)
            flash('Login berhasil.', 'success')
            return redirect(_safe_next(request.args.get('next')) or url_for('dashboard.index'))

        flash('Email atau password salah.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        nama     = request.form.get('nama', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not nama or '@' not in email:
            flash('Nama dan email yang valid wajib diisi.', 'warning')
            return render_template('auth/register.html')
        if len(password) < MIN_PASSWORD:
            flash(f'Password minimal {MIN_PASSWORD} karakter.', 'warning')
            return render_template('auth/register.html')
        if Pengguna.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.', 'warning')
            return render_template('auth/register.html')

        # Akun dari pendaftaran publik selalu viewer; admin dibuat lewat scripts/create_admin.py
        pengguna = Pengguna(nama=nama, email=email, role='viewer')
        pengguna.set_password(password)
        db.session.add(pengguna)
        db.session.commit()
        flash('Akun berhasil dibuat, silakan login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))
