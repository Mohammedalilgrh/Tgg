import asyncio
import random
import json
import os
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, PeerFloodError,
    UserAlreadyParticipantError
)

# === CONFIGURATION - Update with your own Telegram API credentials and phone ===
API_ID = 21706160
API_HASH = "548b91f0e7cd2e44bbee05190620d9f4"
PHONE = "+96407762476460"

# === DATA FILES & PATHS ===
DATA_PATH = "data"
SCRAPED_FILE = os.path.join(DATA_PATH, "scraped_users.json")
ADDED_FILE = os.path.join(DATA_PATH, "added_users.json")
PRIVACY_FILE = os.path.join(DATA_PATH, "privacy_failed.json")
FAILED_FILE = os.path.join(DATA_PATH, "failed_users.json")
ALREADY_FILE = os.path.join(DATA_PATH, "already_participant.json")

# === ANTI-BAN SETTINGS / TIMINGS ===
MIN_DELAY = 60             # seconds delay per add minimum
MAX_DELAY = 120            # seconds delay per add maximum
MAX_ADDS_PER_SESSION = 5   # Restart session after this many successful adds
FLOOD_WAIT_THRESHOLD = 1800  # seconds, abort session if flood wait is more than this (30 mins)
SESSION_MAX_RUNTIME = 7 * 3600  # 7 hours max runtime per session in seconds
SESSION_BREAK_MIN = 3 * 3600    # Minimum break between sessions (3 hours)
SESSION_BREAK_MAX = 7 * 3600    # Maximum break between sessions (7 hours)

# === LOGGING CONFIGURATION ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler()
    ]
)

class TelegramScraper:
    def __init__(self):
        self.api_id = API_ID
        self.api_hash = API_HASH
        self.phone = PHONE
        self.client = None

        os.makedirs(DATA_PATH, exist_ok=True)

        # Load persistent state or init empty
        self.scraped_users = self.load_json(SCRAPED_FILE) or []
        self.added_users = set(self.load_json(ADDED_FILE) or [])
        self.privacy_failed = set(self.load_json(PRIVACY_FILE) or [])
        self.failed_users = set(self.load_json(FAILED_FILE) or [])
        self.already_participant = set(self.load_json(ALREADY_FILE) or [])

        self.session_start_time = None
        self.add_count = 0

    # Simple JSON load/save helpers
    def load_json(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def save_json(self, path, data):
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save {path}: {e}")

    # === Session management ===
    async def start_new_session(self):
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logging.info("Cleanly disconnected previous session.")
        self.client = TelegramClient('session', self.api_id, self.api_hash)
        await self.client.start(phone=self.phone)
        self.session_start_time = asyncio.get_event_loop().time()
        self.add_count = 0
        logging.info("New Telegram client session started.")

    def session_expired(self):
        # Session expires after max add count or max runtime
        elapsed = asyncio.get_event_loop().time() - self.session_start_time if self.session_start_time else 0
        if self.add_count >= MAX_ADDS_PER_SESSION or elapsed >= SESSION_MAX_RUNTIME:
            return True
        return False

    async def session_break(self):
        # Pause between sessions randomly between 3 and 7 hours
        duration = random.randint(SESSION_BREAK_MIN, SESSION_BREAK_MAX)
        logging.info(f"Session break initiated for {duration // 3600}h {(duration % 3600)//60}m ...")
        await asyncio.sleep(duration)
        logging.info("Session break ended.")

    # Human-like delay between adds
    async def safe_delay(self):
        delay = random.randint(MIN_DELAY, MAX_DELAY)
        logging.info(f"Waiting {delay}s to mimic human timing...")
        await asyncio.sleep(delay)

    # === Scrape members of a given channel/group ===
    async def scrape_channel_members(self, channel_username):
        try:
            logging.info(f"Starting scraping from: {channel_username}")
            channel = await self.client.get_entity(channel_username)
            offset = 0
            limit = 100
            new_members_count = 0
            while True:
                if offset > 0:
                    await asyncio.sleep(random.randint(10, 25))
                participants = await self.client(functions.channels.GetParticipantsRequest(
                    channel=channel,
                    filter=types.ChannelParticipantsSearch(''),
                    offset=offset,
                    limit=limit,
                    hash=0
                ))
                if not participants.users:
                    break
                count_new = 0
                for user in participants.users:
                    if user.bot or user.deleted:
                        continue
                    if any(u['id'] == user.id for u in self.scraped_users):
                        continue  # Already stored
                    member_data = {
                        'id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'phone': user.phone,
                        'is_premium': getattr(user, 'premium', False)
                    }
                    self.scraped_users.append(member_data)
                    count_new += 1
                offset += len(participants.users)
                new_members_count += count_new
                logging.info(f"Scraped total {len(self.scraped_users)} users (+{count_new} new this batch)")
                if len(participants.users) < limit:
                    break
            self.save_json(SCRAPED_FILE, self.scraped_users)
            logging.info(f"Scraping finished: {len(self.scraped_users)} users saved total.")
            return new_members_count
        except FloodWaitError as e:
            logging.warning(f"Flood wait while scraping: sleeping {e.seconds} seconds")
            await asyncio.sleep(e.seconds + 10)
        except Exception as e:
            logging.error(f"Error scraping channel {channel_username}: {e}")
        return 0

    # === Add one member safely with session restart + flood handling ===
    async def add_member_to_group(self, target_group, user_data):
        user_key = user_data.get('username') or str(user_data.get('id'))
        if (user_key in self.added_users
                or user_key in self.privacy_failed
                or user_key in self.already_participant):
            return "skipped"
        
        # Check if session reached the limits: restart if needed
        if self.session_expired():
            logging.info(f"Session expired (after {self.add_count} adds or max runtime). Restarting session...")
            await self.session_break()
            await self.start_new_session()

        try:
            # Try fetching user entity
            user_to_add = None
            if user_data.get('username'):
                try:
                    user_to_add = await self.client.get_entity(user_data['username'])
                except Exception:
                    pass
            if not user_to_add and user_data.get('id'):
                try:
                    user_to_add = await self.client.get_entity(user_data['id'])
                except Exception:
                    pass

            if not user_to_add:
                self.failed_users.add(user_key)
                self.save_json(FAILED_FILE, list(self.failed_users))
                return "fail"

            await self.client(functions.channels.InviteToChannelRequest(
                channel=target_group,
                users=[user_to_add]
            ))

            self.added_users.add(user_key)
            self.save_json(ADDED_FILE, list(self.added_users))
            self.add_count += 1
            return "added"

        except UserAlreadyParticipantError:
            self.already_participant.add(user_key)
            self.save_json(ALREADY_FILE, list(self.already_participant))
            return "already"

        except UserPrivacyRestrictedError:
            self.privacy_failed.add(user_key)
            self.save_json(PRIVACY_FILE, list(self.privacy_failed))
            return "privacy"

        except (PeerFloodError, FloodWaitError) as e:
            if hasattr(e, "seconds") and e.seconds > FLOOD_WAIT_THRESHOLD:
                logging.error(f"Flood wait longer than {FLOOD_WAIT_THRESHOLD}s, stopping session.")
                raise e
            wait_secs = getattr(e, "seconds", 180)
            logging.warning(f"Flood wait detected: sleeping {wait_secs}s, then restarting session.")
            await self.client.disconnect()
            await asyncio.sleep(wait_secs + 20)
            await self.start_new_session()
            return "flood"

        except Exception as e:
            logging.error(f"Failed to add user {user_key}: {e}")
            self.failed_users.add(user_key)
            self.save_json(FAILED_FILE, list(self.failed_users))
            return "fail"

    # === Bulk add members prompt with saved scraped users and group picker ===
    async def bulk_add_members(self):
        try:
            groups = await self.get_my_groups()
            if not groups:
                print("❌ No groups found or no admin rights available.")
                return

            print("\n🚩 Your groups where you have admin rights:")
            for i, group in enumerate(groups, start=1):
                print(f"{i}. {group['title']} (@{group.get('username', 'N/A')})")

            choice = input("\n📌 Select group number to add members: ").strip()
            if not choice.isdigit():
                print("❌ Invalid input")
                return
            idx = int(choice)
            if not (1 <= idx <= len(groups)):
                print("❌ Invalid group number")
                return
            target_group = groups[idx-1]['username']
            if not target_group:
                print("❌ Selected group doesn't have a username, cannot continue.")
                return

            if not self.scraped_users:
                print("❌ No scraped users available. Scrape first.")
                return

            print(f"\n📋 Total scraped users: {len(self.scraped_users)}")
            how_many_input = input("🔢 How many users to add? (0 = all): ").strip()
            try:
                how_many = int(how_many_input) if how_many_input else 0
            except Exception:
                how_many = 0
            if how_many == 0 or how_many > len(self.scraped_users):
                how_many = len(self.scraped_users)

            # Shuffle and filter users not added yet
            candidates = [u for u in self.scraped_users if (u.get('username') or str(u.get('id'))) not in self.added_users]
            random.shuffle(candidates)

            added = privacy = already = skipped = failed = flood = 0

            for user in candidates:
                if added >= how_many:
                    break
                status = await self.add_member_to_group(target_group, user)
                if status == "added":
                    added += 1
                    logging.info(f"Added: @{user.get('username', user.get('id'))}")
                elif status == "privacy":
                    privacy += 1
                    logging.info(f"Privacy block: @{user.get('username', user.get('id'))}")
                elif status == "already":
                    already += 1
                elif status == "skipped":
                    skipped += 1
                elif status == "flood":
                    flood += 1
                    logging.warning("Flood wait detected, stopping bulk adding.")
                    break
                else:
                    failed += 1
                await self.safe_delay()

            print(f"\n✅ Bulk Add Finished:")
            print(f"  Added: {added}")
            print(f"  Privacy blocked: {privacy}")
            print(f"  Already in group: {already}")
            print(f"  Failed: {failed}")
            print(f"  Flood/wait events: {flood}")
            print(f"  Skipped: {skipped}")

        except Exception as e:
            logging.error(f"Error in bulk_add_members: {e}")

    # === List groups admin of ===
    async def get_my_groups(self):
        try:
            dialogs = await self.client.get_dialogs()
            groups = []
            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    if getattr(entity, 'admin_rights', None):
                        groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'username': getattr(entity, 'username', None)
                        })
            return groups
        except Exception as e:
            logging.error(f"Error fetching user groups: {e}")
            return []

    async def start_client(self):
        try:
            await self.start_new_session()
            me = await self.client.get_me()
            logging.info(f"Logged in as {me.username or me.id}")
            return True
        except Exception as e:
            logging.error(f"Could not start client: {e}")
            return False

    # === Menu & run loop ===
    def display_menu(self):
        print("\n" + "="*60)
        print("🚀 ADVANCED TELEGRAM SCRAPER & AUTO-ADDER WITH SESSION RESTART 🚀")
        print("="*60)
        print("\n📊 SCRAPER")
        print("1️⃣  Scrape Channel/Group Members")
        print("2️⃣  View Scraped Users")
        print("3️⃣  Export Scraped Users")
        print("\n👥 ADDERS")
        print("4️⃣  Add Members to Group (Smart)")
        print("\n❌ EXIT")
        print("0️⃣  Exit Program")
        print("="*60)

    async def run(self):
        if not await self.start_client():
            return
        while True:
            self.display_menu()
            choice = input("\n🔢 Choose an option: ").strip()
            try:
                if choice == "1":
                    channel = input("📢 Enter channel/group username (with @): ").strip()
                    if not channel.startswith("@"):
                        print("❌ Username must start with '@'")
                        continue
                    await self.scrape_channel_members(channel)
                elif choice == "2":
                    if self.scraped_users:
                        print(f"\n📋 Total scraped users: {len(self.scraped_users)}")
                        for i, user in enumerate(self.scraped_users[:10], start=1):
                            uname = user.get('username') or "N/A"
                            name = (user.get('first_name') or "") + " " + (user.get('last_name') or "")
                            print(f"{i}. @{uname} - {name.strip()}")
                        if len(self.scraped_users) > 10:
                            print(f"... and {len(self.scraped_users)-10} more.")
                    else:
                        print("❌ No scraped users found.")
                elif choice == "3":
                    if self.scraped_users:
                        fname = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(fname, 'w') as f:
                            json.dump(self.scraped_users, f, indent=2)
                        print(f"✅ Data exported to {fname}")
                    else:
                        print("❌ No data to export.")
                elif choice == "4":
                    await self.bulk_add_members()
                elif choice == "0":
                    print("👋 Exiting program...")
                    await self.client.disconnect()
                    break
                else:
                    print("❌ Invalid choice.")
            except KeyboardInterrupt:
                print("\n⚠️ User cancelled operation, exiting.")
                await self.client.disconnect()
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    scraper = TelegramScraper()
    asyncio.run(scraper.run())
