from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache

db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()