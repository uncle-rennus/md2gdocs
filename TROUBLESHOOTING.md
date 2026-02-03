# md2gdocs Troubleshooting Guide

## Common Issues and Solutions

### 1. Google Drive API Not Enabled (403 Forbidden)

**Error**: `403 Forbidden: Google Drive API has not been used in project...`

**Solution**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (143114029223)
3. Navigate to "APIs & Services" > "Library"
4. Search for "Google Drive API" and enable it
5. Wait 2-5 minutes for the change to propagate

### 2. Invalid Code Style Formatting (400 Bad Request)

**Error**: `Invalid value at 'requests[X].update_text_style.text_style.weighted_font_family'`

**Solution**: This has been fixed in the updated code. The script now properly handles code formatting.

### 3. Authentication Timeout

**Error**: Script hangs waiting for browser authentication

**Solution**: 
1. Run the script in a terminal that can open browser windows
2. When the browser opens, sign in with your Google account
3. Approve the requested permissions
4. The script will continue automatically

### 4. Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'google_auth_oauthlib'`

**Solution**: Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Step-by-Step Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable these APIs:
   - Google Docs API
   - Google Drive API (only needed for templates)

### 3. Configure OAuth Consent Screen
1. Go to "APIs & Services" > "OAuth consent screen"
2. Select "External" user type
3. Fill in app information (name, email, etc.)
4. Add your email as a test user
5. Save and continue (no need to add scopes yet)

### 4. Create OAuth Credentials
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app"
4. Copy the Client ID and Client Secret to your `.env` file

### 5. Run the Script
```bash
# First run (will open browser for authentication)
python md2gdocs.py README.md

# Subsequent runs (will use cached token)
python md2gdocs.py README.md --use-template

# Batch processing
python md2gdocs.py *.md --mode single-tabs
```

## Debugging Tips

### Check Your Token
```bash
python -c "
from google.oauth2.credentials import Credentials
creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/documents'])
print('Token valid:', creds.valid)
print('Token expires:', creds.expires_at)
"
```

### Test API Connection
```bash
python -c "
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/documents'])
service = build('docs', 'v1', credentials=creds)
print('API connection successful')
"
```

### Test Markdown Parsing
```bash
python -c "
from md2gdocs import parse_markdown
text, styles = parse_markdown('# Heading\n\n**bold** *italic*')
print('Parsing works! Found', len(styles), 'styles')
"
```

## Common Error Messages

### "file_cache is unavailable"
This warning is harmless and can be ignored. It's related to library version compatibility.

### "Invalid client secrets"
Check that your `.env` file contains the correct Client ID and Client Secret from Google Cloud Console.

### "Token expired"
Delete `token.json` and run the script again to get a fresh token.

### "Access not configured"
The required Google API is not enabled. Enable both Google Docs API and Google Drive API.

## Need More Help?

If you're still experiencing issues, please provide:
1. The exact error message
2. The command you ran
3. Whether this is your first time running the script
4. Whether you've enabled the required Google APIs

This will help diagnose the specific issue you're facing.