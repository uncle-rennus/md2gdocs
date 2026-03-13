#!/usr/bin/env python3
"""Debug script to test the md2gdocs functionality step by step."""

import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test if environment variables are loaded correctly."""
    print("=== Testing Environment Variables ===")
    load_dotenv('.env', override=False)
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    template_id = os.getenv('TEMPLATE_DOC_ID')
    
    print(f"Client ID: {'Found' if client_id else 'MISSING'}")
    print(f"Client Secret: {'Found' if client_secret else 'MISSING'}")
    print(f"Template ID: {'Found' if template_id else 'MISSING'}")
    
    if not client_id or not client_secret:
        print("\n❌ ERROR: Missing required credentials in .env file")
        return False
    
    print("✅ Environment variables loaded successfully")
    return True

def test_markdown_parsing():
    """Test markdown parsing functionality."""
    print("\n=== Testing Markdown Parsing ===")
    
    try:
        from md2gdocs import parse_markdown
        
        test_md = """# Test Heading

This is **bold** and *italic* text.

```code example```"""
        
        plain_text, styles = parse_markdown(test_md)
        print(f"Parsed text length: {len(plain_text)}")
        print(f"Found {len(styles)} style actions")
        print("✅ Markdown parsing works")
        return True
        
    except Exception as e:
        print(f"❌ ERROR in markdown parsing: {e}")
        return False

def test_google_auth():
    """Test Google authentication."""
    print("\n=== Testing Google Authentication ===")
    
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        
        # Check if token exists
        if os.path.exists('token.json'):
            print("Found existing token.json")
            try:
                creds = Credentials.from_authorized_user_file('token.json', [
                    'https://www.googleapis.com/auth/documents',
                    'https://www.googleapis.com/auth/drive'
                ])
                if creds and creds.valid:
                    print("✅ Valid credentials found in token.json")
                    return True
                else:
                    print("Token expired or invalid")
            except Exception as e:
                print(f"Error loading token: {e}")
        
        print("No valid token found - would need browser authentication")
        print("This is expected for first run")
        return True
        
    except Exception as e:
        print(f"❌ ERROR in Google auth: {e}")
        return False

def main():
    """Run all tests."""
    print("Starting md2gdocs debug tests...\n")
    
    results = []
    results.append(test_environment())
    results.append(test_markdown_parsing())
    results.append(test_google_auth())
    
    print(f"\n=== Summary ===")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("✅ All basic tests passed!")
        print("\nNext steps:")
        print("1. If this is your first run, the script will open a browser for authentication")
        print("2. Make sure you have enabled Google Docs API in your Google Cloud project")
        print("3. For templates, also enable Google Drive API")
        print("4. Run: python md2gdocs.py README.md")
    else:
        print("❌ Some tests failed - check the errors above")

if __name__ == '__main__':
    main()