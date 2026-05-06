from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, session, url_for, request

from backend.core.auth import require_auth

bp = Blueprint('pages', __name__)


@bp.get('/')
def root():
    if session.get('user_id'):
        return redirect(url_for('pages.index'))
    return redirect(url_for('pages.login'))


@bp.get('/login')
def login():
    if session.get('user_id'):
        return redirect(url_for('pages.index'))
    return render_template('auth/login.html')


@bp.get('/register')
def register():
    if session.get('user_id'):
        return redirect(url_for('pages.index'))
    return render_template('auth/register.html')


@bp.get('/app')
@require_auth
def index():
    return render_template('app/index.html', user_id=g.user_id)
