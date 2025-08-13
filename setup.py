def setup_credentials():
    print("🚀 TELEGRAM SCRAPER SETUP")
    print("=" * 40)
    print("\n📱 First, get your API credentials from https://my.telegram.org")
    print("1. Log in with your phone number")
    print("2. Go to 'API development tools'")
    print("3. Create a new application")
    print("4. Copy your api_id and api_hash")
    
    print("\n⚙️  Enter your credentials:")
    
    api_id = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()
    phone = input("Phone Number (with country code, e.g., +1234567890): ").strip()
    
    # Update the main file
    with open('telegram_scraper.py', 'r') as f:
        content = f.read()
    
    content = content.replace('YOUR_API_ID', api_id)
    content = content.replace('YOUR_API_HASH', f'"{api_hash}"')
    content = content.replace('YOUR_PHONE_NUMBER', f'"{phone}"')
    
    with open('telegram_scraper.py', 'w') as f:
        f.write(content)
    
    print("\n✅ Setup complete!")
    print("💡 Tips for safe usage:")
    print("• Start with small limits (5-10 adds per day)")
    print("• Use long delays between actions (60+ seconds)")
    print("• Don't scrape/add from the same IP repeatedly")
    print("• Take breaks between sessions")
    print("\n🚀 Run: python telegram_scraper.py")

if __name__ == "__main__":
    setup_credentials()
