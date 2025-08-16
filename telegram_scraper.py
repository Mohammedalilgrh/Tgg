import asyncio
import random
import time
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, PeerFloodError,
    UserNotMutualContactError, UserChannelsTooMuchError,
    ChatAdminRequiredError, UserAlreadyParticipantError
)
import logging

# Configure logging
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
        self.api_id = "21706160"
        self.api_hash = "548b91f0e7cd2e44bbee05190620d9f4"
        self.phone = "+96407762476460"
        self.client = TelegramClient('session', self.api_id, self.api_hash)
        self.scraped_users = []
        self.added_users = set()
        self.privacy_failed = set()
        self.failed_users = set()
        self.already_participant = set()
        self.session_start = datetime.now()

        # Anti-ban settings
        self.min_delay = 35
        self.max_delay = 95
        self.session_limit = 500  # Just for safety (per session run)
        self.flood_wait_threshold = 1800  # If flood wait > 30 minutes, abort

    async def start_client(self):
        try:
            await self.client.start(phone=self.phone)
            me = await self.client.get_me()
            logging.info(f"Logged in as {me.username or me.id}")
            return True
        except Exception as e:
            logging.error(f"Failed to start client: {e}")
            return False

    async def safe_delay(self, min_delay=None, max_delay=None):
        d1 = min_delay if min_delay else self.min_delay
        d2 = max_delay if max_delay else self.max_delay
        delay = random.randint(d1, d2)
        logging.info(f"Waiting {delay} seconds for safety...")
        await asyncio.sleep(delay)

    async def scrape_channel_members(self, channel_username):
        try:
            logging.info(f"Starting to scrape: {channel_username}")
            channel = await self.client.get_entity(channel_username)
            members = []
            offset = 0
            limit = 100
            while True:
                try:
                    if offset > 0:
                        await self.safe_delay(10, 25)
                    participants = await self.client(functions.channels.GetParticipantsRequest(
                        channel=channel,
                        filter=types.ChannelParticipantsSearch(''),
                        offset=offset,
                        limit=limit,
                        hash=0
                    ))
                    if not participants.users:
                        break
                    for user in participants.users:
                        if user.bot or user.deleted:
                            continue
                        member_data = {
                            'id': user.id,
                            'username': user.username,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'phone': user.phone,
                            'is_premium': getattr(user, 'premium', False)
                        }
                        members.append(member_data)
                    offset += len(participants.users)
                    logging.info(f"Scraped {len(members)} members so far...")
                    if len(participants.users) < limit:
                        break
                except FloodWaitError as e:
                    logging.warning(f"Flood wait! Sleeping for {e.seconds} seconds.")
                    await asyncio.sleep(e.seconds + 5)
                except Exception as e:
                    logging.error(f"Error scraping: {e}")
                    break
            self.scraped_users = members
            fname = f'scraped_{channel_username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(fname, 'w') as f:
                json.dump(members, f, indent=2)
            logging.info(f"Scraped {len(members)} users. Saved to {fname}.")
            return members
        except Exception as e:
            logging.error(f"Failed to scrape {channel_username}: {e}")
            return []

    async def add_member_to_group(self, target_group, user_data):
        user_key = user_data.get('username') or str(user_data.get('id'))
        if user_key in self.added_users or user_key in self.privacy_failed or user_key in self.already_participant:
            return "skipped"
        try:
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
                return "fail"
            res = await self.client(functions.channels.InviteToChannelRequest(
                channel=target_group,
                users=[user_to_add]
            ))
            self.added_users.add(user_key)
            return "added"
        except UserAlreadyParticipantError:
            self.already_participant.add(user_key)
            return "already"
        except UserPrivacyRestrictedError:
            self.privacy_failed.add(user_key)
            return "privacy"
        except (PeerFloodError, FloodWaitError) as e:
            # Stop the bulk operation if serious ban risk
            if hasattr(e, "seconds") and e.seconds > self.flood_wait_threshold:
                logging.error(f"Flood wait over {self.flood_wait_threshold // 60} min, aborting for safety.")
                raise e
            logging.warning(f"Flood wait detected: sleeping for {getattr(e, 'seconds', 180)} seconds")
            await asyncio.sleep(getattr(e, "seconds", 180) + 10)
            return "flood"
        except Exception as e:
            logging.error(f"Failed to add user {user_key}: {e}")
            self.failed_users.add(user_key)
            return "fail"

    async def bulk_add_members(self, target_group, how_many=None):
        raw_target = target_group
        try:
            target_group = await self.client.get_entity(target_group)
        except Exception as e:
            logging.error(f"Could not resolve target group {raw_target}: {e}")
            print("❌ Could not find target group.")
            return
        # Remove already known-failed or privacy users
        user_list = [u for u in self.scraped_users if (u.get('username') or str(u.get('id'))) not in self.added_users]
        random.shuffle(user_list)
        if not user_list:
            print("❗ No users to add. Did you scrape users?")
            return
        if not how_many:
            how_many = len(user_list)
        added = 0
        privacy = 0
        already = 0
        skipped = 0
        failed = 0
        flood = 0
        for user in user_list:
            if added >= how_many:
                break
            try:
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
                else:
                    failed += 1
                await self.safe_delay()
            except (PeerFloodError, FloodWaitError) as e:
                logging.error("Flood wait or ban risk! Aborting.")
                break
            except KeyboardInterrupt:
                print("\nAborted by user.")
                break
            except Exception as e:
                logging.error(f"Error in bulk add: {e}")
                failed += 1
        print(f"\nBulk Add Finished: {added} added | {privacy} privacy blocked | {already} already in group | {failed} failed | {flood} flood-wait/peerflood | {skipped} skipped.")

    async def run(self):
        if not await self.start_client():
            return
        while True:
            self.display_menu()
            choice = input("\n🔢 Enter your choice: ").strip()
            try:
                if choice == '1':
                    channel = input("📢 Enter channel/group username (with @): ")
                    await self.scrape_channel_members(channel)
                elif choice == '2':
                    if self.scraped_users:
                        print(f"\n📋 Found {len(self.scraped_users)} scraped users.")
                        for i, user in enumerate(self.scraped_users[:10]):
                            print(f"{i+1}. @{user.get('username', 'N/A')} - {user.get('first_name', 'N/A')}")
                        if len(self.scraped_users) > 10:
                            print(f"... and {len(self.scraped_users) - 10} more")
                    else:
                        print("❌ No scraped data found")
                elif choice == '3':
                    if self.scraped_users:
                        fname = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(fname, 'w') as f:
                            json.dump(self.scraped_users, f, indent=2)
                        print(f"✅ Data exported to {fname}")
                    else:
                        print("❌ No data to export")
                elif choice == '4':
                    target = input("🎯 Enter target group username (with @): ")
                    try:
                        how_many = int(input("🔢 How many users to add? (0 = all): ").strip() or "0")
                    except:
                        how_many = 0
                    await self.bulk_add_members(target, how_many if how_many > 0 else None)
                elif choice == '5':
                    target = input("🎯 Enter target group username (with @): ")
                    username = input("👤 Enter username to add (with @): ")
                    user_data = {'username': username}
                    await self.add_member_to_group(target, user_data)
                elif choice == '6':
                    groups = await self.get_my_groups()
                    if groups:
                        print("\n📋 Your Groups:")
                        for group in groups:
                            print(f"• {group['title']} (@{group.get('username', 'N/A')})")
                    else:
                        print("❌ No groups found or no admin rights")
                elif choice == '7':
                    print(f"\n📊 Current session stats:")
                    print(f"Added: {len(self.added_users)}")
                    print(f"Privacy failed: {len(self.privacy_failed)}")
                    print(f"Already in group: {len(self.already_participant)}")
                    print(f"Failed: {len(self.failed_users)}")
                    print(f"Delay: {self.min_delay}-{self.max_delay} sec")
                elif choice == '8':
                    self.added_users.clear()
                    self.privacy_failed.clear()
                    self.failed_users.clear()
                    self.already_participant.clear()
                    print("✅ Counters reset.")
                elif choice == '9':
                    print("\n⚙️  Configure anti-ban settings:")
                    try:
                        self.min_delay = int(input(f"Min delay ({self.min_delay}): ") or self.min_delay)
                        self.max_delay = int(input(f"Max delay ({self.max_delay}): ") or self.max_delay)
                        print("✅ Settings updated")
                    except ValueError:
                        print("❌ Invalid input")
                elif choice == '0':
                    print("👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice")
            except KeyboardInterrupt:
                print("\n⚠️  Operation cancelled by user")
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                print(f"❌ Error: {e}")

    def display_menu(self):
        print("\n" + "="*60)
        print("🚀 ADVANCED TELEGRAM SCRAPER WITH ANTI-BAN PROTECTION 🚀")
        print("="*60)
        print("\n📊 SCRAPER SECTION")
        print("1️⃣  Scrape Channel/Group Members")
        print("2️⃣  View Scraped Data")
        print("3️⃣  Export Scraped Data")
        print("\n👥 ADDER SECTION")
        print("4️⃣  Add Members to Group (Smart Mode)")
        print("5️⃣  Add Single Member")
        print("6️⃣  View My Groups")
        print("\n🛠️  TOOLS SECTION")
        print("7️⃣  View Current Stats")
        print("8️⃣  Reset Counters")
        print("9️⃣  Configure Anti-Ban Settings")
        print("\n❌ EXIT")
        print("0️⃣  Exit Program")
        print("="*60)

    async def get_my_groups(self):
        try:
            dialogs = await self.client.get_dialogs()
            my_groups = []
            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    if hasattr(entity, 'admin_rights') and entity.admin_rights:
                        my_groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'username': getattr(entity, 'username', None)
                        })
            return my_groups
        except Exception as e:
            logging.error(f"Error getting groups: {e}")
            return []

if __name__ == "__main__":
    scraper = TelegramScraper()
    asyncio.run(scraper.run())
