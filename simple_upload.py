#!/usr/bin/env python3
"""
Simple script to upload files to Google Drive without Markdown parsing.
This is a minimal version for testing upload functionality.
"""
import os
import logging
import sys
from typing import Dict, Optional
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPES = [
    'https://www.googleapis.com/auth/drive'
]
TOKEN_FILE = 'token.json'

def load_secrets() -> Dict[str, str]:
    """Load secrets from environment variables or .env file."""
    load_dotenv('.env', override=False)
    secrets = {
        'client_id': os.getenv('GOOGLE_CLIENT_ID'),
        'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
        'output_folder_id': os.getenv('OUTPUT_FOLDER_ID'),
    }
    if not secrets['client_id'] or not secrets['client_secret']:
        logger.error("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET. Set in .env or environment.")
        exit(1)
    return secrets

def authenticate(secrets: Dict[str, str]) -> Credentials:
    """Authenticate with Google APIs and cache token."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(
                {
                    'installed': {
                        'client_id': secrets['client_id'],
                        'client_secret': secrets['client_secret'],
                        'redirect_uris': ['http://localhost'],
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token'
                    }
                },
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

def upload_file_to_drive(drive_service, file_path: str, output_folder_id: Optional[str] = None) -> str:
    """Upload a file to Google Drive."""
    file_name = Path(file_path).name
    
    # Create file metadata
    file_metadata = {
        'name': file_name,
        'mimeType': 'application/vnd.google-apps.document'
    }
    
    # Add parent folder if specified
    if output_folder_id:
        file_metadata['parents'] = [output_folder_id]
    
    try:
        # Upload the file using MediaFileUpload approach
        from googleapiclient.http import MediaFileUpload
        
        media = MediaFileUpload(file_path, mimetype='text/markdown', resumable=True)
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logger.info(f"Uploaded file '{file_name}' to Google Drive with ID: {file['id']}")
        return file['id']
        
    except HttpError as error:
        logger.error(f"Failed to upload file '{file_name}': {error}")
        raise

def main():
    """Main function to upload files to Google Drive."""
    if len(sys.argv) < 2:
        print("Usage: python simple_upload.py <file1> [<file2> ...]")
        return
    
    try:
        # Load secrets and authenticate
        secrets = load_secrets()
        creds = authenticate(secrets)
        drive_service = build('drive', 'v3', credentials=creds)
        logger.info("Drive service initialized")
        
        # Process each file
        output_folder_id = secrets['output_folder_id']
        
        for file_path in sys.argv[1:]:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                continue
                
            file_id = upload_file_to_drive(drive_service, file_path, output_folder_id)
            file_url = f"https://drive.google.com/file/d/{file_id}/view"
            print(f"✅ Uploaded: {file_path}")
            print(f"   URL: {file_url}")
            print()
            
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
