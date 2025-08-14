import asyncio
import random
import time
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types
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
        # Replace these with your values
        self.api_id = "21706160"  # Get from my.telegram.org
        self.api_hash = "548b91f0e7cd2e44bbee05190620d9f4"  # Get from my.telegram.org
        self.phone = "+96407762476460"  # Your phone number
        
        self.client = TelegramClient('session', self.api_id, self.api_hash)
        self.scraped_users = []
        self.failed_users = []
        
        # Anti-ban settings
        self.min_delay = 30  # Minimum delay between actions (seconds)
        self.max_delay = 120  # Maximum delay between actions (seconds)
        self.daily_limit = 50  # Max adds per day
        self.hourly_limit = 10  # Max adds per hour
        self.session_limit = 5  # Max adds per session
        
        # Tracking
        self.daily_count = 0
        self.hourly_count = 0
        self.session_count = 0
        self.last_reset = datetime.now()
        
    async def start_client(self):
        """Initialize and start the Telegram client"""
        try:
            await self.client.start(phone=self.phone)
            me = await self.client.get_me()
            logging.info(f"Successfully logged in as {me.username}")
            return True
        except Exception as e:
            logging.error(f"Failed to start client: {e}")
            return False
    
    def reset_counters(self):
        """Reset hourly/daily counters when needed"""
        now = datetime.now()
        if now - self.last_reset > timedelta(hours=1):
            self.hourly_count = 0
        if now - self.last_reset > timedelta(days=1):
            self.daily_count = 0
            self.hourly_count = 0
        self.last_reset = now
    
    def check_limits(self):
        """Check if we've hit our safety limits"""
        self.reset_counters()
        return (self.daily_count < self.daily_limit and 
                self.hourly_count < self.hourly_limit and 
                self.session_count < self.session_limit)
    
    async def safe_delay(self, custom_delay=None):
        """Implement random delays to avoid detection"""
        if custom_delay:
            delay = custom_delay
        else:
            delay = random.randint(self.min_delay, self.max_delay)
        
        logging.info(f"Waiting {delay} seconds for safety...")
        await asyncio.sleep(delay)
    
    async def scrape_channel_members(self, channel_username):
        """Scrape members from a channel with protection"""
        try:
            logging.info(f"Starting to scrape: {channel_username}")
            channel = await self.client.get_entity(channel_username)
            
            # Check if it's a channel or group
            if hasattr(channel, 'megagroup') and channel.megagroup:
                logging.info("Target is a supergroup")
            elif hasattr(channel, 'broadcast') and channel.broadcast:
                logging.info("Target is a broadcast channel")
            
            members = []
            offset = 0
            limit = 100  # Small batches to avoid suspicion
            
            while True:
                try:
                    # Add delay between requests
                    if offset > 0:
                        await self.safe_delay(random.randint(10, 30))
                    
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
                    
                    # Break if we get less than limit (end of list)
                    if len(participants.users) < limit:
                        break
                        
                except FloodWaitError as e:
                    logging.warning(f"Hit flood wait, sleeping for {e.seconds} seconds")
                    await asyncio.sleep(e.seconds + 10)
                    continue
                except Exception as e:
                    logging.error(f"Error scraping: {e}")
                    break
            
            # Save scraped data
            self.scraped_users = members
            with open(f'scraped_{channel_username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
                json.dump(members, f, indent=2)
            
            logging.info(f"Successfully scraped {len(members)} members from {channel_username}")
            return members
            
        except Exception as e:
            logging.error(f"Failed to scrape {channel_username}: {e}")
            return []
    
    async def add_member_to_group(self, target_group, user_data):
        """Add a single member with maximum protection"""
        try:
            # Check safety limits
            if not self.check_limits():
                logging.warning("Hit daily/hourly limits, stopping adds")
                return False
            
            target = await self.client.get_entity(target_group)
            
            # Try different methods to add user
            user_to_add = None
            
            # Method 1: Try by username
            if user_data.get('username'):
                try:
                    user_to_add = await self.client.get_entity(user_data['username'])
                except:
                    pass
            
            # Method 2: Try by user ID
            if not user_to_add and user_data.get('id'):
                try:
                    user_to_add = await self.client.get_entity(user_data['id'])
                except:
                    pass
            
            if not user_to_add:
                logging.warning(f"Could not resolve user: {user_data}")
                return False
            
            # Add the user
            await self.client(functions.channels.InviteToChannelRequest(
                channel=target,
                users=[user_to_add]
            ))
            
            # Update counters
            self.daily_count += 1
            self.hourly_count += 1
            self.session_count += 1
            
            logging.info(f"Successfully added {user_data.get('username', user_data.get('id'))}")
            return True
            
        except UserAlreadyParticipantError:
            logging.info(f"User {user_data.get('username', user_data.get('id'))} already in group")
            return True
        except UserPrivacyRestrictedError:
            logging.warning(f"User {user_data.get('username', user_data.get('id'))} has privacy restrictions")
            return False
        except PeerFloodError:
            logging.error("Account limited due to flood. Stopping for safety.")
            return False
        except FloodWaitError as e:
            logging.warning(f"Flood wait: {e.seconds} seconds")
            await asyncio.sleep(e.seconds + 10)
            return False
        except Exception as e:
            logging.error(f"Failed to add user {user_data}: {e}")
            return False
    
    async def bulk_add_members(self, target_group, user_list=None):
        """Add multiple members with protection"""
        if not user_list:
            user_list = self.scraped_users
        
        if not user_list:
            logging.error("No users to add")
            return
        
        successful_adds = 0
        failed_adds = 0
        
        # Randomize order to appear more natural
        random.shuffle(user_list)
        
        for user_data in user_list:
            if not self.check_limits():
                logging.info("Hit safety limits, stopping bulk add")
                break
            
            success = await self.add_member_to_group(target_group, user_data)
            
            if success:
                successful_adds += 1
            else:
                failed_adds += 1
            
            # Random delay between adds
            await self.safe_delay()
        
        logging.info(f"Bulk add complete: {successful_adds} successful, {failed_adds} failed")
    
    async def get_my_groups(self):
        """Get list of groups where user is admin"""
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
    
    def display_menu(self):
        """Display the main menu"""
        print("\n" + "="*60)
        print("🚀 ADVANCED TELEGRAM SCRAPER WITH ANTI-BAN PROTECTION 🚀")
        print("="*60)
        print("\n📊 SCRAPER SECTION")
        print("1️⃣  Scrape Channel/Group Members")
        print("2️⃣  View Scraped Data")
        print("3️⃣  Export Scraped Data")
        
        print("\n👥 ADDER SECTION")
        print("4️⃣  Add Members to Group (Safe Mode)")
        print("5️⃣  Add Single Member")
        print("6️⃣  View My Groups")
        
        print("\n🛠️  TOOLS SECTION")
        print("7️⃣  View Current Limits")
        print("8️⃣  Reset Counters")
        print("9️⃣  Configure Anti-Ban Settings")
        
        print("\n📈 STATISTICS")
        print(f"Daily Adds: {self.daily_count}/{self.daily_limit}")
        print(f"Hourly Adds: {self.hourly_count}/{self.hourly_limit}")
        print(f"Session Adds: {self.session_count}/{self.session_limit}")
        
        print("\n❌ EXIT")
        print("0️⃣  Exit Program")
        print("="*60)
    
    async def run(self):
        """Main program loop"""
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
                        print(f"\n📋 Found {len(self.scraped_users)} scraped users")
                        for i, user in enumerate(self.scraped_users[:10]):
                            print(f"{i+1}. @{user.get('username', 'N/A')} - {user.get('first_name', 'N/A')}")
                        if len(self.scraped_users) > 10:
                            print(f"... and {len(self.scraped_users) - 10} more")
                    else:
                        print("❌ No scraped data found")
                
                elif choice == '3':
                    if self.scraped_users:
                        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(filename, 'w') as f:
                            json.dump(self.scraped_users, f, indent=2)
                        print(f"✅ Data exported to {filename}")
                    else:
                        print("❌ No data to export")
                
                elif choice == '4':
                    target = input("🎯 Enter target group username (with @): ")
                    await self.bulk_add_members(target)
                
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
                    print(f"\n📊 Current Limits:")
                    print(f"Daily: {self.daily_count}/{self.daily_limit}")
                    print(f"Hourly: {self.hourly_count}/{self.hourly_limit}")
                    print(f"Session: {self.session_count}/{self.session_limit}")
                    print(f"Delay Range: {self.min_delay}-{self.max_delay} seconds")
                
                elif choice == '8':
                    self.daily_count = 0
                    self.hourly_count = 0
                    self.session_count = 0
                    print("✅ Counters reset")
                
                elif choice == '9':
                    print("\n⚙️  Configure Anti-Ban Settings:")
                    try:
                        self.daily_limit = int(input(f"Daily limit ({self.daily_limit}): ") or self.daily_limit)
                        self.hourly_limit = int(input(f"Hourly limit ({self.hourly_limit}): ") or self.hourly_limit)
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
                print("\n⚠️  Operation cancelled")
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    scraper = TelegramScraper()
    asyncio.run(scraper.run())
