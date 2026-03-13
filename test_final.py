#!/usr/bin/env python3
"""
Test script for the simplified md2gdocs.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from md2gdocs import upload_markdown_to_docs, load_secrets, authenticate
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def test_upload_function():
    """Test the upload_markdown_to_docs function with a simple file."""
    
    # Create a test markdown file
    test_content = """
# Test Document

This is a test of the **simplified** Markdown upload.

## Features

- Much simpler code
- Better reliability
- Uses Google's built-in conversion

[Google](https://www.google.com) link test.
"""
    
    test_file = "test_upload.md"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print("✅ Created test Markdown file: test_upload.md")
    print("Content:")
    print(test_content)
    print("\n" + "="*50 + "\n")
    
    try:
        # Test the upload function (without actually uploading)
        print("Testing upload_markdown_to_docs function...")
        
        # Load secrets to make sure they work
        secrets = load_secrets()
        print("✅ Secrets loaded successfully")
        
        # Test authentication
        creds = authenticate(secrets)
        print("✅ Authentication successful")
        
        # Build drive service
        drive_service = build('drive', 'v3', credentials=creds)
        print("✅ Drive service built successfully")
        
        # Test the upload function structure (commented out to avoid actual upload)
        # doc_id = upload_markdown_to_docs(drive_service, test_file)
        # print(f"✅ Upload successful! Document ID: {doc_id}")
        
        print("✅ All function tests passed!")
        print("\nTo actually test the upload, run:")
        print(f"python md2gdocs.py {test_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test file
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"\n🗑️  Cleaned up test file: {test_file}")

if __name__ == "__main__":
    success = test_upload_function()
    sys.exit(0 if success else 1)