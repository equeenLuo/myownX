import argparse
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from app import app
from models import Comment, Conversation, ConversationMember, Follow, Like, Message, Notification, Post, User, UserSettings, db


DEMO_PASSWORD = "123456"
DEMO_USERNAMES = ("alex", "maya", "noah", "zoe")


def seed_demo_data(flask_app, reset=False):
    """Populate a predictable classroom demo dataset.

    The default mode does not overwrite existing data. Use reset=True only when
    a clean demonstration database is explicitly required.
    """
    with flask_app.app_context():
        if reset:
            db.drop_all()
            db.create_all()
        elif User.query.filter(User.username.in_(DEMO_USERNAMES)).first():
            raise ValueError("Demo users already exist. Run with --reset to rebuild the demo database.")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        password_hash = generate_password_hash(DEMO_PASSWORD)
        users = {
            "alex": User(
                username="alex01",
                display_name="alex",
                bio="this is alex and a demo user for myownX. you can follow, like, comment, and message.",
                password_hash=password_hash,
                created_at=now - timedelta(days=8),
            ),
            "maya": User(
                username="maya02",
                display_name="maya",
                bio="ok lollllllllllllll",
                password_hash=password_hash,
                created_at=now - timedelta(days=6),
            ),
            "noah": User(
                username="noah03",
                display_name="noah",
                bio="noah the ship",
                password_hash=password_hash,
                created_at=now - timedelta(days=4),
            ),
            "zoe": User(
                username="zoe04",
                display_name="zoe",
                bio="EQRQ duh",
                password_hash=password_hash,
                created_at=now - timedelta(days=2),
            ),
        }
        db.session.add_all(users.values())
        db.session.flush()

        db.session.add_all(
            [
                UserSettings(user_id=users["alex"].id, is_private=False, allow_dms=True),
                UserSettings(user_id=users["maya"].id, is_private=False, allow_dms=True),
                UserSettings(user_id=users["noah"].id, is_private=True, allow_dms=False),
                UserSettings(user_id=users["zoe"].id, is_private=False, allow_dms=True),
            ]
        )

        db.session.add_all(
            [
                Follow(follower_id=users["alex"].id, following_id=users["maya"].id),
                Follow(follower_id=users["alex"].id, following_id=users["noah"].id),
                Follow(follower_id=users["maya"].id, following_id=users["alex"].id),
                Follow(follower_id=users["maya"].id, following_id=users["zoe"].id),
                Follow(follower_id=users["noah"].id, following_id=users["alex"].id),
                Follow(follower_id=users["zoe"].id, following_id=users["alex"].id),
            ]
        )

        posts = {
            "alex": Post(
                user_id=users["alex"].id,
                content="wow testing demo funny huh",
                created_at=now - timedelta(hours=6),
            ),
            "maya": Post(
                user_id=users["maya"].id,
                content="dooooo dooooo doooo dooooo duh duh duh duh",
                created_at=now - timedelta(hours=4),
            ),
            "noah": Post(
                user_id=users["noah"].id,
                content="heyyyyy im posting from the demo account",
                created_at=now - timedelta(hours=2),
            ),
            "zoe": Post(
                user_id=users["zoe"].id,
                content="crz thursday v me 50?? thank you",
                created_at=now - timedelta(hours=1),
            ),
        }
        db.session.add_all(posts.values())
        db.session.flush()

        repost = Post(
            user_id=users["maya"].id,
            content="",
            media_type="text",
            repost_from_id=posts["alex"].id,
            created_at=now - timedelta(hours=3),
        )
        db.session.add(repost)

        db.session.add_all(
            [
                Like(user_id=users["maya"].id, post_id=posts["alex"].id),
                Like(user_id=users["zoe"].id, post_id=posts["alex"].id),
                Like(user_id=users["alex"].id, post_id=posts["maya"].id),
                Comment(
                    user_id=users["maya"].id,
                    post_id=posts["alex"].id,
                    content="The notification flow is ready for the demo.",
                    created_at=now - timedelta(hours=5),
                ),
                Comment(
                    user_id=users["alex"].id,
                    post_id=posts["maya"].id,
                    content="The mobile layout is looking good.",
                    created_at=now - timedelta(hours=3, minutes=30),
                ),
            ]
        )

        conversation = Conversation(conversation_type="private", created_at=now - timedelta(hours=2))
        db.session.add(conversation)
        db.session.flush()
        db.session.add_all(
            [
                ConversationMember(conversation_id=conversation.id, user_id=users["alex"].id),
                ConversationMember(conversation_id=conversation.id, user_id=users["maya"].id),
                Message(
                    conversation_id=conversation.id,
                    sender_id=users["alex"].id,
                    content="Could you review the demo flow before class?",
                    created_at=now - timedelta(minutes=90),
                ),
                Message(
                    conversation_id=conversation.id,
                    sender_id=users["maya"].id,
                    content="Yes. I will check the feed and notification states.",
                    created_at=now - timedelta(minutes=45),
                ),
            ]
        )

        db.session.add_all(
            [
                Notification(
                    recipient_id=users["alex"].id,
                    actor_id=users["maya"].id,
                    notification_type="follow",
                    created_at=now - timedelta(days=1),
                ),
                Notification(
                    recipient_id=users["alex"].id,
                    actor_id=users["maya"].id,
                    post_id=posts["alex"].id,
                    notification_type="like",
                    created_at=now - timedelta(hours=5),
                ),
                Notification(
                    recipient_id=users["alex"].id,
                    actor_id=users["zoe"].id,
                    post_id=posts["alex"].id,
                    notification_type="like",
                    created_at=now - timedelta(hours=4, minutes=30),
                ),
                Notification(
                    recipient_id=users["alex"].id,
                    actor_id=users["maya"].id,
                    post_id=posts["alex"].id,
                    notification_type="comment",
                    created_at=now - timedelta(hours=5),
                ),
                Notification(
                    recipient_id=users["alex"].id,
                    actor_id=users["maya"].id,
                    post_id=posts["alex"].id,
                    notification_type="repost",
                    created_at=now - timedelta(hours=3),
                ),
                Notification(
                    recipient_id=users["alex"].id,
                    actor_id=users["maya"].id,
                    notification_type="message",
                    created_at=now - timedelta(minutes=45),
                ),
            ]
        )
        db.session.commit()

        return {
            "users": len(users),
            "posts": len(posts) + 1,
            "follows": 6,
            "notifications": 6,
            "messages": 2,
        }


def main():
    parser = argparse.ArgumentParser(description="Create myownX classroom demo data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing database data before creating the demo dataset.",
    )
    args = parser.parse_args()

    try:
        summary = seed_demo_data(app, reset=args.reset)
    except ValueError as error:
        parser.error(str(error))

    print(
        "Created demo data: "
        f"{summary['users']} users, {summary['posts']} posts, {summary['follows']} follows, "
        f"{summary['notifications']} notifications, and {summary['messages']} messages."
    )
    print(f"Demo account password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
