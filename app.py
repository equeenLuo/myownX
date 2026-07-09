from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import Post, User, db


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"

DEFAULT_AVATAR_URL = "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&h=100&fit=crop"
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


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
    avatar_upload_dir = Path(app.static_folder) / "uploads" / "avatars"
    avatar_upload_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        db.create_all()

    @app.context_processor
    def utility_processor():
        def user_avatar_url(user):
            if user and getattr(user, "profile_picture_path", None):
                path = user.profile_picture_path
                if path.startswith(("http://", "https://", "/")):
                    return path
                return url_for("static", filename=path)
            return DEFAULT_AVATAR_URL

        return {"user_avatar_url": user_avatar_url}

    @app.get("/health")
    def health():
        return jsonify({"app": "myownX", "status": "ok"})

    def latest_posts():
        return Post.query.order_by(Post.created_at.desc()).all()

    def placeholder(page_title, **context):
        return render_template("placeholder.html", page_title=page_title, **context)

    @app.get("/")
    def index():
        return placeholder("首页", posts=latest_posts())

    @app.get("/feed")
    @login_required
    def feed():
        return placeholder("信息流", posts=latest_posts())

    @app.post("/posts/create")
    @login_required
    def create_post():
        content = request.form.get("content", "").strip()

        if not content:
            flash("Post content is required.", "error")
            return redirect(url_for("feed"))

        if len(content) > 280:
            flash("Post content must be 280 characters or fewer.", "error")
            return redirect(url_for("feed"))

        post = Post(user_id=current_user.id, content=content, media_type="text")
        db.session.add(post)
        db.session.commit()
        flash("Post created successfully.", "success")
        return redirect(url_for("feed"))

    @app.post("/posts/<int:post_id>/delete")
    @login_required
    def delete_post(post_id):
        post = db.session.get(Post, post_id)

        if not post:
            flash("Post not found.", "error")
            return redirect(url_for("feed"))

        if post.user_id != current_user.id:
            flash("You can only delete your own posts.", "error")
            return redirect(url_for("feed"))

        db.session.delete(post)
        db.session.commit()
        flash("Post deleted successfully.", "success")
        return redirect(url_for("feed"))

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
    @login_required
    def profile():
        user_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).all()
        return placeholder("个人主页", posts=user_posts)

    @app.route("/profile/edit", methods=["GET", "POST"])
    @login_required
    def profile_edit():
        if request.method == "POST":
            display_name = request.form.get("display_name", "").strip()
            bio = request.form.get("bio", "").strip()

            if not display_name:
                flash("Display name is required.", "error")
                return render_template("profile_edit.html", page_title="Edit Profile")

            if len(display_name) > 50:
                flash("Display name must be 50 characters or fewer.", "error")
                return render_template("profile_edit.html", page_title="Edit Profile")

            if len(bio) > 255:
                flash("Bio must be 255 characters or fewer.", "error")
                return render_template("profile_edit.html", page_title="Edit Profile")

            avatar_file = request.files.get("profile_picture")
            if avatar_file and avatar_file.filename:
                original_filename = secure_filename(avatar_file.filename)
                extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""

                if extension not in ALLOWED_AVATAR_EXTENSIONS:
                    flash("Profile picture must be a png, jpg, jpeg, gif, or webp file.", "error")
                    return render_template("profile_edit.html", page_title="Edit Profile")

                filename = f"user_{current_user.id}_{uuid4().hex}.{extension}"
                avatar_file.save(avatar_upload_dir / filename)
                current_user.profile_picture_path = f"uploads/avatars/{filename}"

            current_user.display_name = display_name
            current_user.bio = bio or None
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("profile"))

        return render_template("profile_edit.html", page_title="Edit Profile")

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
