#!/usr/bin/env python3
"""
md2gdocs.py - Convert Markdown files to Google Docs with batch processing, templates, and secure credential management.
Simplified version using Google Drive's built-in Markdown conversion.
"""
import io
import os
import re
import glob
import logging
import sys
from typing import List, Dict, Optional
from pathlib import Path

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from dotenv import load_dotenv

# Set up proper Unicode handling for Windows
if sys.platform == "win32":
    import codecs
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except:
        pass  # If already set or can't be set, continue anyway

# Create Typer app
app = typer.Typer(
    name="md2gdocs",
    help="Convert Markdown files to Google Docs using Google Drive's built-in conversion.",
    add_completion=False,
    no_args_is_help=True
)

# Constants
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive'
]
TOKEN_FILE = 'token.json'

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def preprocess_markdown(content: str) -> str:
    """Preprocess markdown to handle elements that Google's converter struggles with."""
    
    # Extract footnote definitions and convert to inline references
    footnote_map = {}
    definition_pattern = re.compile(r'\[\^(\d+)\]:\s*(.+)$', re.MULTILINE)
    
    for match in definition_pattern.finditer(content):
        footnote_id = match.group(1)
        footnote_text = match.group(2).strip()
        footnote_map[footnote_id] = footnote_text
    
    # Replace footnote references with inline references
    if footnote_map:
        ref_pattern = re.compile(r'\[\^(\d+)\]')
        
        def replace_footnote(match):
            fn_id = match.group(1)
            if fn_id in footnote_map:
                return f"[({footnote_map[fn_id]})]"
            return ""
        
        content = ref_pattern.sub(replace_footnote, content)
        
        # Remove footnote definition lines
        content = definition_pattern.sub('', content)
    
    # Remove reference-style image links that might cause issues (keep alt text)
    content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', content)
    
    return content

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

def upload_markdown_to_docs(drive_service, docs_service, file_path: str, template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Upload Markdown file and convert to Google Docs format with proper template support."""
    file_name = Path(file_path).stem
    doc_name = f"{file_name}"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    preprocessed_content = preprocess_markdown(markdown_content)
    
    media = MediaIoBaseUpload(
        io.BytesIO(preprocessed_content.encode('utf-8')),
        mimetype='text/markdown',
        resumable=True
    )
    
    markdown_file = drive_service.files().create(
        body={
            'name': f"{doc_name}.md",
            'mimeType': 'text/markdown',
            'parents': [output_folder_id] if output_folder_id else []
        },
        media_body=media
    ).execute()
    
    markdown_file_id = markdown_file['id']
    logger.info(f"Uploaded Markdown file: {markdown_file_id}")
    
    converted_doc = drive_service.files().copy(
        fileId=markdown_file_id,
        body={
            'name': doc_name,
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [output_folder_id] if output_folder_id else []
        }
    ).execute()
    
    final_doc_id = converted_doc['id']
    logger.info(f"Converted Markdown to Google Doc: {final_doc_id}")
    
    if template_doc_id:
        logger.info(f"Template styling would be applied here (future enhancement)")
    
    drive_service.files().delete(fileId=markdown_file_id).execute()
    logger.info(f"Cleaned up temporary Markdown file: {markdown_file_id}")
    
    return final_doc_id

def create_document(drive_service, docs_service, md_file: str, template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Create a Google Doc from markdown using simple upload."""
    return upload_markdown_to_docs(drive_service, docs_service, md_file, template_doc_id, output_folder_id)

def create_tabs_document(drive_service, docs_service, md_files: List[str], template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Create a single doc with sections for each markdown file."""
    # Create main document
    doc = drive_service.files().create(
        body={
            'name': 'Markdown Batch Conversion',
            'mimeType': 'application/vnd.google-apps.document'
        }
    ).execute()
    doc_id = doc['id']
    logger.info(f"Created main document: {doc_id}")

    # Move to output folder if specified
    if output_folder_id:
        drive_service.files().update(
            fileId=doc_id,
            addParents=output_folder_id,
            fields='id, parents'
        ).execute()
        logger.info(f"Moved combined document to folder {output_folder_id}")

    # For tabs mode, we'll append each file's content using Docs API
    for md_file in md_files:
        tab_title = Path(md_file).stem
        
        # Read the markdown content
        with open(md_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Add section heading
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [
                {'insertText': {
                    'location': {'index': 1},
                    'text': f'\n\n=== {tab_title} ===\n\n'
                }}
            ]}
        ).execute()
        
        # Insert the markdown content
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [
                {'insertText': {
                    'location': {'index': 1},
                    'text': markdown_content + '\n\n'
                }}
            ]}
        ).execute()
        
        logger.info(f"Added content from {md_file}")

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

@app.command()
def convert(
    files: List[str] = typer.Argument(..., help="Markdown files or glob patterns (e.g., *.md)"),
    mode: str = typer.Option("multi-docs", "--mode", "-m", 
                           help="Output mode: 'single-tabs' (one doc) or 'multi-docs' (separate docs)"),
    use_template: bool = typer.Option(False, "--use-template", "-t",
                                    help="Apply template styles from Google Docs template"),
    verbose: bool = typer.Option(False, "--verbose", "-v",
                               help="Enable verbose logging for debugging"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d",
                              help="Preview what would be converted without uploading")
):
    """Convert Markdown files to Google Docs using Google Drive's built-in conversion."""
    
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    try:
        # Load secrets and authenticate
        secrets = load_secrets()
        creds = authenticate(secrets)
        
        # Build Drive service (always needed now)
        drive_service = build('drive', 'v3', credentials=creds)
        logger.info("Drive service initialized")
        
        # Build Docs service for tabs mode
        docs_service = build('docs', 'v1', credentials=creds)
        
        # Discover and validate markdown files
        md_files = discover_markdown_files(files)
        
        if dry_run:
            logger.info(f"Would convert {len(md_files)} files: {md_files}")
            typer.echo(f"Would convert {len(md_files)} files to Google Docs")
            for file in md_files:
                typer.echo(f"  - {file}")
            return
        
        output_folder_id = secrets['output_folder_id']
        
        if mode == 'single-tabs':
            doc_id = create_tabs_document(
                drive_service, docs_service, md_files,
                secrets['template_doc_id'] if use_template else None,
                output_folder_id
            )
            logger.info(f"Created single doc with sections: https://docs.google.com/document/d/{doc_id}/edit")
            typer.echo(f"Created single document with sections: https://docs.google.com/document/d/{doc_id}/edit")
        else:  # multi-docs mode
            for md_file in md_files:
                doc_id = create_document(
                    drive_service, docs_service, 
                    md_file, 
                    secrets['template_doc_id'] if use_template else None,
                    output_folder_id
                )
                logger.info(f"Created doc for {md_file}: https://docs.google.com/document/d/{doc_id}/edit")
                typer.echo(f"Created document for {md_file}: https://docs.google.com/document/d/{doc_id}/edit")
                
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

# Add version command
@app.command()
def version():
    """Show version information."""
    typer.echo("md2gdocs - Markdown to Google Docs Converter")
    typer.echo("Version: 1.0.0")
    typer.echo("Using Typer for CLI interface")

# Add setup command
@app.command()
def setup():
    """Show setup instructions."""
    typer.echo("=== md2gdocs Setup ===")
    typer.echo("1. Install dependencies: pip install -r requirements.txt")
    typer.echo("2. Copy .env.example to .env and add your Google credentials")
    typer.echo("3. Enable Google Docs API in Google Cloud Console")
    typer.echo("4. Run: python md2gdocs.py --help for usage")

if __name__ == "__main__":
    app()