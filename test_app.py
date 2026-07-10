import os
import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from models import Comment, Conversation, ConversationMember, Follow, Like, Message, Notification, Post, User, UserSettings, db
from seed_data import DEMO_USERNAMES, seed_demo_data


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class MyownXFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        TestConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(self.temp_dir, 'test.db').replace(os.sep, '/')}"
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.uploaded_paths = []

        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()
            db.session.remove()
            db.engine.dispose()
        for uploaded_path in self.uploaded_paths:
            Path(uploaded_path).unlink(missing_ok=True)
        shutil.rmtree(self.temp_dir)

    def create_user(self, username, display_name=None):
        with self.app.app_context():
            user = User(
                username=username,
                display_name=display_name or username.title(),
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(user)
            db.session.commit()
            return user.id

    def login(self, username):
        return self.client.post(
            "/login",
            data={"username": username, "password": "password123"},
            follow_redirects=True,
        )

    def logout(self):
        return self.client.post("/logout", follow_redirects=True)

    def test_registration_social_actions_notifications_and_messages(self):
        bob_id = self.create_user("bob", "Bob")

        response = self.client.post(
            "/register",
            data={"username": "alice", "display_name": "Alice", "password": "password123"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome", response.data)

        self.client.post(
            "/profile/edit",
            data={"display_name": "Alice Updated", "bio": "Ready to present the demo."},
            follow_redirects=True,
        )
        self.client.post("/posts/create", data={"content": "Alice demo post"}, follow_redirects=True)
        self.client.post(
            "/posts/create",
            data={
                "content": "Alice image post",
                "images": (BytesIO(b"\x89PNG\r\n\x1a\n"), "demo.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        with self.app.app_context():
            alice = User.query.filter_by(username="alice").first()
            post = Post.query.filter_by(user_id=alice.id, content="Alice demo post").first()
            image_post = Post.query.filter_by(user_id=alice.id, content="Alice image post").first()
            alice_id = alice.id
            post_id = post.id
            self.assertEqual(alice.display_name, "Alice Updated")
            self.assertEqual(image_post.media_type, "image")
            self.uploaded_paths.append(Path(self.app.static_folder) / image_post.media_path)

        self.logout()
        self.login("bob")
        self.client.post(f"/users/{alice_id}/follow", follow_redirects=True)
        self.client.post(f"/posts/{post_id}/like", follow_redirects=True)
        self.client.post(f"/posts/{post_id}/comment", data={"content": "Looks good"}, follow_redirects=True)
        self.client.post(f"/posts/{post_id}/repost", follow_redirects=True)
        conversation_response = self.client.post(f"/messages/start/{alice_id}", follow_redirects=False)
        self.assertEqual(conversation_response.status_code, 302)
        conversation_id = int(conversation_response.headers["Location"].rstrip("/").split("/")[-1])
        self.client.post(
            f"/messages/{conversation_id}",
            data={"content": "Ready for the classroom demo."},
            follow_redirects=True,
        )

        with self.app.app_context():
            self.assertEqual(Like.query.filter_by(user_id=bob_id, post_id=post_id).count(), 1)
            self.assertEqual(Comment.query.filter_by(user_id=bob_id, post_id=post_id).count(), 1)
            self.assertEqual(Post.query.filter_by(user_id=bob_id, repost_from_id=post_id).count(), 1)
            notification_types = {
                notification.notification_type
                for notification in Notification.query.filter_by(recipient_id=alice_id).all()
            }
            self.assertTrue({"follow", "like", "comment", "repost", "message"}.issubset(notification_types))
            self.assertEqual(Message.query.filter_by(conversation_id=conversation_id, sender_id=bob_id).count(), 1)

        self.logout()
        self.login("alice")
        notification_page = self.client.get("/notifications")
        self.assertIn(b"unread", notification_page.data.lower())
        with self.app.app_context():
            self.assertEqual(
                Notification.query.filter_by(recipient_id=alice_id, is_read=False)
                .filter(Notification.notification_type != "message")
                .count(),
                0,
            )
        self.client.get(f"/messages/{conversation_id}")
        with self.app.app_context():
            self.assertEqual(
                Notification.query.filter_by(
                    recipient_id=alice_id,
                    actor_id=bob_id,
                    notification_type="message",
                    is_read=False,
                ).count(),
                0,
            )

    def test_private_visibility_repost_protection_and_direct_message_permission(self):
        alice_id = self.create_user("alice", "Alice")
        bob_id = self.create_user("bob", "Bob")
        carol_id = self.create_user("carol", "Carol")

        with self.app.app_context():
            private_post = Post(user_id=bob_id, content="Bob private post")
            db.session.add_all(
                [
                    UserSettings(user_id=bob_id, is_private=True, allow_dms=False),
                    private_post,
                ]
            )
            db.session.flush()
            db.session.add(Post(user_id=carol_id, content="", repost_from_id=private_post.id))
            db.session.commit()
            private_post_id = private_post.id

        self.login("alice")
        for path in ("/feed", "/discover", f"/users/{bob_id}", f"/users/{carol_id}"):
            self.assertNotIn(b"Bob private post", self.client.get(path).data)

        self.assertIn(
            b"Post not found.",
            self.client.post(f"/posts/{private_post_id}/like", follow_redirects=True).data,
        )
        self.assertIn(
            b"This user only accepts messages from people they follow.",
            self.client.post(f"/messages/start/{bob_id}", follow_redirects=True).data,
        )

        with self.app.app_context():
            db.session.add(Follow(follower_id=alice_id, following_id=bob_id))
            db.session.commit()

        self.assertIn(b"Bob private post", self.client.get("/feed").data)
        self.assertIn(b"Bob private post", self.client.get(f"/users/{carol_id}").data)

        with self.app.app_context():
            db.session.add(Follow(follower_id=bob_id, following_id=alice_id))
            db.session.commit()

        self.assertEqual(
            self.client.post(f"/messages/start/{bob_id}", follow_redirects=False).status_code,
            302,
        )

    def test_seed_data_creates_a_complete_demo_dataset(self):
        summary = seed_demo_data(self.app)
        self.assertEqual(summary["users"], 4)
        self.assertEqual(summary["posts"], 5)
        self.assertEqual(summary["follows"], 6)
        self.assertEqual(summary["notifications"], 6)
        self.assertEqual(summary["messages"], 2)

        with self.app.app_context():
            self.assertEqual(User.query.filter(User.username.in_(DEMO_USERNAMES)).count(), 4)
            self.assertTrue(UserSettings.query.filter_by(is_private=True, allow_dms=False).first())
            self.assertEqual(Conversation.query.count(), 1)
            self.assertEqual(ConversationMember.query.count(), 2)

        with self.assertRaises(ValueError):
            seed_demo_data(self.app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
