import asyncio
import random
import json
import os
import logging
from datetime import datetime
from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, PeerFloodError,
    UserAlreadyParticipantError
)

# === CONFIGURATION ===
API_ID = 21706160  # Your Telegram API ID
API_HASH = "548b91f0e7cd2e44bbee05190620d9f4"  # Your Telegram API Hash
PHONE = "+96407762476460"  # Your phone number with country code

# === DATA PATHS ===
DATA_PATH = "data"
SCRAPED_FILE = os.path.join(DATA_PATH, "scraped_users.json")
ADDED_FILE = os.path.join(DATA_PATH, "added_users.json")
PRIVACY_FILE = os.path.join(DATA_PATH, "privacy_failed.json")
FAILED_FILE = os.path.join(DATA_PATH, "failed_users.json")
ALREADY_FILE = os.path.join(DATA_PATH, "already_participant.json")

# === ANTI-BAN SETTINGS ===
MIN_DELAY = 60                # minimum delay between adds (sec)
MAX_DELAY = 120               # maximum delay between adds (sec)
MAX_ADDS_PER_SESSION = 5      # max members to add per Telegram session
FLOOD_WAIT_THRESHOLD = 1800   # abort if flood wait longer than this (sec)
SESSION_BREAK_MIN = 3 * 3600  # 3 hours break minimum between sessions (sec)
SESSION_BREAK_MAX = 7 * 3600  # 7 hours break maximum between sessions (sec)

# === LOGGING CONFIGURATION ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('telegram_bot.log'), logging.StreamHandler()]
)

class TelegramScraper:
    def __init__(self):
        self.api_id = API_ID
        self.api_hash = API_HASH
        self.phone = PHONE
        self.client = None

        os.makedirs(DATA_PATH, exist_ok=True)

        # Load or initialize persistent data
        self.scraped_users = self.load_json(SCRAPED_FILE) or []
        self.added_users = set(self.load_json(ADDED_FILE) or [])
        self.privacy_failed = set(self.load_json(PRIVACY_FILE) or [])
        self.failed_users = set(self.load_json(FAILED_FILE) or [])
        self.already_participant = set(self.load_json(ALREADY_FILE) or [])

        self.add_count = 0
        self.session_start_time = None

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

    async def start_new_session(self):
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logging.info("Disconnected previous Telegram session.")
        self.client = TelegramClient('session', self.api_id, self.api_hash)
        await self.client.start(phone=self.phone)
        self.add_count = 0
        self.session_start_time = asyncio.get_event_loop().time()
        logging.info("Started new Telegram client session.")

    def session_expired(self):
        return self.add_count >= MAX_ADDS_PER_SESSION

    async def session_break(self):
        duration = random.randint(SESSION_BREAK_MIN, SESSION_BREAK_MAX)
        logging.info(f"Taking session break for {duration // 3600}h {(duration % 3600) // 60}m...")
        await asyncio.sleep(duration)
        logging.info("Session break ended.")

    async def safe_delay(self):
        delay = random.randint(MIN_DELAY, MAX_DELAY)
        logging.info(f"Waiting {delay} seconds to mimic human behavior...")
        await asyncio.sleep(delay)

    async def scrape_channel_members(self, channel_username):
        try:
            logging.info(f"Scraping members from {channel_username}")
            channel = await self.client.get_entity(channel_username)
            offset = 0
            limit = 100
            total_new = 0
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
                new_this_batch = 0
                for user in participants.users:
                    if user.bot or user.deleted:
                        continue
                    if any(u['id'] == user.id for u in self.scraped_users):
                        continue
                    member_data = {
                        'id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'phone': user.phone,
                        'is_premium': getattr(user, 'premium', False)
                    }
                    self.scraped_users.append(member_data)
                    new_this_batch += 1
                offset += len(participants.users)
                total_new += new_this_batch
                logging.info(f"Scraped total {len(self.scraped_users)} users (+{new_this_batch} new this batch)")
                if len(participants.users) < limit:
                    break
            self.save_json(SCRAPED_FILE, self.scraped_users)
            logging.info(f"Finished scraping. Total saved users: {len(self.scraped_users)}")
            return total_new
        except FloodWaitError as e:
            logging.warning(f"Flood wait during scrape for {e.seconds} seconds")
            await asyncio.sleep(e.seconds + 10)
        except Exception as e:
            logging.error(f"Error while scraping: {e}")
        return 0

    async def add_member_to_group(self, target_group, user_data):
        user_key = user_data.get('username') or str(user_data.get('id'))
        if (user_key in self.added_users or
                user_key in self.privacy_failed or
                user_key in self.already_participant):
            return "skipped"

        if self.session_expired():
            logging.info("Session add limit reached. Taking break & restarting session.")
            await self.session_break()
            await self.start_new_session()

        try:
            user_entity = None
            if user_data.get('username'):
                try:
                    user_entity = await self.client.get_entity(user_data['username'])
                except Exception:
                    pass
            if not user_entity and user_data.get('id'):
                try:
                    user_entity = await self.client.get_entity(user_data['id'])
                except Exception:
                    pass
            if not user_entity:
                self.failed_users.add(user_key)
                self.save_json(FAILED_FILE, list(self.failed_users))
                return "fail"

            await self.client(functions.channels.InviteToChannelRequest(
                channel=target_group,
                users=[user_entity]
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
            if hasattr(e, 'seconds') and e.seconds > FLOOD_WAIT_THRESHOLD:
                logging.error(f"Flood wait > {FLOOD_WAIT_THRESHOLD}s, aborting session.")
                raise e
            wait = getattr(e, 'seconds', 180)
            logging.warning(f"Flood wait detected ({wait}s). Disconnecting and restarting session.")
            await self.client.disconnect()
            await asyncio.sleep(wait + 20)
            await self.start_new_session()
            return "flood"
        except Exception as e:
            logging.error(f"Adding user failed: {e}")
            self.failed_users.add(user_key)
            self.save_json(FAILED_FILE, list(self.failed_users))
            return "fail"

    async def bulk_add_members(self):
        try:
            groups = await self.get_my_groups()
            if not groups:
                print("❌ No admin groups found.")
                return

            print("\n🚩 Your Admin Groups:")
            for i, group in enumerate(groups, start=1):
                print(f"{i}. {group['title']} (@{group.get('username', 'N/A')})")

            group_index = input("\nSelect group number to add members: ").strip()
            if not group_index.isdigit() or not (1 <= int(group_index) <= len(groups)):
                print("❌ Invalid group selection.")
                return
            target_group = groups[int(group_index) - 1]['username']
            if not target_group:
                print("❌ Selected group has no username.")
                return

            if not self.scraped_users:
                print("❌ No scraped users found. Scrape first!")
                return

            print(f"\nTotal scraped users: {len(self.scraped_users)}")
            how_many_input = input("How many members to add? (0 = all): ").strip()
            try:
                how_many = int(how_many_input) if how_many_input else 0
            except Exception:
                how_many = 0
            how_many = len(self.scraped_users) if how_many == 0 or how_many > len(self.scraped_users) else how_many

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
                    logging.info(f"Privacy blocked: @{user.get('username', user.get('id'))}")
                elif status == "already":
                    already += 1
                elif status == "skipped":
                    skipped += 1
                elif status == "flood":
                    flood += 1
                    logging.warning("Flood detected - stopping bulk add.")
                    break
                else:
                    failed += 1
                await self.safe_delay()

            print(f"\n✅ Bulk Add Completed:")
            print(f"  Added: {added} | Privacy blocked: {privacy} | Already in group: {already}")
            print(f"  Failed: {failed} | Flood events: {flood} | Skipped: {skipped}")

        except Exception as e:
            logging.error(f"Error in bulk add members: {e}")

    async def get_my_groups(self):
        try:
            dialogs = await self.client.get_dialogs()
            groups = []
            for d in dialogs:
                if d.is_group or d.is_channel:
                    entity = d.entity
                    if getattr(entity, 'admin_rights', None):
                        groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'username': getattr(entity, 'username', None)
                        })
            return groups
        except Exception as e:
            logging.error(f"Error getting groups: {e}")
            return []

    async def start_client(self):
        try:
            await self.start_new_session()
            me = await self.client.get_me()
            logging.info(f"Logged in as {me.username or me.id}")
            return True
        except Exception as e:
            logging.error(f"Failed to start Telegram client: {e}")
            return False

    def display_menu(self):
        print("\n" + "="*60)
        print("🚀 TELEGRAM SCRAPER & SAFE AUTO-ADDER SCRIPT 🚀")
        print("="*60)
        print("\n📊 SCRAPE")
        print("1️⃣  Scrape Channel/Group Members")
        print("2️⃣  View Scraped Users")
        print("3️⃣  Export Scraped Users")
        print("\n👥 ADD")
        print("4️⃣  Add Members to Group")
        print("\n❌ Exit")
        print("0️⃣  Exit Program")
        print("="*60)

    async def run(self):
        if not await self.start_client():
            return
        while True:
            self.display_menu()
            choice = input("\nChoose option: ").strip()
            try:
                if choice == "1":
                    username = input("Enter channel/group username (with '@'): ").strip()
                    if username.startswith("@"):
                        count = await self.scrape_channel_members(username)
                        print(f"Scraped {count} new members from {username}")
                    else:
                        print("❌ Username must start with '@'")
                elif choice == "2":
                    if self.scraped_users:
                        print(f"\nTotal scraped users: {len(self.scraped_users)}")
                        for i, user in enumerate(self.scraped_users[:10], start=1):
                            uname = user.get('username') or "N/A"
                            name = (user.get('first_name') or "") + " " + (user.get('last_name') or "")
                            print(f"{i}. @{uname} - {name.strip()}")
                        if len(self.scraped_users) > 10:
                            print(f"... and {len(self.scraped_users) - 10} more")
                    else:
                        print("❌ No scraped users yet.")
                elif choice == "3":
                    if self.scraped_users:
                        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(filename, 'w') as f:
                            json.dump(self.scraped_users, f, indent=2)
                        print(f"Saved scraped users to {filename}")
                    else:
                        print("❌ No data to export.")
                elif choice == "4":
                    await self.bulk_add_members()
                elif choice == "0":
                    print("Exiting... Goodbye!")
                    if self.client and self.client.is_connected():
                        await self.client.disconnect()
                    break
                else:
                    print("❌ Invalid option.")
            except KeyboardInterrupt:
                print("\nInterrupted by user. Exiting...")
                if self.client and self.client.is_connected():
                    await self.client.disconnect()
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    scraper = TelegramScraper()
    asyncio.run(scraper.run())
