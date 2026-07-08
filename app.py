from flask import Flask, jsonify, render_template
from flask_login import LoginManager

from config import Config
from models import db


login_manager = LoginManager()
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return None


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    @app.get("/health")
    def health():
        return jsonify({"app": "myownX", "status": "ok"})

    def placeholder(page_title):
        return render_template("placeholder.html", page_title=page_title)

    @app.get("/")
    def index():
        return placeholder("首页")

    @app.get("/feed")
    def feed():
        return placeholder("信息流")

    @app.get("/discover")
    def discover():
        return placeholder("发现")

    @app.get("/messages")
    def messages():
        return placeholder("私信")

    @app.get("/notifications")
    def notifications():
        return placeholder("通知")

    @app.get("/profile")
    def profile():
        return placeholder("个人主页")

    @app.get("/settings")
    def settings():
        return placeholder("设置")

    @app.get("/login")
    def login():
        return placeholder("登录")

    @app.get("/register")
    def register():
        return placeholder("注册")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
