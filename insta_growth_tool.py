import os
import time
import random
import json
import datetime
from instagrapi import Client

# ==========================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==========================================
INSTAGRAM_USERNAME = "love.couplevids"
INSTAGRAM_PASSWORD = "mAGGROSU123!"
INSTAGRAM_SESSION_FILE = "insta_session.json"
ANALYTICS_FILE = "growth_analytics.json"

# Safety Limits (Daily)
MAX_FOLLOWS_PER_DAY = 50
MAX_UNFOLLOWS_PER_DAY = 50
MAX_LIKES_PER_DAY = 100

# Human Simulation Config
MIN_DELAY = 15
MAX_DELAY = 45
SESSION_BREAK_INTERVAL = 10  # Take a break after every 10 actions
SESSION_BREAK_DURATION = (60, 180)  # Break for 1-3 minutes

# ==========================================
# 📊 ANALYTICS & DASHBOARD ENGINE
# ==========================================
class GrowthManager:
    def __init__(self, client):
        self.cl = client
        self.data = self._load_data()
        self.today = datetime.date.today().isoformat()
        
        # Initialize today's entry if not exists
        if self.today not in self.data["daily_stats"]:
            self.data["daily_stats"][self.today] = {
                "follows": 0,
                "unfollows": 0,
                "likes": 0,
                "followers_start": 0,
                "followers_end": 0
            }
            self._update_follower_count(is_start=True)

    def _load_data(self):
        if os.path.exists(ANALYTICS_FILE):
            try:
                with open(ANALYTICS_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"daily_stats": {}, "targets": {}}

    def _save_data(self):
        with open(ANALYTICS_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def _update_follower_count(self, is_start=False):
        try:
            my_info = self.cl.user_info(self.cl.user_id)
            count = my_info.follower_count
            if is_start:
                self.data["daily_stats"][self.today]["followers_start"] = count
            self.data["daily_stats"][self.today]["followers_end"] = count
            self._save_data()
            return count
        except Exception as e:
            print(f"⚠️ Could not fetch follower count: {e}")
            return 0

    def log_action(self, action_type):
        self.data["daily_stats"][self.today][action_type] += 1
        self._save_data()

    def check_limit(self, action_type):
        current = self.data["daily_stats"][self.today].get(action_type, 0)
        limit = {
            "follows": MAX_FOLLOWS_PER_DAY,
            "unfollows": MAX_UNFOLLOWS_PER_DAY,
            "likes": MAX_LIKES_PER_DAY
        }.get(action_type, 0)
        
        if current >= limit:
            print(f"\n🛑 SAFETY STOP: Daily limit for {action_type} ({limit}) reached!")
            return False
        return True

    def show_dashboard(self):
        self._update_follower_count()
        stats = self.data["daily_stats"].get(self.today, {})
        
        print("\n" + "="*40)
        print(f" 📈 GROWTH DASHBOARD ({self.today})")
        print("="*40)
        print(f"👥 Followers: {stats.get('followers_end', 0)}")
        print(f"➕ New Today: {stats.get('followers_end', 0) - stats.get('followers_start', 0)}")
        print("-" * 20)
        print(f"✅ Follows:    {stats.get('follows', 0)} / {MAX_FOLLOWS_PER_DAY}")
        print(f"❌ Unfollows:  {stats.get('unfollows', 0)} / {MAX_UNFOLLOWS_PER_DAY}")
        print(f"❤️ Likes:      {stats.get('likes', 0)} / {MAX_LIKES_PER_DAY}")
        print("="*40 + "\n")

# ==========================================
# 🛡️ SAFETY & HUMAN SIMULATION
# ==========================================
class HumanSimulator:
    def __init__(self):
        self.actions_since_break = 0

    def sleep_random(self):
        """Sleeps for a random interval to mimic human behavior."""
        sleep_time = random.randint(MIN_DELAY, MAX_DELAY)
        # Add slight variance (Gaussian-like)
        sleep_time += random.uniform(-2.0, 5.0)
        sleep_time = max(2, sleep_time) # Ensure at least 2 seconds
        
        print(f"   ⏳ Sleeping {sleep_time:.1f}s...", end="\r")
        time.sleep(sleep_time)
        print(" " * 20, end="\r") # Clear line

    def check_break(self):
        """Triggers a 'coffee break' if action threshold is met."""
        self.actions_since_break += 1
        if self.actions_since_break >= SESSION_BREAK_INTERVAL:
            duration = random.randint(*SESSION_BREAK_DURATION)
            print(f"\n☕ Taking a coffee break for {duration} seconds...")
            time.sleep(duration)
            self.actions_since_break = 0
            print("▶️ Break over. Resuming...\n")

# ==========================================
# 🚀 MAIN APP LOGIC
# ==========================================
def login_instagram():
    cl = Client()
    if os.path.exists(INSTAGRAM_SESSION_FILE):
        print("🔑 Loading session...")
        try:
            cl.load_settings(INSTAGRAM_SESSION_FILE)
            cl.get_timeline_feed()
            print("✅ Session active.")
            return cl
        except Exception:
            print("⚠️ Session expired.")
    
    try:
        print("🔐 Logging in with password...")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.dump_settings(INSTAGRAM_SESSION_FILE)
        print("✅ Logged in.")
        return cl
    except Exception as e:
        print(f"❌ Login Error: {e}")
        if "challenge" in str(e).lower():
            print("⚠️ Challenge required. Please resolve via the official app or GUI.")
        return None

def run_follow_strategy(cl, manager, human):
    target = input("🎯 Enter target username (competitor): ").strip()
    try:
        count = int(input("🔢 How many to follow? (Max 20 rec.): ").strip())
    except:
        return

    print(f"\n🔍 Analyzing {target}...")
    try:
        uid = cl.user_id_from_username(target)
        followers = cl.user_followers(uid, amount=min(count * 2, 100))
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    print(f"📋 Found {len(followers)} candidates.")
    processed = 0
    
    for uid, user in followers.items():
        if processed >= count: break
        if not manager.check_limit("follows"): break

        print(f"👉 Following {user.username}...", end=" ")
        try:
            cl.user_follow(uid)
            print("✅")
            manager.log_action("follows")
            processed += 1
            human.sleep_random()
            human.check_break()
        except Exception as e:
            print(f"❌ ({e})")
            time.sleep(5)

def run_unfollow_strategy(cl, manager, human):
    try:
        count = int(input("🔢 How many to unfollow? (Max 20 rec.): ").strip())
    except:
        return

    print("\n🔍 Fetching non-followers...")
    try:
        my_id = cl.user_id
        following = cl.user_following(my_id)
        followers = cl.user_followers(my_id)
        non_followers = [uid for uid in following if uid not in followers]
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    print(f"📉 Found {len(non_followers)} non-followers.")
    processed = 0

    for uid in non_followers:
        if processed >= count: break
        if not manager.check_limit("unfollows"): break

        user = following[uid]
        print(f"👋 Unfollowing {user.username}...", end=" ")
        try:
            cl.user_unfollow(uid)
            print("✅")
            manager.log_action("unfollows")
            processed += 1
            human.sleep_random()
            human.check_break()
        except Exception as e:
            print(f"❌ ({e})")
            time.sleep(5)

def main():
    print("""
    ========================================
       INSTAGRAM GROWTH COMPANION v2.0 🚀
    ========================================
    Note: This tool simulates human behavior.
    Actions are delayed to ensure safety.
    """)
    
    cl = login_instagram()
    if not cl: return

    manager = GrowthManager(cl)
    human = HumanSimulator()

    while True:
        manager.show_dashboard()
        print("1. 🎯 Smart Follow (Competitor Audience)")
        print("2. 🧹 Clean Up (Unfollow Non-Followers)")
        print("3. 🚪 Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            run_follow_strategy(cl, manager, human)
        elif choice == "2":
            run_unfollow_strategy(cl, manager, human)
        elif choice == "3":
            print("Bye! 👋")
            break

if __name__ == "__main__":
    main()
