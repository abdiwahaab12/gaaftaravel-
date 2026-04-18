#!/usr/bin/env python3
"""
Wanaag Travel & Logistics - Deployment Script
This script helps you deploy your application to various hosting platforms.
"""

import os
import subprocess
import sys

def check_requirements():
    """Check if all required files exist"""
    required_files = [
        'App.py',
        'requirements.txt',
        'Procfile',
        'runtime.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return False
    
    print("✅ All required files found!")
    return True

def setup_git():
    """Initialize git repository if not already done"""
    if not os.path.exists('.git'):
        print("🔧 Initializing Git repository...")
        subprocess.run(['git', 'init'], check=True)
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        print("✅ Git repository initialized!")
    else:
        print("✅ Git repository already exists!")

def deploy_heroku():
    """Deploy to Heroku"""
    print("🚀 Deploying to Heroku...")
    
    # Check if Heroku CLI is installed
    try:
        subprocess.run(['heroku', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Heroku CLI not found. Please install it from https://devcenter.heroku.com/articles/heroku-cli")
        return False
    
    # Login to Heroku
    print("🔐 Please login to Heroku...")
    subprocess.run(['heroku', 'login'], check=True)
    
    # Create app
    app_name = input("Enter your Heroku app name (or press Enter for auto-generated): ").strip()
    if app_name:
        subprocess.run(['heroku', 'create', app_name], check=True)
    else:
        subprocess.run(['heroku', 'create'], check=True)
    
    # Set environment variables
    print("🔧 Setting up environment variables...")
    print("Please enter your database and JWT configuration:")
    
    db_host = input("Database Host (default: localhost): ").strip() or "localhost"
    db_user = input("Database User (default: root): ").strip() or "root"
    db_password = input("Database Password: ").strip()
    db_name = input("Database Name (default: wanaagtravel_db): ").strip() or "wanaagtravel_db"
    jwt_secret = input("JWT Secret Key (press Enter for auto-generated): ").strip()
    
    if not jwt_secret:
        import secrets
        jwt_secret = secrets.token_urlsafe(32)
        print(f"Generated JWT Secret: {jwt_secret}")
    
    # Set config vars
    subprocess.run(['heroku', 'config:set', f'DB_HOST={db_host}'], check=True)
    subprocess.run(['heroku', 'config:set', f'DB_USER={db_user}'], check=True)
    subprocess.run(['heroku', 'config:set', f'DB_PASSWORD={db_password}'], check=True)
    subprocess.run(['heroku', 'config:set', f'DB_NAME={db_name}'], check=True)
    subprocess.run(['heroku', 'config:set', f'JWT_SECRET_KEY={jwt_secret}'], check=True)
    subprocess.run(['heroku', 'config:set', 'FLASK_ENV=production'], check=True)
    
    # Deploy
    print("🚀 Deploying to Heroku...")
    subprocess.run(['git', 'add', '.'], check=True)
    subprocess.run(['git', 'commit', '-m', 'Deploy to Heroku'], check=True)
    subprocess.run(['git', 'push', 'heroku', 'main'], check=True)
    
    print("✅ Deployment completed!")
    print("🌐 Your app is now live on Heroku!")
    return True

def main():
    """Main deployment function"""
    print("🌟 Wanaag Travel & Logistics - Deployment Script")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Setup git
    setup_git()
    
    # Choose deployment platform
    print("\n🚀 Choose your deployment platform:")
    print("1. Heroku (Recommended for beginners)")
    print("2. Railway")
    print("3. Render")
    print("4. PythonAnywhere")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == '1':
        deploy_heroku()
    elif choice == '2':
        print("📖 Please follow the Railway deployment guide in DEPLOYMENT_GUIDE.md")
    elif choice == '3':
        print("📖 Please follow the Render deployment guide in DEPLOYMENT_GUIDE.md")
    elif choice == '4':
        print("📖 Please follow the PythonAnywhere deployment guide in DEPLOYMENT_GUIDE.md")
    elif choice == '5':
        print("👋 Goodbye!")
        sys.exit(0)
    else:
        print("❌ Invalid choice!")
        sys.exit(1)

if __name__ == '__main__':
    main()
