from database import DatabaseManager
import json
import os

class UserManager:
    CONFIG_FILE = "free_user_limit.json"

    def __init__(self):
        self.db = DatabaseManager()
        self.default_free_limit = self.load_free_limit()

    def load_free_limit(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    return int(data.get("free_limit", 1000))
            except Exception:
                return 1000
        return 1000

    def save_free_limit(self, new_limit):
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"free_limit": new_limit}, f)
            self.default_free_limit = new_limit
        except Exception:
            pass

    def get_or_create_user(self, user_id, username=None):
        user = self.db.get_user(user_id)
        if not user:
            self.db.add_user(user_id, username)
            user = self.db.get_user(user_id)
        return user

    def get_user_stats(self, user_id):
        stats = self.db.get_user_stats(user_id) or {}
        # Provide defaults and logic for missing fields
        stats.setdefault('is_owner', False)
        stats.setdefault('is_vip', False)
        stats.setdefault('message_count', 0)
        # Set message limits and speed
        if stats['is_owner'] or stats['is_vip']:
            stats['message_limit'] = float('inf')
            stats['remaining_messages'] = float('inf')
            stats['speed_limit'] = 100.0  # or any high value for VIP/owner
        else:
            stats['message_limit'] = self.default_free_limit
            stats['remaining_messages'] = stats['message_limit'] - stats['message_count']
            stats['speed_limit'] = 2.0  # or your free user speed
        return stats

    def is_owner(self, user_id):
        user = self.db.get_user(user_id)
        return user.get('is_owner', False) if user else False

    def can_send_messages(self, user_id):
        stats = self.get_user_stats(user_id)
        if stats['is_owner'] or stats['is_vip']:
            return True
        if not (stats['is_owner'] or stats['is_vip']) and stats['message_count'] >= stats['message_limit']:
            # Optionally, trigger a notification or log here
            return False
        return True

    def increment_message_count(self, user_id, count=1):
        for _ in range(count):
            self.db.increment_message_count(user_id)

    def promote_to_vip(self, user_id):
        """Promote a user to VIP status."""
        try:
            self.db.set_vip_status(user_id, True)
            return True
        except Exception as e:
            return False

    def demote_from_vip(self, user_id):
        """Remove VIP status from a user."""
        try:
            self.db.set_vip_status(user_id, False)
            return True
        except Exception as e:
            return False

    # Add your user management methods here
