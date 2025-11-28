from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login = LoginManager()
login.login_view = 'auth.login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login.init_app(app)

    from .routes import auth, main, portfolio, rotation
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(portfolio.bp)
    app.register_blueprint(rotation.bp)

    return app

from . import models

@login.user_loader
def load_user(id):
    return models.User.query.get(int(id))
