from flask import flash, redirect, url_for, session, request, abort
from flask_login import current_user
from datetime import datetime
from functools import wraps

from .config import CAPTCHA_CLEARANCE_HOURS
from .cloudflare_util import is_valid_captcha
from .qol_util import is_within_threshold_minutes


def admin_required(func):
    """This decorator is used to check if the user is an admin."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if the user is an admin based on the role
        if current_user.is_authenticated and current_user.role == 'admin':
            return func(*args, **kwargs)
        
        # Return not found page
        return abort(404)

    return decorated_function


def profile_owner_required(func):
    """This decorator is used to check if the user is the profile owner."""
    @wraps(func)
    def decorated_function(username, *args, **kwargs):
        if current_user.is_authenticated and (username == current_user.username):
            return func(username, *args, **kwargs)
        
        flash('Only the profile owner can edit their profile.', 'error')
        return redirect(url_for('views.user_redirect'))

    return decorated_function


def unauthenticated_only(func):
    """This decorator is used to check if the user is unauthenticated."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if the user is an authenticated
        if not current_user.is_authenticated:
            return func(*args, **kwargs)
        
        flash('You are already authenticated!', 'error')
        return redirect(url_for('views.home'))

    return decorated_function


def in_maintenance(func):
    """This decorator is used when the endpoint is in maintenance."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # If the user is admin, maintenance is bypassed
        if current_user.is_authenticated and current_user.role == 'admin':
            return func(*args, **kwargs)
        
        return redirect(url_for('views.be_right_back'))

    return decorated_function


def captcha_required(func):
    """This decorator is used to check if the user needs to resolve a proof of life first."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        clearance = session.get('clearance', '')
        if clearance:
            now = datetime.now()
            
            time_difference = now - datetime.fromisoformat(clearance)
            if time_difference < timedelta(hours=CAPTCHA_CLEARANCE_HOURS):
                return func(*args, **kwargs)
        
        session['clearance_from'] = request.url
        return redirect(url_for('views.captcha'))

    return decorated_function


def verify_captcha(func):
    """This decorator is used to check if a captcha token is valid"""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('cf-turnstile-response', '')
            if not is_valid_captcha(token):
                flash('Invalid captcha. Are you a robot?', 'error')
                return redirect(request.url)

        # If captcha is valid, return the function as usual
        return func(*args, **kwargs)

    return decorated_function


def sensitive_area(func):
    """This decorator is used to check if the user needs to resolve a proof of life first."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        sensitive_clearance = session.get('sensitive_clearance', '')
        if sensitive_clearance:
            timestamp = datetime.fromisoformat(sensitive_clearance)
            if qol_util.is_within_threshold_minutes(timestamp, CAPTCHA_CLEARANCE_HOURS, is_hours=True):
                return func(*args, **kwargs)
        
        if 
        return redirect(url_for('views.sensitive'))

    return decorated_function
