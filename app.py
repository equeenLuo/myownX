from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import User, db


login_manager = LoginManager()
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db.create_all()

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

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("feed"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()

            if not user or not check_password_hash(user.password_hash, password):
                flash("Invalid username or password.", "error")
                return placeholder("登录")

            login_user(user)
            return redirect(url_for("feed"))

        return placeholder("登录")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("feed"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            display_name = request.form.get("display_name", "").strip()
            password = request.form.get("password", "")

            if not username or not display_name or not password:
                flash("Username, display name, and password are required.", "error")
                return placeholder("注册")

            if User.query.filter_by(username=username).first():
                flash("Username is already taken. Please choose another one.", "error")
                return placeholder("注册")

            user = User(
                username=username,
                display_name=display_name,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("feed"))

        return placeholder("注册")

    @app.post("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
