#!/usr/bin/env python3
"""Debug script to see raw Xert API response."""
import asyncio
import os
import sys

# Need to set encryption key for decrypting credentials
os.environ.setdefault("TRAININGDASH_ENCRYPTION_KEY", "D1prO+2rx2zmauRYJc8yKA2rbW0ABdAo5uf8ZJMoXSQ=")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://trainingdash:trainingdash@db:5432/trainingdash")

async def main():
    from sqlalchemy import select
    from trainingdash.db import async_session
    from trainingdash.models import XertCredentials
    from trainingdash.crypto import decrypt
    import httpx
    
    async with async_session() as db:
        result = await db.execute(select(XertCredentials).where(XertCredentials.user_id == 1))
        creds = result.scalar_one_or_none()
        if not creds:
            print("No Xert credentials found")
            return
        
        xert_password = decrypt(creds.encrypted_password)
        print(f"Email: {creds.xert_email}")
        
        # Try web login instead of OAuth to get session cookies
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # First get the home/login page to get CSRF token
            home_page = await client.get("https://www.xertonline.com/")
            print(f"Home page status: {home_page.status_code}")
            
            # Extract CSRF token from cookies
            csrf_token = None
            for cookie in client.cookies.jar:
                if cookie.name == "XSRF-TOKEN":
                    import urllib.parse
                    csrf_token = urllib.parse.unquote(cookie.value)
                    break
            
            print(f"CSRF token found: {csrf_token is not None}")
            
            if not csrf_token:
                # Try to find it in the HTML
                import re
                match = re.search(r'<meta name="csrf-token" content="([^"]+)"', home_page.text)
                if match:
                    csrf_token = match.group(1)
                    print(f"CSRF from HTML: {csrf_token[:30]}...")
            
            # Try to login via the web form
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.xertonline.com/",
                "Origin": "https://www.xertonline.com",
            }
            if csrf_token:
                headers["X-XSRF-TOKEN"] = csrf_token
            
            login_response = await client.post(
                "https://www.xertonline.com/login",
                data={
                    "email": creds.xert_email,
                    "password": xert_password,
                    "_token": csrf_token or "",
                },
                headers=headers
            )
            print(f"Login response status: {login_response.status_code}")
            print(f"Login response URL: {login_response.url}")
            
            # Check if we're logged in
            is_logged_in = "logout" in login_response.text.lower() or "dashboard" in str(login_response.url).lower()
            print(f"Logged in: {is_logged_in}")
            
            if is_logged_in:
                # Try to download FIT file
                activity_id = "s8pehgletoecmk5x"
                download_response = await client.get(
                    f"https://www.xertonline.com/activities/download/{activity_id}",
                    follow_redirects=True,
                )
                print(f"\nDownload status: {download_response.status_code}")
                print(f"Download content-type: {download_response.headers.get('content-type')}")
                print(f"Download content-disposition: {download_response.headers.get('content-disposition')}")
                print(f"Download size: {len(download_response.content)} bytes")
                
                content_type = download_response.headers.get('content-type', '')
                if 'octet' in content_type or 'fit' in content_type or \
                   'fit' in download_response.headers.get('content-disposition', '').lower():
                    print("SUCCESS! Got FIT file!")
                    # Check FIT file header
                    content = download_response.content
                    print(f"First 20 bytes: {content[:20]}")
                    if len(content) > 12 and content[8:12] == b'.FIT':
                        print("Valid FIT file header detected!")
                else:
                    print(f"Content preview: {download_response.text[:300]}")
            else:
                print("Login failed - checking response...")
                print(f"Response snippet: {login_response.text[:500]}")

if __name__ == "__main__":
    asyncio.run(main())
