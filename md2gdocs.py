#!/usr/bin/env python3
"""
md2gdocs.py - Convert Markdown files to Google Docs with batch processing, templates, and secure credential management.
"""
import os
import re
import glob
import argparse
import logging
from typing import List, Dict, Optional
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

# Constants
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive'
]
TOKEN_FILE = 'token.json'
STYLE_MAP = {
    'bold': 'bold',
    'italic': 'italic',
    'code': 'code',
    'heading1': 'HEADING_1',
    'heading2': 'HEADING_2',
    'heading3': 'HEADING_3',
    'link': 'link',
    'list': 'list',
}

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_secrets() -> Dict[str, str]:
    """Load secrets from environment variables or .env file."""
    load_dotenv('.env', override=False)
    secrets = {
        'client_id': os.getenv('GOOGLE_CLIENT_ID'),
        'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
        'template_doc_id': os.getenv('TEMPLATE_DOC_ID'),
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

def parse_markdown(md: str) -> tuple[str, List[tuple]]:
    """Parse markdown to plain text and style actions with improved formatting."""
    plain_text = md
    style_actions = []

    # Headings - preserve the heading markers for better Google Docs compatibility
    heading_matches = list(re.finditer(r'^(#{1,3})\s+(.*?)$', plain_text, re.MULTILINE))
    for match in heading_matches:
        level = len(match.group(1))
        style_actions.append((f'heading{level}', match.start(), match.end()))
    
    # Remove heading markers but keep the text
    plain_text = re.sub(r'^#{1,3}\s+', '', plain_text, flags=re.MULTILINE)

    # Bold - handle both **bold** and __bold__
    bold_matches = list(re.finditer(r'(\*\*|__)(.*?)\1', plain_text))
    for match in bold_matches:
        # Adjust positions since we removed heading markers
        adjusted_start = match.start()
        adjusted_end = match.end()
        style_actions.append(('bold', adjusted_start, adjusted_end))
    
    # Remove bold markers
    plain_text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', plain_text)

    # Italic - handle both *italic* and _italic_
    italic_matches = list(re.finditer(r'([*_])(.*?)\1', plain_text))
    for match in italic_matches:
        # Skip if it's part of a bold pattern (already handled)
        if not re.match(r'\*\*|__', match.group(0)):
            adjusted_start = match.start()
            adjusted_end = match.end()
            style_actions.append(('italic', adjusted_start, adjusted_end))
    
    # Remove italic markers
    plain_text = re.sub(r'([*_])(.*?)\1', r'\2', plain_text)

    # Code blocks - handle both ```code``` and `code`
    code_matches = list(re.finditer(r'(```|`)(.*?)\1', plain_text, re.DOTALL))
    for match in code_matches:
        adjusted_start = match.start()
        adjusted_end = match.end()
        style_actions.append(('code', adjusted_start, adjusted_end))
    
    # Remove code markers
    plain_text = re.sub(r'(```|`)(.*?)\1', r'\2', plain_text, flags=re.DOTALL)

    # Links - basic link parsing
    link_matches = list(re.finditer(r'\[(.*?)\]\((.*?)\)', plain_text))
    for match in link_matches:
        adjusted_start = match.start()
        adjusted_end = match.end()
        style_actions.append(('link', adjusted_start, adjusted_end))
    
    # Remove link markers but keep the text
    plain_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', plain_text)

    # Lists - basic unordered list detection
    list_matches = list(re.finditer(r'^\s*[-*+]\s+', plain_text, re.MULTILINE))
    for match in list_matches:
        style_actions.append(('list', match.start(), match.end()))
    
    # Remove list markers
    plain_text = re.sub(r'^\s*[-*+]\s+', '', plain_text, flags=re.MULTILINE)

    return plain_text, style_actions

def apply_styles(service, doc_id: str, style_actions: List[tuple], tab_id: Optional[str] = None):
    """Apply styles to a Google Doc with enhanced formatting."""
    requests = []
    for style_type, start_idx, end_idx in style_actions:
        if style_type.startswith('heading'):
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': start_idx, 'endIndex': end_idx},
                    'paragraphStyle': {'namedStyleType': STYLE_MAP[style_type]},
                    'fields': 'namedStyleType'
                }
            })
        elif style_type == 'code':
            # Enhanced code formatting
            requests.append({
                'updateTextStyle': {
                    'range': {'startIndex': start_idx, 'endIndex': end_idx},
                    'textStyle': {
                        'weightedFontFamily': {'fontFamily': 'Courier New'},
                        'backgroundColor': {'color': {'rgbColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}}}
                    },
                    'fields': 'weightedFontFamily,backgroundColor'
                }
            })
        elif style_type == 'link':
            # Link formatting
            requests.append({
                'updateTextStyle': {
                    'range': {'startIndex': start_idx, 'endIndex': end_idx},
                    'textStyle': {
                        'link': {'url': 'https://example.com'},
                        'bold': True
                    },
                    'fields': 'link,bold'
                }
            })
        elif style_type == 'list':
            # List formatting
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': start_idx, 'endIndex': end_idx},
                    'paragraphStyle': {
                        'bullet': {'listId': 'kix.list.1', 'nestingLevel': 0}
                    },
                    'fields': 'bullet'
                }
            })
        else:
            # Bold, italic, etc.
            requests.append({
                'updateTextStyle': {
                    'range': {'startIndex': start_idx, 'endIndex': end_idx},
                    'textStyle': {STYLE_MAP[style_type]: True},
                    'fields': STYLE_MAP[style_type]
                }
            })
    
    # Apply styles in smaller batches to avoid API limits
    if requests:
        batch_size = 15  # Further reduced for better reliability
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            try:
                service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': batch}
                ).execute()
            except Exception as e:
                logger.error(f"Failed to apply style batch {i//batch_size + 1}: {e}")
                # Continue with next batch even if one fails

def create_document(service, drive_service, md_file: str, template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Create a Google Doc from markdown."""
    with open(md_file, 'r', encoding='utf-8') as f:
        md = f.read()
    plain_text, style_actions = parse_markdown(md)
    doc_name = Path(md_file).stem

    # Create document
    if template_doc_id and drive_service:
        try:
            # Try to use template if Drive API is available
            copied = drive_service.files().copy(
                fileId=template_doc_id,
                body={'name': doc_name}
            ).execute()
            doc_id = copied['id']
            logger.info(f"Created document from template {template_doc_id}")
            
            # Move to output folder if specified
            if output_folder_id:
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=output_folder_id,
                    fields='id, parents'
                ).execute()
                logger.info(f"Moved document to folder {output_folder_id}")
                
        except Exception as e:
            logger.warning(f"Could not use template (Drive API may not be enabled): {str(e)}")
            # Fall back to blank document
            doc = service.documents().create(body={'title': doc_name}).execute()
            doc_id = doc['documentId']
            
            # Move to output folder if specified
            if output_folder_id and drive_service:
                try:
                    drive_service.files().update(
                        fileId=doc_id,
                        addParents=output_folder_id,
                        fields='id, parents'
                    ).execute()
                    logger.info(f"Moved document to folder {output_folder_id}")
                except Exception as e:
                    logger.warning(f"Could not move document to folder: {str(e)}")
    else:
        # No template requested or Drive service not available
        doc = service.documents().create(body={'title': doc_name}).execute()
        doc_id = doc['documentId']
        
        # Move to output folder if specified
        if output_folder_id and drive_service:
            try:
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=output_folder_id,
                    fields='id, parents'
                ).execute()
                logger.info(f"Moved document to folder {output_folder_id}")
            except Exception as e:
                logger.warning(f"Could not move document to folder: {str(e)}")

    # Insert content
    service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': [{'insertText': {'location': {'index': 1}, 'text': plain_text}}]}
    ).execute()
    
    # Apply styles in smaller batches to avoid API limits
    batch_size = 20  # Reduced to be safer
    for i in range(0, len(style_actions), batch_size):
        batch = style_actions[i:i + batch_size]
        apply_styles(service, doc_id, batch)
    
    return doc_id

def create_tabs_document(service, drive_service, md_files: List[str], template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Create a single doc with sections for each markdown file."""
    doc = service.documents().create(body={'title': 'Markdown Batch Conversion'}).execute()
    doc_id = doc['documentId']

    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            md = f.read()
        plain_text, style_actions = parse_markdown(md)
        tab_title = Path(md_file).stem

        # Insert section heading
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [
                {'insertText': {'location': {'index': 1}, 'text': f'\n\n=== {tab_title} ===\n\n'}},
                {'insertText': {'location': {'index': 1}, 'text': plain_text}}
            ]}
        ).execute()
        apply_styles(service, doc_id, style_actions)

    # Move to output folder if specified
    if output_folder_id and drive_service:
        try:
            drive_service.files().update(
                fileId=doc_id,
                addParents=output_folder_id,
                fields='id, parents'
            ).execute()
            logger.info(f"Moved combined document to folder {output_folder_id}")
        except Exception as e:
            logger.warning(f"Could not move combined document to folder: {str(e)}")

    return doc_id

def discover_markdown_files(patterns: List[str]) -> List[str]:
    """Discover markdown files using glob patterns."""
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        logger.error(f"No markdown files found matching: {patterns}")
        exit(1)
    return sorted(files)

def main():
    parser = argparse.ArgumentParser(description='Convert Markdown files to Google Docs.')
    parser.add_argument('files', nargs='+', help='Markdown files or glob patterns (e.g., *.md)')
    parser.add_argument('--mode', choices=['single-tabs', 'multi-docs'], default='multi-docs',
                       help='Output mode: single-tabs (one doc) or multi-docs (separate docs)')
    parser.add_argument('--use-template', action='store_true', help='Apply template styles')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--dry-run', action='store_true', help='Preview without uploading')
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    secrets = load_secrets()
    creds = authenticate(secrets)
    service = build('docs', 'v1', credentials=creds)
    
    # Only build Drive service if templates are requested
    drive_service = None
    if args.use_template and secrets['template_doc_id']:
        try:
            drive_service = build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.warning(f"Could not initialize Drive service (templates disabled): {e}")

    md_files = discover_markdown_files(args.files)
    if args.dry_run:
        logger.info(f"Would convert {len(md_files)} files: {md_files}")
        return

    output_folder_id = secrets['output_folder_id']
    
    if args.mode == 'single-tabs':
        doc_id = create_tabs_document(service, drive_service, md_files, secrets['template_doc_id'] if args.use_template else None, output_folder_id)
        logger.info(f"Created single doc with sections: https://docs.google.com/document/d/{doc_id}/edit")
    else:
        for md_file in md_files:
            doc_id = create_document(
                service, 
                drive_service, 
                md_file, 
                secrets['template_doc_id'] if args.use_template else None,
                output_folder_id
            )
            logger.info(f"Created doc for {md_file}: https://docs.google.com/document/d/{doc_id}/edit")

if __name__ == '__main__':
    main()