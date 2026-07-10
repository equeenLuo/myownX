import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from models import Conversation, ConversationMember, Follow, Like, Message, Notification, Post, User, UserSettings, db
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
        detail_page = self.client.get(f"/posts/{post_id}")
        self.assertEqual(detail_page.status_code, 200)
        self.assertIn(b"Alice demo post", detail_page.data)
        self.assertIn(b"Looks good", detail_page.data)
        draft_response = self.client.get(f"/messages/start/{alice_id}")
        self.assertEqual(draft_response.status_code, 200)
        self.assertIn(b"Alice", draft_response.data)
        self.assertIn(b"Start a new message...", draft_response.data)
        self.assertNotIn(b"No messages in this conversation yet.", draft_response.data)
        with self.app.app_context():
            self.assertEqual(Conversation.query.filter_by(conversation_type="private").count(), 0)

        conversation_response = self.client.post(
            f"/messages/start/{alice_id}",
            data={"content": "Ready for the classroom demo."},
            follow_redirects=False,
        )
        self.assertEqual(conversation_response.status_code, 302)
        conversation_id = int(conversation_response.headers["Location"].rstrip("/").split("/")[-1])

        with self.app.app_context():
            self.assertEqual(Like.query.filter_by(user_id=bob_id, post_id=post_id).count(), 1)
            self.assertEqual(Post.query.filter_by(user_id=bob_id, reply_to_post_id=post_id).count(), 1)
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

        self.assertEqual(self.client.get(f"/posts/{private_post_id}").status_code, 404)

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
        self.assertEqual(self.client.get(f"/posts/{private_post_id}").status_code, 200)

        with self.app.app_context():
            db.session.add(Follow(follower_id=bob_id, following_id=alice_id))
            db.session.commit()

        profile_page = self.client.get(f"/users/{bob_id}")
        self.assertIn(f'/messages/start/{bob_id}'.encode(), profile_page.data)
        draft_response = self.client.get(f"/messages/start/{bob_id}")
        self.assertEqual(draft_response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Conversation.query.filter_by(conversation_type="private").count(), 0)

        self.assertEqual(
            self.client.post(
                f"/messages/start/{bob_id}",
                data={"content": "Hello Bob"},
                follow_redirects=False,
            ).status_code,
            302,
        )
        with self.app.app_context():
            self.assertEqual(Conversation.query.filter_by(conversation_type="private").count(), 1)

    def test_group_chat_creates_members_and_tracks_group_notifications(self):
        alice_id = self.create_user("alice", "Alice")
        bob_id = self.create_user("bob", "Bob")
        carol_id = self.create_user("carol", "Carol")

        self.login("alice")
        response = self.client.post(
            "/messages/group",
            data={
                "title": "Study group",
                "participant_ids": [str(bob_id), str(carol_id)],
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        conversation_id = int(response.headers["Location"].rstrip("/").split("/")[-1])

        with self.app.app_context():
            conversation = db.session.get(Conversation, conversation_id)
            self.assertEqual(conversation.conversation_type, "group")
            self.assertEqual(conversation.title, "Study group")
            self.assertEqual(ConversationMember.query.filter_by(conversation_id=conversation_id).count(), 3)

        self.client.post(
            f"/messages/{conversation_id}",
            data={"content": "Bring your notes for the group chat."},
            follow_redirects=True,
        )
        with self.app.app_context():
            notifications = Notification.query.filter_by(
                conversation_id=conversation_id,
                notification_type="message",
            ).all()
            self.assertEqual({notification.recipient_id for notification in notifications}, {bob_id, carol_id})

        self.logout()
        self.login("bob")
        group_page = self.client.get(f"/messages/{conversation_id}")
        self.assertIn(b"Study group", group_page.data)
        self.assertIn(b"3 members", group_page.data)
        with self.app.app_context():
            self.assertEqual(
                Notification.query.filter_by(
                    recipient_id=bob_id,
                    conversation_id=conversation_id,
                    is_read=False,
                ).count(),
                0,
            )
            self.assertEqual(
                Notification.query.filter_by(
                    recipient_id=carol_id,
                    conversation_id=conversation_id,
                    is_read=False,
                ).count(),
                1,
            )

        self.logout()
        self.login("alice")
        duplicate_response = self.client.post(
            "/messages/group",
            data={"participant_ids": [str(bob_id), str(carol_id)]},
            follow_redirects=False,
        )
        self.assertEqual(duplicate_response.headers["Location"], f"/messages/{conversation_id}")
        with self.app.app_context():
            self.assertEqual(Conversation.query.filter_by(conversation_type="group").count(), 1)

    def test_profile_relationship_lists_and_post_timestamps(self):
        alice_id = self.create_user("alice", "Alice")
        bob_id = self.create_user("bob", "Bob")
        carol_id = self.create_user("carol", "Carol")

        with self.app.app_context():
            post = Post(
                user_id=alice_id,
                content="Timestamped post",
                created_at=datetime(2026, 7, 9, 14, 53),
            )
            db.session.add_all(
                [
                    Follow(follower_id=bob_id, following_id=alice_id),
                    Follow(follower_id=alice_id, following_id=carol_id),
                    post,
                ]
            )
            db.session.commit()
            post_id = post.id

            post.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2, hours=12)
            db.session.commit()

        self.login("alice")
        profile_page = self.client.get("/profile")
        self.assertIn(f"/users/{alice_id}/followers".encode(), profile_page.data)
        self.assertIn(f"/users/{alice_id}/following".encode(), profile_page.data)

        followers_page = self.client.get(f"/users/{alice_id}/followers")
        following_page = self.client.get(f"/users/{alice_id}/following")
        self.assertIn(b"Bob", followers_page.data)
        self.assertIn(b"Carol", following_page.data)

        feed_page = self.client.get("/feed")
        self.assertIn(b"2d", feed_page.data)

        with self.app.app_context():
            post = db.session.get(Post, post_id)
            post.created_at = datetime(2026, 7, 9, 14, 53)
            db.session.commit()

        detail_page = self.client.get(f"/posts/{post_id}")
        self.assertIn(b"2:53 PM", detail_page.data)
        self.assertIn(b"Jul 9, 2026", detail_page.data)

    def test_replies_are_interactive_posts_with_nested_replies(self):
        alice_id = self.create_user("alice", "Alice")
        bob_id = self.create_user("bob", "Bob")

        with self.app.app_context():
            post = Post(user_id=alice_id, content="Original post")
            db.session.add(post)
            db.session.commit()
            post_id = post.id

        self.login("bob")
        self.client.post(
            f"/posts/{post_id}/comment",
            data={"content": "First reply"},
            follow_redirects=True,
        )
        with self.app.app_context():
            reply = Post.query.filter_by(user_id=bob_id, reply_to_post_id=post_id).one()
            reply_id = reply.id

        feed_with_reply = self.client.get("/feed")
        self.assertIn(f'data-post-id="{reply_id}"'.encode(), feed_with_reply.data)
        self.assertIn(b"Replying to", feed_with_reply.data)
        explore_with_reply = self.client.get("/discover")
        self.assertIn(f'data-post-id="{reply_id}"'.encode(), explore_with_reply.data)

        self.client.post(f"/posts/{reply_id}/like", follow_redirects=True)
        self.client.post(f"/posts/{reply_id}/repost", follow_redirects=True)

        self.logout()
        self.login("alice")
        nested_response = self.client.post(
            f"/posts/{reply_id}/comment",
            data={"content": "Nested reply", "return_to_post_id": str(reply_id)},
            follow_redirects=False,
        )
        self.assertEqual(nested_response.headers["Location"], f"/posts/{reply_id}")

        with self.app.app_context():
            nested_reply = Post.query.filter_by(reply_to_post_id=reply_id).one()
            nested_reply_id = nested_reply.id
            self.assertEqual(Like.query.filter_by(user_id=bob_id, post_id=reply_id).count(), 1)
            self.assertEqual(Post.query.filter_by(user_id=bob_id, repost_from_id=reply_id).count(), 1)

        self.logout()
        self.login("bob")
        self.client.post(
            f"/posts/{nested_reply_id}/comment",
            data={"content": "Fourth reply"},
            follow_redirects=True,
        )
        with self.app.app_context():
            fourth_reply = Post.query.filter_by(reply_to_post_id=nested_reply_id).one()
            fourth_reply_id = fourth_reply.id

        self.logout()
        self.login("alice")
        self.client.post(
            f"/posts/{fourth_reply_id}/comment",
            data={"content": "Fifth reply"},
            follow_redirects=True,
        )
        with self.app.app_context():
            fifth_reply = Post.query.filter_by(reply_to_post_id=fourth_reply_id).one()

        root_detail = self.client.get(f"/posts/{post_id}")
        self.assertIn(b"First reply", root_detail.data)
        self.assertIn(b"Nested reply", root_detail.data)
        self.assertNotIn(b"Fourth reply", root_detail.data)
        self.assertIn(b"Show more replies", root_detail.data)

        expanded_root_detail = self.client.get(f"/posts/{post_id}?reply_depth=4")
        self.assertIn(b"Fourth reply", expanded_root_detail.data)
        self.assertIn(b"Fifth reply", expanded_root_detail.data)

        deepest_detail = self.client.get(f"/posts/{fifth_reply.id}")
        chain_positions = [
            deepest_detail.data.find(text)
            for text in (b"Original post", b"First reply", b"Nested reply", b"Fourth reply", b"Fifth reply")
        ]
        self.assertTrue(all(position >= 0 for position in chain_positions))
        self.assertEqual(chain_positions, sorted(chain_positions))
        self.assertIn(b"Replying to", deepest_detail.data)
        self.assertIn(f'href="/users/{bob_id}">@bob</a>'.encode(), deepest_detail.data)

    def test_social_actions_return_local_json_without_success_flashes(self):
        alice_id = self.create_user("alice", "Alice")
        bob_id = self.create_user("bob", "Bob")

        with self.app.app_context():
            post = Post(user_id=alice_id, content="Async post")
            db.session.add(post)
            db.session.commit()
            post_id = post.id

        self.login("bob")
        headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}

        follow_response = self.client.post(f"/users/{alice_id}/follow", headers=headers)
        self.assertEqual(follow_response.get_json()["following"], True)

        like_response = self.client.post(f"/posts/{post_id}/like", headers=headers)
        like_payload = like_response.get_json()
        self.assertTrue(like_payload["liked"])
        self.assertEqual(like_payload["like_count"], 1)

        reply_response = self.client.post(
            f"/posts/{post_id}/comment",
            data={"content": "Async reply"},
            headers=headers,
        )
        reply_payload = reply_response.get_json()
        self.assertEqual(reply_payload["action"], "reply")
        self.assertIn("Async reply", reply_payload["reply_html"])

        with self.client.session_transaction() as session:
            self.assertNotIn("_flashes", session)

        with self.app.app_context():
            self.assertEqual(Post.query.filter_by(user_id=bob_id, reply_to_post_id=post_id).count(), 1)

    def test_search_matches_users_and_visible_standalone_posts(self):
        alice_id = self.create_user("alice", "Alice Example")
        bob_id = self.create_user("bob", "Robert")
        carol_id = self.create_user("carol", "Carol")

        with self.app.app_context():
            public_post = Post(user_id=alice_id, content="Flask classroom search demo")
            private_post = Post(user_id=bob_id, content="Flask private search demo")
            reply = Post(user_id=carol_id, content="Flask reply should stay hidden", reply_to_post_id=public_post.id)
            repost = Post(user_id=carol_id, content="", repost_from_id=public_post.id)
            db.session.add_all(
                [
                    public_post,
                    private_post,
                    UserSettings(user_id=bob_id, is_private=True),
                ]
            )
            db.session.flush()
            reply.reply_to_post_id = public_post.id
            repost.repost_from_id = public_post.id
            db.session.add_all([reply, repost])
            db.session.commit()

        public_search = self.client.get("/search?q=flask")
        self.assertEqual(public_search.status_code, 200)
        self.assertIn(b"Flask classroom search demo", public_search.data)
        self.assertNotIn(b"Flask private search demo", public_search.data)
        self.assertNotIn(b"Flask reply should stay hidden", public_search.data)

        user_search = self.client.get("/search?q=example")
        self.assertIn(b"Alice Example", user_search.data)

        empty_search = self.client.get("/search")
        self.assertIn(b"Try searching for people or posts.", empty_search.data)

        long_search = self.client.get("/search?q=" + ("a" * 101))
        self.assertIn(b"Search query must be 100 characters or fewer.", long_search.data)

        self.login("carol")
        self.client.post(f"/users/{bob_id}/follow", follow_redirects=True)
        followed_search = self.client.get("/search?q=private")
        self.assertIn(b"Flask private search demo", followed_search.data)

    def test_profile_banner_upload_and_default_banner_helper(self):
        user_id = self.create_user("alice", "Alice")
        self.login("alice")

        response = self.client.post(
            "/profile/edit",
            data={
                "display_name": "Alice",
                "bio": "Banner test",
                "profile_banner": (BytesIO(b"\x89PNG\r\n\x1a\n"), "banner.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            user = db.session.get(User, user_id)
            self.assertTrue(user.profile_banner_path.startswith("uploads/banners/banner_"))
            self.uploaded_paths.append(Path(self.app.static_folder) / user.profile_banner_path)

        with self.app.test_request_context():
            helpers = {}
            for processor in self.app.template_context_processors[None]:
                helpers.update(processor())

            self.assertIn("uploads/banners/banner_", helpers["user_banner_url"](user))
            self.assertTrue(
                helpers["user_banner_url"](User(username="new", display_name="New")).endswith(
                    "/static/images/default-banner.svg"
                )
            )

        reset_banner = self.client.post(
            "/profile/edit",
            data={
                "display_name": "Alice",
                "bio": "Banner test",
                "remove_profile_banner": "on",
            },
            follow_redirects=False,
        )
        self.assertEqual(reset_banner.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, user_id).profile_banner_path)

        invalid_banner = self.client.post(
            "/profile/edit",
            data={
                "display_name": "Alice",
                "bio": "Banner test",
                "profile_banner": (BytesIO(b"not-an-image"), "banner.txt"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Profile banner must be a png, jpg, jpeg, gif, or webp file.", invalid_banner.data)

    def test_profile_tabs_show_posts_replies_and_likes(self):
        alice_id = self.create_user("alice", "Alice")
        bob_id = self.create_user("bob", "Bob")

        with self.app.app_context():
            alice_post = Post(user_id=alice_id, content="Alice standalone post")
            bob_post = Post(user_id=bob_id, content="Bob liked post")
            db.session.add_all([alice_post, bob_post])
            db.session.flush()
            alice_reply = Post(
                user_id=alice_id,
                content="Alice reply post",
                reply_to_post_id=alice_post.id,
            )
            db.session.add_all([alice_reply, Like(user_id=alice_id, post_id=bob_post.id)])
            db.session.commit()
            alice_post_id = alice_post.id
            alice_reply_id = alice_reply.id
            bob_post_id = bob_post.id

        self.login("alice")

        posts_page = self.client.get("/profile?tab=posts")
        self.assertIn(b"Alice standalone post", posts_page.data)
        self.assertIn(f'data-post-id="{alice_post_id}"'.encode(), posts_page.data)
        self.assertNotIn(f'data-post-id="{alice_reply_id}"'.encode(), posts_page.data)
        self.assertNotIn(f'data-post-id="{bob_post_id}"'.encode(), posts_page.data)

        replies_page = self.client.get("/profile?tab=replies")
        self.assertIn(b"Alice reply post", replies_page.data)
        self.assertIn(b"Replying to", replies_page.data)
        self.assertIn(f'data-post-id="{alice_reply_id}"'.encode(), replies_page.data)
        self.assertNotIn(f'data-post-id="{alice_post_id}"'.encode(), replies_page.data)

        likes_page = self.client.get("/profile?tab=likes")
        self.assertIn(b"Bob liked post", likes_page.data)
        self.assertIn(f'data-post-id="{bob_post_id}"'.encode(), likes_page.data)
        self.assertNotIn(f'data-post-id="{alice_reply_id}"'.encode(), likes_page.data)
        self.assertIn(b"profile-tab text-decoration-none active", likes_page.data)

    def test_seed_data_creates_a_complete_demo_dataset(self):
        summary = seed_demo_data(self.app)
        self.assertEqual(summary["users"], 4)
        self.assertEqual(summary["posts"], 7)
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
