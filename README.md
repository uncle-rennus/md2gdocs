# Markdown to Google Docs Batch Converter (`md2gdocs.py`)

A minimalist Python CLI tool for converting Markdown files to Google Docs, supporting batch processing, two output modes, template styling, and secure, cross-platform credential management. Only four dependencies.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Credential Setup & Secret Management](#credential-setup--secret-management)
- [Setup Instructions](#setup-instructions)
- [Usage Examples](#usage-examples)
- [Detailed Guide: Secret Management](#detailed-guide-secret-management)
- [Security Notes](#security-notes)
- [Quick Start](#quick-start)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Batch conversion** of Markdown files to Google Docs
- **Two CLI output modes**:
  - **single-tabs**: All files combined into one document with section headings as tabs
  - **multi-docs**: Each file converted to a separate Google Doc
- **Google Docs style templating** (optional)
- **Glob patterns** for Markdown file selection
- **Minimal dependencies** using only:
  - `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `python-dotenv`
- **Secret management** supporting environment variables and `.env` files (never hardcoded)
- **OAuth2 token caching** for browserless re-authentication
- **Detailed logging, error handling, and actionable troubleshooting info**
- **Cross-platform**: Windows & Linux support

---

## Requirements

**Python 3.8 or later**

Install required dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
google-api-python-client==1.12.5
google-auth-oauthlib==1.2.1
google-auth-httplib2==0.2.0
python-dotenv==1.0.0
```

---

## Installation

1. Clone/download this repository and `cd` into the project folder.
2. Copy `.env.example` to `.env` and fill out your credentials.
   ```bash
   cp .env.example .env
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Credential Setup & Secret Management

Follow these steps to create and configure your Google Cloud credentials:

### 1. Get Your Google Cloud OAuth2 Credentials

- Go to https://console.cloud.google.com/apis/credentials
- Create an OAuth 2.0 Client ID ("Desktop app")
- Download your Client ID & Secret

**Required values:**
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- (Optionally) `TEMPLATE_DOC_ID` (for template styling)
- (Optionally) `OUTPUT_FOLDER_ID` (for Drive output folder)

### 2. Add Credentials to Your Environment

**Recommended:**
- Place in `.env` (see [Secret Management](#detailed-guide-secret-management))
- _Never commit your actual secrets, only use `.env.example` as template._

---

## Setup Instructions

### 1. Create Your `.env` File

1. Copy the template:
   ```bash
   cp .env.example .env
   ```
2. Fill in your credentials:
    ```ini
    GOOGLE_CLIENT_ID=your-client-id-here
    GOOGLE_CLIENT_SECRET=your-client-secret-here
    TEMPLATE_DOC_ID=your-optional-template-id-here
    OUTPUT_FOLDER_ID=your-optional-folder-id-here
    ```
3. **Do NOT commit `.env` to version control!**

### 2. (Alternative) Use Environment Variables

Set these in your system/shell (recommended for CI or production):

**Linux/bash:**
```bash
export GOOGLE_CLIENT_ID=your-client-id-here
export GOOGLE_CLIENT_SECRET=your-client-secret-here
```
**Windows (PowerShell):**
```powershell
$env:GOOGLE_CLIENT_ID="your-client-id-here"
$env:GOOGLE_CLIENT_SECRET="your-client-secret-here"
```

---

## Usage Examples

Run the tool using the following CLI syntax:

```bash
python md2gdocs.py [markdown-file-patterns] [--mode MODE] [--use-template] [--output-folder FOLDER] [--verbose/-v] [--dry-run]
```

Where:
- `[markdown-file-patterns]` can be one or more glob patterns (e.g., `docs/*.md`)
- `--mode`: either `single-tabs` (default: `multi-docs`)
- `--use-template`: Apply template Google Doc styles
- `--output-folder`: Specify Google Drive folder ID
- `--dry-run`: Print what would be converted, but don’t upload
- `--verbose`, `-v`: More logging

### Real Examples:

```bash
# Convert a single file to a new Google Doc
python md2gdocs.py README.md

# Convert multiple files (glob pattern) to one Google Doc, using tabs/sections
python md2gdocs.py docs/*.md --mode single-tabs

# Convert all .md files to individual Google Docs with template
python md2gdocs.py *.md --mode multi-docs --use-template

# Preview operation, verbose output, no upload/action
python md2gdocs.py *.md --verbose --dry-run
```

---

## Detailed Guide: Secret Management

This project supports **tiered loading** of secrets for security and convenience:

### Priority Order
1. **Environment Variables** (Most secure - production/service use)
2. **`.env` File** (Convenient - local use, loaded via `python-dotenv`)
3. **OAuth2 Token Cache** (token.json, auto-handled)

### `.env` Sample (`.env.example` provided)
```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
TEMPLATE_DOC_ID=
OUTPUT_FOLDER_ID=
```

- Only fill in the fields you need.
- Make sure `.env`, `token.json`, and `client_secret.json` are in your `.gitignore` _and never committed!_

### How It’s Loaded
- On run, the script attempts to load each secret from the OS environment.
- If missing, it loads `.env` (if present) via `python-dotenv`.
- If still missing, an error is shown and you must set the value.

### OAuth2 Token Caching
- On first run, you will be prompted to authenticate in a browser.
- Token is saved to `token.json` for re-use next time (no browser required).
- If token expires or is revoked, you'll be prompted to re-authenticate.
- **Never commit `token.json`!**

### Template Document/Output Folder

- If using `--use-template`, you must set `TEMPLATE_DOC_ID` or pass via `--output-folder`.
- To get `TEMPLATE_DOC_ID`: Open your Google Doc template and copy the string between `/d/` and `/edit` from the URL.
- To get `OUTPUT_FOLDER_ID` (optional): Open your Google Drive folder, copy the string after `/folders/` in the URL.

---

## Security Notes

**Never commit sensitive or generated files.** All the following are already protected by `.gitignore`:

- `.env`
- `token.json`
- `client_secret.json`
- `__pycache__/`
- `*.pyc`
- `.DS_Store`

**Do not log credentials.**   
**Never hardcode secrets.**


---

## Quick Start

1. Copy `.env.example` → `.env` and add Google credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Run one of:
    ```bash
    python md2gdocs.py README.md
    python md2gdocs.py docs/*.md --mode single-tabs
    python md2gdocs.py *.md --mode multi-docs --use-template
    python md2gdocs.py *.md --verbose --dry-run
    ```
4. The first run will open a browser to authenticate (OAuth2). Subsequent runs will use the cached `token.json`.
5. Find your generated Google Docs in your Drive (or folder, if specified).

---

## Troubleshooting

**Common Issues & Solutions**

- **Script exits with error about secrets:**
    - Double-check your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` or the environment.
    - Do not hardcode credentials in the script.
- **OAuth2 authentication fails repeatedly:**
    - Delete `token.json` and re-run the script.
    - Make sure browser opens and completes consent.
- **No markdown files found:**
    - Check your file patterns (e.g., `docs/*.md`).
    - All matching files must exist and be readable.
- **Invalid Google Doc Template ID:**
    - Confirm you copied ID between `/d/` and `/edit` in the URL.
- **Permission error updating Google Drive:**
    - Check that your OAuth2 user can access the output folder/Doc.
- **File encoding errors:**
    - Ensure all markdown files are UTF-8 encoded (default on most systems).
- **Rate limit or quota errors from Google API:**
    - Wait a few minutes and try again.
    - If running many files at once, use `--dry-run` for previewing.
- **"Cannot import module" errors:**
    - Verify all dependencies installed via `pip install -r requirements.txt`.

---

## CLI Help

```bash
python md2gdocs.py --help
```
Shows all available flags and parameters.

---

## Support

All code is self-contained in `md2gdocs.py`. For bug reports or questions, please open an issue or contact the maintainer.

---

**Minimalist. Secure. Cross-platform.**

---

**Required files:**
- `md2gdocs.py` (main script)
- `.env.example`  (template for secrets)
- `.gitignore`  (protects .env, token.json, client_secret.json, .pyc, etc)
- `requirements.txt` (essential dependencies only)
- `README.md`  (this file)

---

**Enjoy fast, secure batch Markdown to Google Docs conversion!**
