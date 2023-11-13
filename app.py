from flask_login import LoginManager
from flask_gzip import Gzip
from flask import Flask
from os import urandom

from website_scripts import config
from auth import auth_views, User
from views import views

app = Flask(__name__)
gzip = Gzip(app)

app.secret_key = config.APP_SECRET_KEY
app.config['SESSION_COOKIE_DOMAIN'] = 'infomundi.net'
app.config['SESSION_COOKIE_SECURE'] = True

app.register_blueprint(views, url_prefix='/')
app.register_blueprint(auth_views, url_prefix='/auth')

login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user = User()
    user.id = user_id
    return user

if __name__ == '__main__':
    app.run(debug=True)
