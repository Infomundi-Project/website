from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_gzip import Gzip
from os import urandom

from website_scripts.config import APP_SECRET_KEY
from auth import auth_views, load_users
from views import views
from api import api


app = Flask(__name__)
gzip = Gzip(app)

app.secret_key = APP_SECRET_KEY

app.config['SESSION_COOKIE_NAME'] = 'infomundi-session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

app.register_blueprint(views, url_prefix='/')
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(auth_views, url_prefix='/auth')

login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    """User loader for flask login"""
    
    users = load_users()
    return users.get(user_id)


@app.errorhandler(404)
@app.errorhandler(500)
def error_handler(error):
    error_code = getattr(error, 'code', 500)

    error_message = f"We apologize, but {'the page you are looking for might have been removed, had its name changed or is temporarily unavailable.' if error_code == 404 else 'the server encountered an error and could not finish your request. Our team will work to address this issue as soon as possible. Meanwhile, feel free to send an email to <contact@infomundi.net> telling details about the error.'}"
    
    return render_template('error.html', error_code=error_code, error_message=error_message, page='Error'), error_code

if __name__ == '__main__':
    app.run(debug=True)
