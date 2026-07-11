import argparse
import random
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import app
from models import Conversation, ConversationMember, Follow, Like, Message, Notification, Post, User, UserSettings, db


DEMO_PASSWORD = "123456"
TEST_USERNAMES = tuple(f"test{index}" for index in range(1, 11))
COMMUNITY_USERNAMES = tuple(f"community{index:03d}" for index in range(1, 111))
DEMO_USERNAMES = TEST_USERNAMES + COMMUNITY_USERNAMES
ROOT_POST_COUNT = 1200
DIRECT_REPLY_COUNT = 300
NESTED_REPLY_COUNT = 60
REPOST_COUNT = 180
POST_IMAGE_EVERY = 8

FIRST_NAMES = (
    "Avery", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Jamie", "Quinn", "Skyler", "Rowan",
    "Alex", "Maya", "Noah", "Zoe", "Theo", "Nina", "Leo", "Iris", "Sam", "Emery",
)
LAST_NAMES = (
    "Chen", "Patel", "Garcia", "Kim", "Nguyen", "Wilson", "Martin", "Brown", "Davis", "Lopez",
    "Clark", "Lewis", "Walker", "Hall", "Young", "King", "Wright", "Green", "Baker", "Adams",
)
BIOS = (
    "Building small things, learning in public, and sharing useful notes.",
    "Design, books, good coffee, and calm conversations.",
    "Software student documenting projects and everyday discoveries.",
    "Photography, city walks, food experiments, and friendly debates.",
    "Interested in technology, education, sports, and thoughtful communities.",
    "Making time for music, movement, and one interesting idea each day.",
)
DEMO_ACCOUNT_PROFILES = {
    "test1": ("Building a classroom demo one careful feature at a time.", ("a more useful empty state", "the final feed polish", "a cleaner reply flow")),
    "test2": ("Collecting interface details, study notes, and good design references.", ("a navigation spacing pass", "a small accessibility improvement", "a photo from the desk setup")),
    "test3": ("Learning Flask, keeping project notes, and sharing practical fixes.", ("a migration that finally behaved", "a test case worth keeping", "a quiet debugging win")),
    "test4": ("Coffee, campus walks, and a growing list of thoughtful product ideas.", ("a campus café observation", "a short walk between classes", "a note from a design review")),
    "test5": ("Exploring visual systems, small interactions, and approachable tools.", ("a color choice that simplified the screen", "a better loading state", "a small interaction that felt right")),
    "test6": ("Trying to make technical projects easier to understand and explain.", ("a clearer project explanation", "a helpful peer review", "a change that reduced confusion")),
    "test7": ("Balancing coursework, side projects, playlists, and late-night ideas.", ("a productive library session", "a playlist for focused work", "a side-project checkpoint")),
    "test8": ("Interested in community building, writing, and the craft behind simple apps.", ("a useful community prompt", "a draft that became shorter", "a conversation worth revisiting")),
    "test9": ("Sharing progress on design experiments and everyday learning.", ("a layout experiment", "a note from usability feedback", "a small before-and-after")),
    "test10": ("Keeping a calm record of what worked, what changed, and what is next.", ("a retrospective note", "a small team win", "a plan for the next iteration")),
}
COLORS = (
    ("#1d9bf0", "#7dd3fc"), ("#7c3aed", "#c4b5fd"), ("#059669", "#6ee7b7"),
    ("#ea580c", "#fdba74"), ("#db2777", "#f9a8d4"), ("#2563eb", "#93c5fd"),
    ("#0f766e", "#5eead4"), ("#9333ea", "#d8b4fe"), ("#b45309", "#fcd34d"),
)
TOPICS = (
    "a tiny Flask feature", "a better study routine", "the 2026 World Cup", "Wimbledon championship week",
    "humanoid robotics", "a neighborhood café", "a new science-fiction novel", "an accessible interface",
    "a weekend train trip", "a home-cooked dinner", "an open-source release", "a photography walk",
    "a useful keyboard shortcut", "a calm morning playlist", "a local museum visit", "a team retrospective",
    "a responsive layout", "summer streaming releases", "a personal knowledge system", "an evening run",
)
OPENERS = (
    "Small observation:", "Today I learned:", "A useful reminder:", "Quick update:", "Worth discussing:",
    "One thing that worked:", "Current favorite:", "A note for later:", "Unexpectedly good:", "Tiny win:",
)
POST_MOMENTS = (
    "after a short review with a classmate", "while cleaning up notes from this morning", "during a quiet hour in the library",
    "after comparing the first and second version side by side", "while preparing the next classroom demo", "between two focused work sessions",
    "after a quick usability check", "while organizing a small project board", "after taking a break from a stubborn bug",
    "during a walk back from campus", "while reviewing feedback from the group", "after a useful conversation over coffee",
)
POST_OBSERVATIONS = (
    "The clearest option was also the one with the fewest moving parts.", "A little more space made the next action obvious.",
    "Writing down the trade-off made the decision much easier.", "The first-time-user perspective changed what I wanted to keep.",
    "The smallest adjustment had the biggest effect on the flow.", "It is easier to improve a feature once the purpose is written in one sentence.",
    "A calm, predictable layout made the content feel more trustworthy.", "The best feedback was specific enough to act on right away.",
    "Reducing one extra choice made the whole screen feel lighter.", "The draft improved as soon as I stopped trying to say everything at once.",
    "Seeing the work in context answered more questions than another long discussion.", "The final version feels quieter, but much more intentional.",
)
POST_NEXT_STEPS = (
    "I am saving that approach for the next pass.", "Next I want to test it with someone new to the project.",
    "It is a good reminder to keep the feedback loop short.", "I will keep the change and watch how it holds up tomorrow.",
    "That is enough progress for today, and it feels like the right kind.", "I am curious what a different team would notice first.",
    "The next step is to document it before the context disappears.", "I would happily repeat this process on the next feature.",
)
REPLY_STARTS = (
    "I had a similar reaction.", "That is a helpful way to frame it.", "This is a good reminder.", "I like the practical example here.",
    "That trade-off makes sense to me.", "I ran into something close to this last week.", "The timing of this note is perfect.",
    "I had not considered that angle before.", "This makes the decision feel much clearer.", "I am glad you wrote this down.",
)
REPLY_DETAILS = (
    "Keeping the first version small usually reveals what actually matters.", "A fresh pair of eyes catches the assumptions we stop seeing.",
    "The part about reducing friction is especially useful.", "It is easier to trust a change when the reason is visible in the interface.",
    "I would keep the experiment and compare it again after a few days.", "The simple explanation is often the best test of whether the idea is ready.",
    "That is the kind of detail that makes a demo feel considered.", "I am adding this to my own checklist for the next review.",
    "The example makes the benefit much easier to picture.", "This is a stronger result than adding another layer of complexity.",
)
REPLY_NEXT_STEPS = (
    "I would be interested to hear what changed after another round of feedback.", "Saving this as a reference for later.",
    "A small follow-up test could make the next decision even easier.", "Thanks for sharing the process, not just the result.",
    "It makes me want to revisit one of my own drafts.", "That feels like a good direction to keep exploring.",
)
CHAT_LINES = (
    "Hey! Are you free to review the demo flow today?",
    "Yes, I can take a look after lunch.",
    "Great. The feed and profile pages are ready for another pass.",
    "I will check the spacing, mobile layout, and empty states.",
    "Could you also search for the Project Aurora notes in this chat?",
    "Found them. Conversation search is working for me.",
    "Nice. I left one comment about the notification background.",
    "Updated. The result feels much cleaner now.",
    "Perfect, I think this is ready for the classroom demo.",
    "Thanks! I will do one final run before class.",
)


def _profile_identity(index, username):
    if username in TEST_USERNAMES:
        return username
    offset = index - len(TEST_USERNAMES)
    return f"{FIRST_NAMES[offset % len(FIRST_NAMES)]} {LAST_NAMES[(offset * 7) % len(LAST_NAMES)]}"


def _write_profile_assets(static_folder, index, display_name):
    avatar_dir = Path(static_folder) / "uploads" / "avatars"
    banner_dir = Path(static_folder) / "uploads" / "banners"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    banner_dir.mkdir(parents=True, exist_ok=True)
    first, second = COLORS[index % len(COLORS)]
    initials = "".join(part[0] for part in display_name.split()[:2]).upper() or "X"
    safe_initials = escape(initials)
    avatar_name = f"demo-avatar-{index + 1:03d}.svg"
    banner_name = f"demo-banner-{index + 1:03d}.svg"
    avatar_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="{first}"/><stop offset="1" stop-color="{second}"/></linearGradient></defs><rect width="128" height="128" rx="64" fill="url(#g)"/><circle cx="96" cy="28" r="22" fill="#fff" opacity=".16"/><text x="64" y="76" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="42" font-weight="700" fill="#fff">{safe_initials}</text></svg>'''
    banner_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="{first}"/><stop offset="1" stop-color="{second}"/></linearGradient></defs><rect width="1200" height="400" fill="url(#g)"/><circle cx="980" cy="80" r="220" fill="#fff" opacity=".10"/><circle cx="160" cy="420" r="280" fill="#fff" opacity=".08"/><path d="M0 310 Q300 180 600 300 T1200 230 V400 H0Z" fill="#fff" opacity=".10"/></svg>'''
    (avatar_dir / avatar_name).write_text(avatar_svg, encoding="utf-8")
    (banner_dir / banner_name).write_text(banner_svg, encoding="utf-8")
    return f"uploads/avatars/{avatar_name}", f"uploads/banners/{banner_name}"


def _write_post_assets(static_folder, count=72):
    post_dir = Path(static_folder) / "uploads" / "posts"
    post_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        first, second = COLORS[(index + 2) % len(COLORS)]
        filename = f"demo-post-{index + 1:03d}.svg"
        title = escape(TOPICS[index % len(TOPICS)].title())
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="{first}"/><stop offset="1" stop-color="{second}"/></linearGradient></defs><rect width="1200" height="800" fill="url(#g)"/><circle cx="950" cy="140" r="210" fill="#fff" opacity=".14"/><path d="M0 620 L260 380 470 570 710 300 1200 680 V800 H0Z" fill="#0f1419" opacity=".22"/><text x="70" y="110" font-family="Helvetica,Arial,sans-serif" font-size="52" font-weight="700" fill="#fff">{title}</text></svg>'''
        (post_dir / filename).write_text(svg, encoding="utf-8")
        paths.append(f"uploads/posts/{filename}")
    return paths


def _profile_bio(username, index):
    return DEMO_ACCOUNT_PROFILES.get(username, (BIOS[index % len(BIOS)], ()))[0]


def _root_post_content(index, author, author_post_number):
    profile = DEMO_ACCOUNT_PROFILES.get(author.username)
    topic_pool = profile[1] if profile else TOPICS
    topic = topic_pool[author_post_number % len(topic_pool)]
    return (
        f"{OPENERS[index % len(OPENERS)]} I spent some time with {topic} {POST_MOMENTS[(index * 3) % len(POST_MOMENTS)]}. "
        f"{POST_OBSERVATIONS[(index * 5 + author_post_number) % len(POST_OBSERVATIONS)]} "
        f"{POST_NEXT_STEPS[(index * 7 + author_post_number) % len(POST_NEXT_STEPS)]}"
    )


def _reply_content(index, depth=0):
    prefix = "Following up, " if depth else ""
    return (
        f"{prefix}{REPLY_STARTS[index % len(REPLY_STARTS)]} "
        f"{REPLY_DETAILS[(index * 3 + depth) % len(REPLY_DETAILS)]} "
        f"{REPLY_NEXT_STEPS[(index * 5 + depth) % len(REPLY_NEXT_STEPS)]}"
    )


def _unique_content(content, used_contents, index):
    if content in used_contents:
        content = f"{content} I am keeping this as note {index + 1} for the next review."
    suffix = 2
    while content in used_contents:
        content = f"{content} ({suffix})"
        suffix += 1
    used_contents.add(content)
    return content


def seed_demo_data(flask_app, reset=False):
    """Build a large, deterministic classroom dataset with safe original content."""
    with flask_app.app_context():
        if reset:
            db.drop_all()
            db.create_all()
        elif User.query.filter(User.username.in_(DEMO_USERNAMES)).first():
            raise ValueError("Demo users already exist. Run with --reset to rebuild the demo database.")

        rng = random.Random(20260710)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        password_hash = generate_password_hash(DEMO_PASSWORD)
        generate_assets = not flask_app.config.get("TESTING", False)
        post_asset_paths = _write_post_assets(flask_app.static_folder) if generate_assets else [
            f"uploads/posts/demo-post-{index + 1:03d}.svg" for index in range(72)
        ]

        users = []
        for index, username in enumerate(DEMO_USERNAMES):
            display_name = _profile_identity(index, username)
            if generate_assets:
                avatar_path, banner_path = _write_profile_assets(flask_app.static_folder, index, display_name)
            else:
                avatar_path = f"uploads/avatars/demo-avatar-{index + 1:03d}.svg"
                banner_path = f"uploads/banners/demo-banner-{index + 1:03d}.svg"
            users.append(
                User(
                    username=username,
                    email=f"{username}@example.test",
                    display_name=display_name,
                    bio=_profile_bio(username, index),
                    password_hash=password_hash,
                    profile_picture_path=avatar_path,
                    profile_banner_path=banner_path,
                    created_at=now - timedelta(days=180 - index),
                )
            )
        db.session.add_all(users)
        db.session.flush()
        db.session.add_all(
            UserSettings(user_id=user.id, is_private=False, allow_dms=True)
            for user in users
        )

        follow_pairs = set()
        follow_steps = (1, 2, 3, 5, 8, 13, 21, 34, 55)
        for index, follower in enumerate(users):
            for step in follow_steps:
                following = users[(index + step) % len(users)]
                follow_pairs.add((follower.id, following.id))
            for following_index in rng.sample(range(len(users)), 5):
                if following_index != index:
                    follow_pairs.add((follower.id, users[following_index].id))
        follows = [Follow(follower_id=follower_id, following_id=following_id) for follower_id, following_id in follow_pairs]
        db.session.add_all(follows)

        root_posts = []
        used_post_contents = set()
        for index in range(ROOT_POST_COUNT):
            author = users[index % len(users)]
            author_post_number = index // len(users)
            has_media = index % POST_IMAGE_EVERY == 0 or (
                author.username in TEST_USERNAMES and author_post_number in {0, 5}
            )
            root_posts.append(
                Post(
                    user_id=author.id,
                    content=_unique_content(
                        _root_post_content(index, author, author_post_number),
                        used_post_contents,
                        index,
                    ),
                    media_path=post_asset_paths[(index // POST_IMAGE_EVERY) % len(post_asset_paths)] if has_media else None,
                    media_type="image" if has_media else "text",
                    created_at=now - timedelta(minutes=5 + index * 47),
                )
            )
        db.session.add_all(root_posts)
        db.session.flush()

        direct_replies = []
        for index in range(DIRECT_REPLY_COUNT):
            parent = root_posts[(index * 17) % len(root_posts)]
            author = users[(index * 11 + 7) % len(users)]
            if author.id == parent.user_id:
                author = users[(users.index(author) + 1) % len(users)]
            direct_replies.append(
                Post(
                    user_id=author.id,
                    content=_unique_content(
                        _reply_content(index),
                        used_post_contents,
                        ROOT_POST_COUNT + index,
                    ),
                    media_type="text",
                    reply_to_post_id=parent.id,
                    created_at=parent.created_at + timedelta(minutes=12 + index % 90),
                )
            )
        db.session.add_all(direct_replies)
        db.session.flush()

        nested_replies = []
        for index in range(NESTED_REPLY_COUNT):
            parent = direct_replies[(index * 5) % len(direct_replies)]
            author = users[(index * 13 + 19) % len(users)]
            nested_replies.append(
                Post(
                    user_id=author.id,
                    content=_unique_content(
                        _reply_content(index, depth=1),
                        used_post_contents,
                        ROOT_POST_COUNT + DIRECT_REPLY_COUNT + index,
                    ),
                    media_type="text",
                    reply_to_post_id=parent.id,
                    created_at=parent.created_at + timedelta(minutes=18 + index),
                )
            )
        db.session.add_all(nested_replies)

        reposts = []
        repost_keys = set()
        cursor = 0
        while len(reposts) < REPOST_COUNT:
            source = root_posts[(cursor * 19) % len(root_posts)]
            author = users[(cursor * 23 + 9) % len(users)]
            key = (author.id, source.id)
            cursor += 1
            if author.id == source.user_id or key in repost_keys:
                continue
            repost_keys.add(key)
            reposts.append(
                Post(
                    user_id=author.id,
                    content="",
                    media_type="text",
                    repost_from_id=source.id,
                    created_at=source.created_at + timedelta(minutes=30 + cursor),
                )
            )
        db.session.add_all(reposts)

        likes = []
        like_keys = set()
        like_targets = root_posts + direct_replies[:120]
        for index, target in enumerate(like_targets):
            desired_likes = 4 + index % 20
            candidate = index * 7
            while desired_likes:
                liker = users[candidate % len(users)]
                candidate += 11
                key = (liker.id, target.id)
                if liker.id == target.user_id or key in like_keys:
                    continue
                like_keys.add(key)
                likes.append(Like(user_id=liker.id, post_id=target.id, created_at=target.created_at + timedelta(minutes=20)))
                desired_likes -= 1
        db.session.add_all(likes)

        private_pairs = {(users[0].id, users[index].id) for index in range(1, 31)}
        cursor = 1
        while len(private_pairs) < 60:
            first = users[cursor % len(users)].id
            second = users[(cursor + 17) % len(users)].id
            private_pairs.add(tuple(sorted((first, second))))
            cursor += 1

        conversations = []
        all_messages = []
        for index, (first_id, second_id) in enumerate(sorted(private_pairs)):
            conversation = Conversation(conversation_type="private", created_at=now - timedelta(days=10, hours=index))
            db.session.add(conversation)
            db.session.flush()
            db.session.add_all(
                [
                    ConversationMember(conversation_id=conversation.id, user_id=first_id),
                    ConversationMember(conversation_id=conversation.id, user_id=second_id),
                ]
            )
            conversations.append(conversation)
            message_count = 6 + index % 7
            for message_index in range(message_count):
                sender_id = first_id if message_index % 2 == 0 else second_id
                all_messages.append(
                    Message(
                        conversation_id=conversation.id,
                        sender_id=sender_id,
                        content=CHAT_LINES[(index + message_index) % len(CHAT_LINES)],
                        created_at=conversation.created_at + timedelta(minutes=8 * message_index),
                    )
                )

        for group_index in range(8):
            member_users = [users[(group_index * 7 + offset * 13) % len(users)] for offset in range(5)]
            conversation = Conversation(
                conversation_type="group",
                title=("Design Review", "Study Circle", "Weekend Plans", "Project Aurora")[group_index % 4],
                created_at=now - timedelta(days=5, hours=group_index),
            )
            db.session.add(conversation)
            db.session.flush()
            db.session.add_all(
                ConversationMember(conversation_id=conversation.id, user_id=member.id) for member in member_users
            )
            conversations.append(conversation)
            for message_index in range(12):
                sender = member_users[message_index % len(member_users)]
                all_messages.append(
                    Message(
                        conversation_id=conversation.id,
                        sender_id=sender.id,
                        content=CHAT_LINES[(group_index + message_index + 2) % len(CHAT_LINES)],
                        created_at=conversation.created_at + timedelta(minutes=10 * message_index),
                    )
                )
        db.session.add_all(all_messages)
        db.session.flush()

        notifications = []
        for index, like in enumerate(likes[:220]):
            target = db.session.get(Post, like.post_id)
            notifications.append(
                Notification(
                    recipient_id=target.user_id,
                    actor_id=like.user_id,
                    post_id=target.id,
                    notification_type="like",
                    is_read=index % 4 != 0,
                    created_at=like.created_at,
                )
            )
        for index, reply in enumerate(direct_replies[:180]):
            parent = db.session.get(Post, reply.reply_to_post_id)
            notifications.append(
                Notification(
                    recipient_id=parent.user_id,
                    actor_id=reply.user_id,
                    post_id=parent.id,
                    notification_type="comment",
                    is_read=index % 3 != 0,
                    created_at=reply.created_at,
                )
            )
        for index, repost in enumerate(reposts[:100]):
            source = db.session.get(Post, repost.repost_from_id)
            notifications.append(
                Notification(
                    recipient_id=source.user_id,
                    actor_id=repost.user_id,
                    post_id=source.id,
                    notification_type="repost",
                    is_read=index % 5 != 0,
                    created_at=repost.created_at,
                )
            )
        for index, follow in enumerate(follows[:80]):
            notifications.append(
                Notification(
                    recipient_id=follow.following_id,
                    actor_id=follow.follower_id,
                    notification_type="follow",
                    is_read=index % 4 != 0,
                    created_at=now - timedelta(hours=index + 1),
                )
            )
        for index, conversation in enumerate(conversations):
            last_message = next(message for message in reversed(all_messages) if message.conversation_id == conversation.id)
            recipient_ids = [member.user_id for member in conversation.members if member.user_id != last_message.sender_id]
            for recipient_id in recipient_ids[:2]:
                notifications.append(
                    Notification(
                        recipient_id=recipient_id,
                        actor_id=last_message.sender_id,
                        conversation_id=conversation.id,
                        notification_type="message",
                        is_read=index % 3 != 0,
                        created_at=last_message.created_at,
                    )
                )
        db.session.add_all(notifications)
        db.session.commit()

        return {
            "users": User.query.count(),
            "posts": Post.query.count(),
            "root_posts": len(root_posts),
            "replies": len(direct_replies) + len(nested_replies),
            "reposts": len(reposts),
            "likes": len(likes),
            "follows": len(follows),
            "notifications": len(notifications),
            "conversations": len(conversations),
            "messages": len(all_messages),
        }


def main():
    parser = argparse.ArgumentParser(description="Create the myownX classroom demonstration dataset.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing database data before creating the complete demonstration dataset.",
    )
    args = parser.parse_args()

    try:
        summary = seed_demo_data(app, reset=args.reset)
    except ValueError as error:
        parser.error(str(error))

    print(
        "Created demo data: "
        f"{summary['users']} users, {summary['posts']} posts, {summary['likes']} likes, "
        f"{summary['follows']} follows, {summary['conversations']} conversations, "
        f"{summary['notifications']} notifications, and {summary['messages']} messages."
    )
    print("Test accounts: test1 through test10")
    print(f"Demo account password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
