import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import func, inspect, text
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import Comment, Conversation, ConversationMember, Follow, Like, Message, Notification, Post, User, UserSettings, db


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"

DEFAULT_AVATAR_URL = "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&h=100&fit=crop"
DEFAULT_BANNER_PATH = "images/default-banner.svg"
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_POST_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_POST_IMAGES = 4
MAX_COMMENT_LENGTH = 280
MAX_MESSAGE_LENGTH = 1000
MAX_SEARCH_QUERY_LENGTH = 100
MAX_SEARCH_RESULTS = 50


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


def ensure_schema_updates(app):
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    with db.engine.begin() as connection:
        if "users" in table_names:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "profile_banner_path" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN profile_banner_path VARCHAR(255)"))

        if "posts" in table_names:
            post_columns = {column["name"] for column in inspector.get_columns("posts")}
            if "repost_from_id" not in post_columns:
                connection.execute(text("ALTER TABLE posts ADD COLUMN repost_from_id INTEGER"))
            if "reply_to_post_id" not in post_columns:
                connection.execute(text("ALTER TABLE posts ADD COLUMN reply_to_post_id INTEGER"))
            if "legacy_comment_id" not in post_columns:
                connection.execute(text("ALTER TABLE posts ADD COLUMN legacy_comment_id INTEGER"))

        if "conversations" in table_names:
            conversation_columns = {column["name"] for column in inspector.get_columns("conversations")}
            if "title" not in conversation_columns:
                connection.execute(text("ALTER TABLE conversations ADD COLUMN title VARCHAR(80)"))

        if "notifications" in table_names:
            notification_columns = {column["name"] for column in inspector.get_columns("notifications")}
            if "conversation_id" not in notification_columns:
                connection.execute(text("ALTER TABLE notifications ADD COLUMN conversation_id INTEGER"))

    if "comments" in table_names:
        migrated_comment_ids = db.session.query(Post.legacy_comment_id).filter(Post.legacy_comment_id.is_not(None))
        legacy_comments = Comment.query.filter(~Comment.id.in_(migrated_comment_ids)).all()
        for comment in legacy_comments:
            db.session.add(
                Post(
                    user_id=comment.user_id,
                    content=comment.content,
                    media_type="text",
                    reply_to_post_id=comment.post_id,
                    legacy_comment_id=comment.id,
                    created_at=comment.created_at,
                )
            )
        if legacy_comments:
            db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    avatar_upload_dir = Path(app.static_folder) / "uploads" / "avatars"
    banner_upload_dir = Path(app.static_folder) / "uploads" / "banners"
    post_upload_dir = Path(app.static_folder) / "uploads" / "posts"
    avatar_upload_dir.mkdir(parents=True, exist_ok=True)
    banner_upload_dir.mkdir(parents=True, exist_ok=True)
    post_upload_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        db.create_all()
        ensure_schema_updates(app)

    def follower_count(user):
        if not user:
            return 0
        return Follow.query.filter_by(following_id=user.id).count()

    def following_count(user):
        if not user:
            return 0
        return Follow.query.filter_by(follower_id=user.id).count()

    def relative_time(value):
        if not value:
            return ""

        if value.tzinfo is not None:
            now = datetime.now(timezone.utc)
            timestamp = value.astimezone(timezone.utc)
        else:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            timestamp = value

        elapsed_seconds = max(0, int((now - timestamp).total_seconds()))
        if elapsed_seconds < 60:
            return f"{elapsed_seconds}s"
        if elapsed_seconds < 60 * 60:
            return f"{elapsed_seconds // 60}m"
        if elapsed_seconds < 24 * 60 * 60:
            return f"{elapsed_seconds // (60 * 60)}h"
        return f"{elapsed_seconds // (24 * 60 * 60)}d"

    def post_detail_time(value):
        if not value:
            return ""

        hour = value.strftime("%I").lstrip("0") or "0"
        return f"{hour}:{value.strftime('%M %p')} · {value.strftime('%b')} {value.day}, {value.year}"

    def is_following(user):
        if not user or not current_user or not current_user.is_authenticated:
            return False
        return Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first() is not None

    def user_settings(user, create=False):
        if not user:
            return None

        settings = UserSettings.query.filter_by(user_id=user.id).first()
        if settings:
            return settings

        settings = UserSettings(user_id=user.id, is_private=False, allow_dms=True)
        if create:
            db.session.add(settings)
            db.session.commit()
        return settings

    def can_view_user_posts(user):
        if not user:
            return False
        if current_user and current_user.is_authenticated and user.id == current_user.id:
            return True

        settings = user_settings(user)
        if not settings or not settings.is_private:
            return True

        return is_following(user)

    def can_view_post(post):
        if not post:
            return False
        if not can_view_user_posts(post.author):
            return False
        if post.repost_source and not can_view_user_posts(post.repost_source.author):
            return False
        return True

    def can_message_user(user):
        if not user or not current_user or not current_user.is_authenticated:
            return False
        if user.id == current_user.id:
            return False

        settings = user_settings(user)
        if not settings or settings.allow_dms:
            return True

        return Follow.query.filter_by(follower_id=user.id, following_id=current_user.id).first() is not None

    def recommended_users(limit=3):
        query = User.query.order_by(User.created_at.desc(), User.id.desc())

        if current_user and current_user.is_authenticated:
            followed_ids = db.session.query(Follow.following_id).filter_by(follower_id=current_user.id)
            query = query.filter(User.id != current_user.id).filter(~User.id.in_(followed_ids))

        return query.limit(limit).all()

    def hot_posts(limit=5):
        sorted_posts = (
            Post.query.outerjoin(Like, Like.post_id == Post.id)
            .filter(Post.repost_from_id.is_(None), Post.reply_to_post_id.is_(None))
            .group_by(Post.id)
            .order_by(func.count(Like.id).desc(), Post.created_at.desc(), Post.id.desc())
            .limit(limit * 4)
            .all()
        )
        return [post for post in sorted_posts if can_view_post(post)][:limit]

    def search_users(query):
        pattern = f"%{query}%"
        return (
            User.query.filter((User.username.ilike(pattern)) | (User.display_name.ilike(pattern)))
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(MAX_SEARCH_RESULTS)
            .all()
        )

    def search_posts(query):
        pattern = f"%{query}%"
        candidate_posts = (
            Post.query.filter(
                Post.reply_to_post_id.is_(None),
                Post.repost_from_id.is_(None),
                Post.content.ilike(pattern),
            )
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(MAX_SEARCH_RESULTS * 4)
            .all()
        )
        return [post for post in candidate_posts if can_view_post(post)][:MAX_SEARCH_RESULTS]

    def messageable_users(limit=10):
        query = User.query.order_by(User.created_at.desc(), User.id.desc())

        if current_user and current_user.is_authenticated:
            query = query.filter(User.id != current_user.id)

        candidate_users = query.limit(limit * 3).all()
        return [user for user in candidate_users if can_message_user(user)][:limit]

    def like_count(post):
        if not post:
            return 0
        return Like.query.filter_by(post_id=post.id).count()

    def comment_count(post):
        if not post:
            return 0
        return Post.query.filter_by(reply_to_post_id=post.id).count()

    def reply_count(post):
        return comment_count(post)

    def has_liked(post):
        if not post or not current_user or not current_user.is_authenticated:
            return False
        return Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None

    def post_comments(post):
        return post_replies(post)

    def post_replies(post):
        if not post:
            return []
        return Post.query.filter_by(reply_to_post_id=post.id).order_by(Post.created_at.asc(), Post.id.asc()).all()

    def post_ancestors(post):
        ancestors = []
        visited_post_ids = set()
        current_post = post.reply_to_post if post else None

        while current_post and current_post.id not in visited_post_ids:
            ancestors.append(current_post)
            visited_post_ids.add(current_post.id)
            current_post = current_post.reply_to_post

        return list(reversed(ancestors))

    def repost_count(post):
        if not post:
            return 0
        return Post.query.filter_by(repost_from_id=post.id).count()

    def has_reposted(post):
        if not post or not current_user or not current_user.is_authenticated:
            return False
        target_post = post.repost_source if post.repost_source else post
        return Post.query.filter_by(user_id=current_user.id, repost_from_id=target_post.id).first() is not None

    def create_notification(recipient_id, notification_type, post_id=None, conversation_id=None):
        if not current_user or not current_user.is_authenticated or recipient_id == current_user.id:
            return

        notification = Notification(
            recipient_id=recipient_id,
            actor_id=current_user.id,
            post_id=post_id,
            conversation_id=conversation_id,
            notification_type=notification_type,
        )
        db.session.add(notification)

    def redirect_back(default_endpoint="feed", **values):
        target = request.referrer
        if target:
            return redirect(target)
        return redirect(url_for(default_endpoint, **values))

    def wants_async_response():
        return request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def action_error(message, default_endpoint="feed", status_code=400, **values):
        if wants_async_response():
            return jsonify({"ok": False, "message": message}), status_code
        flash(message, "error")
        return redirect_back(default_endpoint, **values)

    def action_success(payload, default_endpoint="feed", **values):
        if wants_async_response():
            return jsonify({"ok": True, **payload})
        return redirect_back(default_endpoint, **values)

    def conversation_last_message(conversation):
        if not conversation:
            return None
        return (
            Message.query.filter_by(conversation_id=conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .first()
        )

    def conversation_messages(conversation):
        if not conversation:
            return []
        return (
            Message.query.filter_by(conversation_id=conversation.id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )

    def conversation_other_user(conversation):
        if not conversation or not current_user or not current_user.is_authenticated:
            return None

        for member in conversation.members:
            if member.user_id != current_user.id:
                return member.user
        return None

    def conversation_members(conversation):
        if not conversation:
            return []
        return [member.user for member in conversation.members if member.user]

    def conversation_title(conversation):
        if not conversation:
            return "Unknown conversation"
        if conversation.conversation_type == "group":
            if conversation.title:
                return conversation.title
            names = [
                member.user.display_name or member.user.username
                for member in conversation.members
                if member.user and member.user_id != current_user.id
            ]
            return ", ".join(names[:3]) or "Group chat"

        other_user = conversation_other_user(conversation)
        return other_user.display_name or other_user.username if other_user else "Unknown user"

    def conversation_has_unread_messages(conversation):
        if not conversation or not current_user or not current_user.is_authenticated:
            return False

        query = Notification.query.filter_by(
            recipient_id=current_user.id,
            is_read=False,
            notification_type="message",
        )
        if conversation.conversation_type == "group":
            return query.filter_by(conversation_id=conversation.id).first() is not None

        other_user = conversation_other_user(conversation)
        if not other_user:
            return False
        return query.filter(
            (Notification.conversation_id == conversation.id)
            | ((Notification.conversation_id.is_(None)) & (Notification.actor_id == other_user.id))
        ).first() is not None

    def user_conversations():
        if not current_user or not current_user.is_authenticated:
            return []

        conversations = (
            Conversation.query.join(ConversationMember)
            .filter(ConversationMember.user_id == current_user.id)
            .all()
        )
        return sorted(
            conversations,
            key=lambda conversation: (
                conversation_last_message(conversation).created_at
                if conversation_last_message(conversation)
                else conversation.created_at
            ),
            reverse=True,
        )

    def is_conversation_member(conversation):
        if not conversation or not current_user or not current_user.is_authenticated:
            return False
        return (
            ConversationMember.query.filter_by(
                conversation_id=conversation.id,
                user_id=current_user.id,
            ).first()
            is not None
        )

    def private_conversation_with(user_id):
        current_conversation_ids = db.session.query(ConversationMember.conversation_id).filter_by(
            user_id=current_user.id
        )
        return (
            Conversation.query.join(ConversationMember)
            .filter(Conversation.conversation_type == "private")
            .filter(Conversation.id.in_(current_conversation_ids))
            .filter(ConversationMember.user_id == user_id)
            .first()
        )

    def group_conversation_with(member_ids):
        expected_member_ids = {current_user.id, *member_ids}
        current_conversation_ids = db.session.query(ConversationMember.conversation_id).filter_by(
            user_id=current_user.id
        )
        group_conversations = (
            Conversation.query.filter(Conversation.conversation_type == "group")
            .filter(Conversation.id.in_(current_conversation_ids))
            .all()
        )
        for conversation in group_conversations:
            if {member.user_id for member in conversation.members} == expected_member_ids:
                return conversation
        return None

    @app.context_processor
    def utility_processor():
        def user_avatar_url(user):
            if user and getattr(user, "profile_picture_path", None):
                path = user.profile_picture_path
                if path.startswith(("http://", "https://", "/")):
                    return path
                return url_for("static", filename=path)
            return DEFAULT_AVATAR_URL

        def user_banner_url(user):
            if user and getattr(user, "profile_banner_path", None):
                path = user.profile_banner_path
                if path.startswith(("http://", "https://", "/")):
                    return path
                return url_for("static", filename=path)
            return url_for("static", filename=DEFAULT_BANNER_PATH)

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
            "user_banner_url": user_banner_url,
            "post_media_url": post_media_url,
            "post_media_urls": post_media_urls,
            "follower_count": follower_count,
            "following_count": following_count,
            "relative_time": relative_time,
            "post_detail_time": post_detail_time,
            "is_following": is_following,
            "user_settings": user_settings,
            "can_view_user_posts": can_view_user_posts,
            "can_view_post": can_view_post,
            "can_message_user": can_message_user,
            "recommended_users": recommended_users,
            "hot_posts": hot_posts,
            "messageable_users": messageable_users,
            "like_count": like_count,
            "comment_count": comment_count,
            "reply_count": reply_count,
            "has_liked": has_liked,
            "post_comments": post_comments,
            "post_replies": post_replies,
            "post_ancestors": post_ancestors,
            "repost_count": repost_count,
            "has_reposted": has_reposted,
            "conversation_last_message": conversation_last_message,
            "conversation_messages": conversation_messages,
            "conversation_other_user": conversation_other_user,
            "conversation_members": conversation_members,
            "conversation_title": conversation_title,
            "conversation_has_unread_messages": conversation_has_unread_messages,
        }

    @app.context_processor
    def inject_unread_count():
        if current_user.is_authenticated:
            count = (
                Notification.query.filter_by(recipient_id=current_user.id, is_read=False)
                .filter(Notification.notification_type != "message")
                .count()
            )
            return {"unread_notifications_count": count}
        return {"unread_notifications_count": 0}

    @app.context_processor
    def inject_unread_messages():
        if current_user.is_authenticated:
            count = Notification.query.filter_by(
                recipient_id=current_user.id,
                is_read=False,
                notification_type="message",
            ).count()
            return {"unread_messages_count": count}
        return {"unread_messages_count": 0}

    @app.context_processor
    def inject_unread_senders():
        if current_user.is_authenticated:
            unread_notifications = Notification.query.filter_by(
                recipient_id=current_user.id,
                is_read=False,
                notification_type="message",
            ).all()
            unread_sender_ids = {notification.actor_id for notification in unread_notifications}
            return {"unread_sender_ids": unread_sender_ids}
        return {"unread_sender_ids": set()}

    @app.get("/health")
    def health():
        return jsonify({"app": "myownX", "status": "ok"})

    def latest_posts():
        posts = Post.query.filter(Post.reply_to_post_id.is_(None)).order_by(Post.created_at.desc()).all()
        return [post for post in posts if can_view_post(post)]

    def placeholder(page_title, **context):
        return render_template("placeholder.html", page_title=page_title, **context)

    @app.get("/")
    def index():
        return placeholder("首页", posts=latest_posts())

    @app.get("/feed")
    @login_required
    def feed():
        return placeholder("信息流", posts=latest_posts())

    @app.get("/posts/<int:post_id>")
    def post_detail(post_id):
        post = db.session.get(Post, post_id)

        if not post or not can_view_post(post):
            abort(404)

        reply_depth = request.args.get("reply_depth", default=2, type=int)
        reply_depth = max(2, reply_depth)

        return render_template(
            "post_detail.html",
            page_title="Post",
            post=post,
            ancestors=post_ancestors(post),
            replies=post_replies(post),
            reply_depth=reply_depth,
        )

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
        return redirect(url_for("feed"))

    @app.post("/posts/<int:post_id>/delete")
    @login_required
    def delete_post(post_id):
        post = db.session.get(Post, post_id)

        if not post:
            return action_error("Post not found.", status_code=404)

        if post.user_id != current_user.id:
            return action_error("You can only delete your own posts.", status_code=403)

        db.session.delete(post)
        db.session.commit()
        return action_success({"action": "delete", "post_id": post_id})

    @app.post("/posts/<int:post_id>/like")
    @login_required
    def toggle_like(post_id):
        post = db.session.get(Post, post_id)

        if not post or not can_view_post(post):
            return action_error("Post not found.", status_code=404)

        existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
        if existing_like:
            db.session.delete(existing_like)
            Notification.query.filter_by(
                recipient_id=post.user_id,
                actor_id=current_user.id,
                post_id=post.id,
                notification_type="like",
            ).delete()
            db.session.commit()
            return action_success(
                {"action": "like", "post_id": post.id, "liked": False, "like_count": like_count(post)}
            )

        like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(like)
        create_notification(post.user_id, "like", post_id=post.id)
        db.session.commit()
        return action_success(
            {"action": "like", "post_id": post.id, "liked": True, "like_count": like_count(post)}
        )

    @app.post("/posts/<int:post_id>/comment")
    @login_required
    def create_comment(post_id):
        post = db.session.get(Post, post_id)

        if not post or not can_view_post(post):
            return action_error("Post not found.", status_code=404)

        content = request.form.get("content", "").strip()

        if not content:
            return action_error("Comment content is required.")

        if len(content) > MAX_COMMENT_LENGTH:
            return action_error("Comment content must be 280 characters or fewer.")

        reply = Post(
            user_id=current_user.id,
            content=content,
            media_type="text",
            reply_to_post_id=post.id,
        )
        db.session.add(reply)
        create_notification(post.user_id, "comment", post_id=post.id)
        db.session.commit()

        if wants_async_response():
            return jsonify(
                {
                    "ok": True,
                    "action": "reply",
                    "parent_post_id": post.id,
                    "reply_count": reply_count(post),
                    "reply_html": render_template("_async_reply.html", reply=reply),
                }
            )

        return_to_post_id = request.form.get("return_to_post_id", type=int)
        if return_to_post_id:
            return_to_post = db.session.get(Post, return_to_post_id)
            if return_to_post and can_view_post(return_to_post):
                return redirect(url_for("post_detail", post_id=return_to_post.id))

        return redirect_back("feed")

    @app.post("/posts/<int:post_id>/repost")
    @login_required
    def create_repost(post_id):
        post = db.session.get(Post, post_id)

        if not post or not can_view_post(post):
            return action_error("Post not found.", status_code=404)

        source_post = post.repost_source if post.repost_source else post
        existing_repost = Post.query.filter_by(user_id=current_user.id, repost_from_id=source_post.id).first()
        if existing_repost:
            db.session.delete(existing_repost)
            Notification.query.filter_by(
                recipient_id=source_post.user_id,
                actor_id=current_user.id,
                post_id=source_post.id,
                notification_type="repost",
            ).delete()
            db.session.commit()
            return action_success(
                {"action": "repost", "post_id": source_post.id, "reposted": False, "repost_count": repost_count(source_post)}
            )

        repost = Post(
            user_id=current_user.id,
            content="",
            media_type="text",
            repost_from_id=source_post.id,
        )
        db.session.add(repost)
        create_notification(source_post.user_id, "repost", post_id=source_post.id)
        db.session.commit()
        return action_success(
            {"action": "repost", "post_id": source_post.id, "reposted": True, "repost_count": repost_count(source_post)}
        )

    @app.get("/discover")
    def discover():
        return placeholder("发现", users=recommended_users(limit=10), hot_posts=hot_posts(limit=5))

    @app.get("/search")
    def search():
        search_query = request.args.get("q", "").strip()
        context = {
            "page_title": "Search",
            "search_query": search_query,
            "searched": bool(search_query),
            "users": [],
            "posts": [],
            "search_error": None,
        }

        if not search_query:
            return render_template("search.html", **context)

        if len(search_query) > MAX_SEARCH_QUERY_LENGTH:
            context["search_error"] = "Search query must be 100 characters or fewer."
            return render_template("search.html", **context)

        context["users"] = search_users(search_query)
        context["posts"] = search_posts(search_query)
        return render_template("search.html", **context)

    @app.get("/messages")
    @login_required
    def messages():
        return placeholder("私信", conversations=user_conversations(), users=messageable_users(limit=10))

    @app.post("/messages/start/<int:user_id>")
    @login_required
    def start_conversation(user_id):
        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.", "error")
            return redirect_back("messages")

        if user.id == current_user.id:
            flash("You cannot message yourself.", "error")
            return redirect_back("messages")

        if not can_message_user(user):
            flash("This user only accepts messages from people they follow.", "error")
            return redirect_back("messages")

        conversation = private_conversation_with(user.id)
        if not conversation:
            conversation = Conversation(conversation_type="private")
            db.session.add(conversation)
            db.session.flush()
            db.session.add_all(
                [
                    ConversationMember(conversation_id=conversation.id, user_id=current_user.id),
                    ConversationMember(conversation_id=conversation.id, user_id=user.id),
                ]
            )
            db.session.commit()

        return redirect(url_for("conversation", conversation_id=conversation.id))

    @app.post("/messages/group")
    @login_required
    def create_group_conversation():
        participant_ids = set()
        for raw_user_id in request.form.getlist("participant_ids"):
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                continue
            if user_id != current_user.id:
                participant_ids.add(user_id)

        if len(participant_ids) < 2:
            flash("Select at least two people to create a group chat.", "error")
            return redirect(url_for("messages"))

        participants = User.query.filter(User.id.in_(participant_ids)).all()
        if len(participants) != len(participant_ids):
            flash("One or more selected users could not be found.", "error")
            return redirect(url_for("messages"))

        for participant in participants:
            if not can_message_user(participant):
                display_name = participant.display_name or participant.username
                flash(f"{display_name} only accepts messages from people they follow.", "error")
                return redirect(url_for("messages"))

        title = request.form.get("title", "").strip()
        if len(title) > 80:
            flash("Group name must be 80 characters or fewer.", "error")
            return redirect(url_for("messages"))

        conversation = group_conversation_with(participant_ids)
        if not conversation:
            conversation = Conversation(conversation_type="group", title=title or None)
            db.session.add(conversation)
            db.session.flush()
            db.session.add_all(
                [
                    ConversationMember(conversation_id=conversation.id, user_id=current_user.id),
                    *[
                        ConversationMember(conversation_id=conversation.id, user_id=participant.id)
                        for participant in participants
                    ],
                ]
            )
            db.session.commit()

        return redirect(url_for("conversation", conversation_id=conversation.id))

    @app.route("/messages/<int:conversation_id>", methods=["GET", "POST"])
    @login_required
    def conversation(conversation_id):
        conversation = db.session.get(Conversation, conversation_id)

        if not conversation or not is_conversation_member(conversation):
            flash("Conversation not found.", "error")
            return redirect(url_for("messages"))

        if request.method == "POST":
            content = request.form.get("content", "").strip()

            if not content:
                flash("Message content is required.", "error")
                return redirect(url_for("conversation", conversation_id=conversation.id))

            if len(content) > MAX_MESSAGE_LENGTH:
                flash("Message content must be 1000 characters or fewer.", "error")
                return redirect(url_for("conversation", conversation_id=conversation.id))

            message = Message(conversation_id=conversation.id, sender_id=current_user.id, content=content)
            db.session.add(message)

            for member in conversation.members:
                if member.user_id != current_user.id:
                    create_notification(member.user_id, "message", conversation_id=conversation.id)

            db.session.commit()
            flash("Message sent.", "success")
            return redirect(url_for("conversation", conversation_id=conversation.id))

        unread_messages = Notification.query.filter_by(
            recipient_id=current_user.id,
            notification_type="message",
            is_read=False,
        )
        if conversation.conversation_type == "group":
            unread_messages.filter_by(conversation_id=conversation.id).update({"is_read": True})
            db.session.commit()
        else:
            other_member = (
                ConversationMember.query.filter(ConversationMember.conversation_id == conversation.id)
                .filter(ConversationMember.user_id != current_user.id)
                .first()
            )
            if other_member:
                unread_messages.filter(
                    (Notification.conversation_id == conversation.id)
                    | ((Notification.conversation_id.is_(None)) & (Notification.actor_id == other_member.user_id))
                ).update({"is_read": True})
                db.session.commit()

        return placeholder(
            "私信",
            conversations=user_conversations(),
            active_conversation=conversation,
            messages=conversation_messages(conversation),
            users=messageable_users(limit=10),
        )

    @app.get("/notifications")
    @login_required
    def notifications():
        user_notifications = (
            Notification.query.filter_by(recipient_id=current_user.id)
            .filter(Notification.notification_type != "message")
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .all()
        )
        unread_notification_ids = {notification.id for notification in user_notifications if not notification.is_read}
        (
            Notification.query.filter_by(recipient_id=current_user.id, is_read=False)
            .filter(Notification.notification_type != "message")
            .update(
                {"is_read": True},
                synchronize_session=False,
            )
        )
        db.session.commit()
        return placeholder("通知", notifications=user_notifications, unread_notification_ids=unread_notification_ids)

    @app.get("/profile")
    @login_required
    def profile():
        posts = (
            Post.query.filter_by(user_id=current_user.id)
            .filter(Post.reply_to_post_id.is_(None))
            .order_by(Post.created_at.desc())
            .all()
        )
        user_posts = [post for post in posts if can_view_post(post)]
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

        if can_view_user_posts(user):
            posts = (
                Post.query.filter_by(user_id=user.id)
                .filter(Post.reply_to_post_id.is_(None))
                .order_by(Post.created_at.desc())
                .all()
            )
            user_posts = [post for post in posts if can_view_post(post)]
        else:
            user_posts = []

        return render_template("profile.html", page_title=user.display_name, user=user, posts=user_posts)

    @app.get("/users/<int:user_id>/followers")
    @login_required
    def user_followers(user_id):
        user = db.session.get(User, user_id)
        if not user:
            flash("User not found.", "error")
            return redirect(url_for("discover"))

        follows = (
            Follow.query.filter_by(following_id=user.id)
            .order_by(Follow.created_at.desc(), Follow.id.desc())
            .all()
        )
        return render_template(
            "user_list.html",
            page_title=f"{user.display_name or user.username} Followers",
            profile_user=user,
            list_title="Followers",
            users=[follow.follower for follow in follows],
        )

    @app.get("/users/<int:user_id>/following")
    @login_required
    def user_following(user_id):
        user = db.session.get(User, user_id)
        if not user:
            flash("User not found.", "error")
            return redirect(url_for("discover"))

        follows = (
            Follow.query.filter_by(follower_id=user.id)
            .order_by(Follow.created_at.desc(), Follow.id.desc())
            .all()
        )
        return render_template(
            "user_list.html",
            page_title=f"{user.display_name or user.username} Following",
            profile_user=user,
            list_title="Following",
            users=[follow.following for follow in follows],
        )

    @app.post("/users/<int:user_id>/follow")
    @login_required
    def follow_user(user_id):
        user = db.session.get(User, user_id)

        if not user:
            return action_error("User not found.", "discover", status_code=404)

        if user.id == current_user.id:
            return action_error("You cannot follow yourself.", "profile")

        existing_follow = Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first()
        if existing_follow:
            return action_success(
                {"action": "follow", "user_id": user.id, "following": True, "follower_count": follower_count(user)},
                "user_profile",
                user_id=user.id,
            )

        follow = Follow(follower_id=current_user.id, following_id=user.id)
        db.session.add(follow)
        create_notification(user.id, "follow")
        db.session.commit()
        return action_success(
            {"action": "follow", "user_id": user.id, "following": True, "follower_count": follower_count(user)},
            "user_profile",
            user_id=user.id,
        )

    @app.post("/users/<int:user_id>/unfollow")
    @login_required
    def unfollow_user(user_id):
        user = db.session.get(User, user_id)

        if not user:
            return action_error("User not found.", "discover", status_code=404)

        follow = Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first()
        if not follow:
            return action_success(
                {"action": "follow", "user_id": user.id, "following": False, "follower_count": follower_count(user)},
                "user_profile",
                user_id=user.id,
            )

        db.session.delete(follow)
        Notification.query.filter_by(
            recipient_id=user.id,
            actor_id=current_user.id,
            notification_type="follow",
        ).delete()
        db.session.commit()
        return action_success(
            {"action": "follow", "user_id": user.id, "following": False, "follower_count": follower_count(user)},
            "user_profile",
            user_id=user.id,
        )

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
            banner_file = request.files.get("profile_banner")

            if banner_file and banner_file.filename:
                original_filename = secure_filename(banner_file.filename)
                extension = file_extension(original_filename)

                if extension not in ALLOWED_AVATAR_EXTENSIONS:
                    flash("Profile banner must be a png, jpg, jpeg, gif, or webp file.", "error")
                    return render_template("profile_edit.html", page_title="Edit Profile")

            if avatar_file and avatar_file.filename:
                original_filename = secure_filename(avatar_file.filename)
                extension = file_extension(original_filename)

                if extension not in ALLOWED_AVATAR_EXTENSIONS:
                    flash("Profile picture must be a png, jpg, jpeg, gif, or webp file.", "error")
                    return render_template("profile_edit.html", page_title="Edit Profile")

                filename = f"user_{current_user.id}_{uuid4().hex}.{extension}"
                avatar_file.save(avatar_upload_dir / filename)
                current_user.profile_picture_path = f"uploads/avatars/{filename}"

            if banner_file and banner_file.filename:
                extension = file_extension(banner_file.filename)
                filename = f"banner_{current_user.id}_{uuid4().hex}.{extension}"
                banner_file.save(banner_upload_dir / filename)
                current_user.profile_banner_path = f"uploads/banners/{filename}"

            current_user.display_name = display_name
            current_user.bio = bio or None
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("profile"))

        return render_template("profile_edit.html", page_title="Edit Profile")

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        settings = user_settings(current_user, create=True)

        if request.method == "POST":
            settings.is_private = request.form.get("is_private") == "on"
            settings.allow_dms = request.form.get("allow_dms") == "on"
            db.session.commit()
            flash("Privacy settings updated successfully.", "success")
            return redirect(url_for("settings"))

        return placeholder("设置", settings=settings)

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
