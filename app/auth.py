from functools import wraps

from flask import redirect, request, session, url_for


def is_admin_authenticated() -> bool:
    return bool(session.get("admin_user_id"))


def login_admin(user: dict):
    session.clear()
    session["admin_user_id"] = str(user.get("_id") or user.get("id"))
    session["admin_username"] = user.get("username", "")
    session["admin_failed_attempts"] = 0
    session["admin_locked_until"] = 0


def logout_admin():
    session.clear()


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_authenticated():
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped
