import json
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import Comment, Follow, Like, Notification, Post, User, db


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"

DEFAULT_AVATAR_URL = "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&h=100&fit=crop"
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_POST_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_POST_IMAGES = 4
MAX_COMMENT_LENGTH = 280


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def file_extension(filename):
    safe_filename = secure_filename(filename)
    return safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""


def parse_post_media_paths(media_path):
    if not media_path:
        return []

    try:
        parsed_paths = json.loads(media_path)
    except (TypeError, json.JSONDecodeError):
        return [media_path]

    if isinstance(parsed_paths, list):
        return [path for path in parsed_paths if isinstance(path, str) and path]

    if isinstance(parsed_paths, str) and parsed_paths:
        return [parsed_paths]

    return []


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    avatar_upload_dir = Path(app.static_folder) / "uploads" / "avatars"
    post_upload_dir = Path(app.static_folder) / "uploads" / "posts"
    avatar_upload_dir.mkdir(parents=True, exist_ok=True)
    post_upload_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        db.create_all()

    def follower_count(user):
        if not user:
            return 0
        return Follow.query.filter_by(following_id=user.id).count()

    def following_count(user):
        if not user:
            return 0
        return Follow.query.filter_by(follower_id=user.id).count()

    def is_following(user):
        if not user or not current_user or not current_user.is_authenticated:
            return False
        return Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first() is not None

    def recommended_users(limit=3):
        query = User.query.order_by(User.created_at.desc(), User.id.desc())

        if current_user and current_user.is_authenticated:
            followed_ids = db.session.query(Follow.following_id).filter_by(follower_id=current_user.id)
            query = query.filter(User.id != current_user.id).filter(~User.id.in_(followed_ids))

        return query.limit(limit).all()

    def like_count(post):
        if not post:
            return 0
        return Like.query.filter_by(post_id=post.id).count()

    def comment_count(post):
        if not post:
            return 0
        return Comment.query.filter_by(post_id=post.id).count()

    def has_liked(post):
        if not post or not current_user or not current_user.is_authenticated:
            return False
        return Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None

    def post_comments(post):
        if not post:
            return []
        return Comment.query.filter_by(post_id=post.id).order_by(Comment.created_at.asc()).all()

    def create_notification(recipient_id, notification_type, post_id=None):
        if not current_user or not current_user.is_authenticated or recipient_id == current_user.id:
            return

        notification = Notification(
            recipient_id=recipient_id,
            actor_id=current_user.id,
            post_id=post_id,
            notification_type=notification_type,
        )
        db.session.add(notification)

    def redirect_back(default_endpoint="feed", **values):
        target = request.referrer
        if target:
            return redirect(target)
        return redirect(url_for(default_endpoint, **values))

    @app.context_processor
    def utility_processor():
        def user_avatar_url(user):
            if user and getattr(user, "profile_picture_path", None):
                path = user.profile_picture_path
                if path.startswith(("http://", "https://", "/")):
                    return path
                return url_for("static", filename=path)
            return DEFAULT_AVATAR_URL

        def post_media_url(post):
            media_paths = parse_post_media_paths(getattr(post, "media_path", None))
            if media_paths:
                path = media_paths[0]
                if path.startswith(("http://", "https://", "/")):
                    return path
                return url_for("static", filename=path)
            return None

        def post_media_urls(post):
            urls = []
            for path in parse_post_media_paths(getattr(post, "media_path", None)):
                if path.startswith(("http://", "https://", "/")):
                    urls.append(path)
                else:
                    urls.append(url_for("static", filename=path))
            return urls

        return {
            "user_avatar_url": user_avatar_url,
            "post_media_url": post_media_url,
            "post_media_urls": post_media_urls,
            "follower_count": follower_count,
            "following_count": following_count,
            "is_following": is_following,
            "recommended_users": recommended_users,
            "like_count": like_count,
            "comment_count": comment_count,
            "has_liked": has_liked,
            "post_comments": post_comments,
        }

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
        image_files = [
            image_file
            for image_file in request.files.getlist("images") + request.files.getlist("image")
            if image_file and image_file.filename
        ]

        if not content and not image_files:
            flash("Post content or images are required.", "error")
            return redirect(url_for("feed"))

        if len(content) > 280:
            flash("Post content must be 280 characters or fewer.", "error")
            return redirect(url_for("feed"))

        if len(image_files) > MAX_POST_IMAGES:
            flash("You can upload up to 4 images per post.", "error")
            return redirect(url_for("feed"))

        media_path = None
        media_type = "text"

        if image_files:
            saved_paths = []

            for image_file in image_files:
                extension = file_extension(image_file.filename)
                if extension not in ALLOWED_POST_IMAGE_EXTENSIONS:
                    flash("Post images must be png, jpg, jpeg, gif, or webp files.", "error")
                    return redirect(url_for("feed"))

            for image_file in image_files:
                extension = file_extension(image_file.filename)
                filename = f"post_{current_user.id}_{uuid4().hex}.{extension}"
                image_file.save(post_upload_dir / filename)
                saved_paths.append(f"uploads/posts/{filename}")

            if len(saved_paths) == 1:
                media_path = saved_paths[0]
            else:
                media_path = json.dumps(saved_paths)

            media_type = "image"

        post = Post(
            user_id=current_user.id,
            content=content,
            media_path=media_path,
            media_type=media_type,
        )
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

    @app.post("/posts/<int:post_id>/like")
    @login_required
    def toggle_like(post_id):
        post = db.session.get(Post, post_id)

        if not post:
            flash("Post not found.", "error")
            return redirect_back("feed")

        existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            flash("Post unliked.", "success")
            return redirect_back("feed")

        like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(like)
        create_notification(post.user_id, "like", post_id=post.id)
        db.session.commit()
        flash("Post liked.", "success")
        return redirect_back("feed")

    @app.post("/posts/<int:post_id>/comment")
    @login_required
    def create_comment(post_id):
        post = db.session.get(Post, post_id)

        if not post:
            flash("Post not found.", "error")
            return redirect_back("feed")

        content = request.form.get("content", "").strip()

        if not content:
            flash("Comment content is required.", "error")
            return redirect_back("feed")

        if len(content) > MAX_COMMENT_LENGTH:
            flash("Comment content must be 280 characters or fewer.", "error")
            return redirect_back("feed")

        comment = Comment(user_id=current_user.id, post_id=post.id, content=content)
        db.session.add(comment)
        create_notification(post.user_id, "comment", post_id=post.id)
        db.session.commit()
        flash("Comment added successfully.", "success")
        return redirect_back("feed")

    @app.get("/discover")
    def discover():
        return placeholder("发现", users=recommended_users(limit=10))

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
        return placeholder("个人主页", user=current_user, posts=user_posts)

    @app.get("/users/<int:user_id>")
    @login_required
    def user_profile(user_id):
        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("discover"))

        if user.id == current_user.id:
            return redirect(url_for("profile"))

        user_posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
        return render_template("profile.html", page_title=user.display_name, user=user, posts=user_posts)

    @app.post("/users/<int:user_id>/follow")
    @login_required
    def follow_user(user_id):
        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.", "error")
            return redirect_back("discover")

        if user.id == current_user.id:
            flash("You cannot follow yourself.", "error")
            return redirect(url_for("profile"))

        existing_follow = Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first()
        if existing_follow:
            flash("You are already following this user.", "info")
            return redirect_back("user_profile", user_id=user.id)

        follow = Follow(follower_id=current_user.id, following_id=user.id)
        db.session.add(follow)
        db.session.commit()
        flash(f"You are now following {user.display_name or user.username}.", "success")
        return redirect_back("user_profile", user_id=user.id)

    @app.post("/users/<int:user_id>/unfollow")
    @login_required
    def unfollow_user(user_id):
        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.", "error")
            return redirect_back("discover")

        follow = Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first()
        if not follow:
            flash("You are not following this user.", "info")
            return redirect_back("user_profile", user_id=user.id)

        db.session.delete(follow)
        db.session.commit()
        flash(f"You unfollowed {user.display_name or user.username}.", "success")
        return redirect_back("user_profile", user_id=user.id)

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
                extension = file_extension(original_filename)

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
