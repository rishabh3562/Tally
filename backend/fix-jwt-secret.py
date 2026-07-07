#!/usr/bin/env python3
"""
JWT Secret Helper Script

This script helps you:
1. Get the correct JWT secret from Supabase
2. Update your backend/.env file
3. Verify the JWT secret is correct
"""

import os
import sys
import re
from pathlib import Path


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(num, text):
    """Print a numbered step"""
    print(f"📍 Step {num}: {text}")
    print("-" * 60)


def get_jwt_from_env():
    """Get current JWT secret from .env"""
    env_file = Path(__file__).parent / ".env"

    if not env_file.exists():
        return None

    with open(env_file, 'r') as f:
        content = f.read()
        match = re.search(r'SUPABASE_JWT_SECRET=(.+)', content)
        if match:
            return match.group(1).strip()

    return None


def update_jwt_secret(new_secret):
    """Update the JWT secret in .env file"""
    env_file = Path(__file__).parent / ".env"

    if not env_file.exists():
        print("❌ Error: backend/.env not found!")
        return False

    with open(env_file, 'r') as f:
        content = f.read()

    # Replace or add the JWT secret
    if 'SUPABASE_JWT_SECRET=' in content:
        # Replace existing
        new_content = re.sub(
            r'SUPABASE_JWT_SECRET=.+',
            f'SUPABASE_JWT_SECRET={new_secret}',
            content
        )
    else:
        # Add new (after other Supabase config)
        new_content = re.sub(
            r'(SUPABASE_JWT_SECRET.*?\n)',
            f'SUPABASE_JWT_SECRET={new_secret}\n',
            content,
            flags=re.DOTALL
        )

    with open(env_file, 'w') as f:
        f.write(new_content)

    return True


def main():
    """Main function"""
    print_header("🔐 Supabase JWT Secret Helper")

    print("""
This script will help you fix your JWT secret authentication issue.

The error you're seeing:
  ❌ AUTH: JWT validation failed: The specified alg value is not allowed

This means your SUPABASE_JWT_SECRET in backend/.env is incorrect.
    """)

    print_step(1, "Get the JWT Secret from Supabase (takes 2 minutes)")
    print("""
Follow these steps in your browser:

1. Go to: https://app.supabase.com
2. Log in with your credentials
3. Select your PROJECT (where rishabhdubey2003@gmail.com is registered)
4. Click ⚙️  Settings (bottom left)
5. Click "Auth" in left sidebar
6. Scroll down to "JWT Settings" section
7. Find the "JWT Secret" field
8. COPY the entire value (it's a long string starting with something like: eyJ...)

    """)

    current_secret = get_jwt_from_env()
    if current_secret:
        print(f"Current JWT Secret in .env:")
        print(f"  {current_secret[:50]}...")
        print()

    jwt_secret = input("🔑 Paste the JWT Secret from Supabase here: ").strip()

    if not jwt_secret:
        print("❌ No secret provided. Exiting.")
        return False

    if len(jwt_secret) < 50:
        print("⚠️  Warning: JWT secret seems too short (should be 100+ chars)")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            return False

    print_step(2, "Updating backend/.env")

    if update_jwt_secret(jwt_secret):
        print("✅ Updated SUPABASE_JWT_SECRET in backend/.env")
        print("\nNew JWT Secret in .env:")
        print(f"  {jwt_secret[:50]}...")
    else:
        print("❌ Failed to update backend/.env")
        return False

    print_step(3, "Next Steps")
    print("""
1. 🔄 RESTART YOUR BACKEND:
   - Stop the running backend (Ctrl+C)
   - Run: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

2. 🧹 CLEAR BROWSER CACHE:
   - Press Ctrl+Shift+R (hard refresh)
   - OR use Incognito mode
   - OR F12 → Settings → "Disable cache (while DevTools open)"

3. 🧪 TEST LOGIN:
   - Go to: http://localhost:3000/auth/login
   - Login with: dubeyrishabh108@gmail.com / password

4. ✅ VERIFY IN BACKEND LOGS:
   - Should see: ✅ AUTH: Token valid for user...
   - Should NOT see: ❌ JWT validation failed

    """)

    print_step(4, "Verify Success")
    print("""
Check your backend terminal for these GOOD signs:
  ✅ AUTH: Validating token with JWT secret...
  ✅ AUTH: Token valid for user rishabhdubey2003@gmail.com
  GET /api/users/me HTTP/1.1" 200 OK

If you see these BAD signs, the secret is still wrong:
  ❌ AUTH: JWT validation failed: The specified alg value is not allowed
  GET /api/users/me HTTP/1.1" 401 Unauthorized

    """)

    print_header("✨ All Done!")
    print("""
Your JWT secret has been updated. Now restart your backend and test login!

If you still get 401 errors:
1. Double-check you copied the EXACT value from Supabase (no extra spaces)
2. Make sure you restarted the backend
3. Clear your browser cache completely
    """)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
