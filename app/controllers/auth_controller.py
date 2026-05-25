from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.pengguna import Pengguna

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')



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
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))

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
        role     = request.form.get('role', 'viewer')

        if Pengguna.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.', 'warning')
            return render_template('auth/register.html')

        pengguna = Pengguna(nama=nama, email=email, role=role)
        pengguna.set_password(password)
        db.session.add(pengguna)
        db.session.commit()
        flash('Akun berhasil dibuat, silakan login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))
