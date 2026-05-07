from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, request, session, url_for

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


@bp.get('/learn/<session_id>')
@require_auth
def learn(session_id: str):
    from backend.api.sessions.service import get_session, get_tree
    session_obj = get_session(g.user_id, session_id)
    if not session_obj:
        return redirect(url_for('pages.index'))
    tree = get_tree(g.user_id, session_id)
    return render_template(
        'learn/session.html',
        session=session_obj,
        tree=tree,
        user_id=g.user_id,
    )


@bp.get('/quiz/<attempt_id>')
@require_auth
def quiz(attempt_id: str):
    from backend.core.db import query_one as _qone
    from backend.api.quiz.service import get_attempt
    from backend.api.sessions.service import get_session
    attempt = get_attempt(g.user_id, attempt_id)
    session_obj = get_session(g.user_id, attempt['session_id']) or {}
    quiz_row = _qone(
        "SELECT id FROM chat_sessions WHERE linked_attempt_id = %s AND user_id = %s",
        (attempt_id, g.user_id),
    )
    quiz_session_id = str(quiz_row["id"]) if quiz_row else ""
    return render_template(
        'quiz/attempt.html',
        attempt=attempt,
        session_title=session_obj.get('title') or 'Knowledge Check',
        quiz_session_id=quiz_session_id,
    )
