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
        if hasattr(sys.stdout, 'detach'):
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        if hasattr(sys.stderr, 'detach'):
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

def preprocess_markdown(content: str) -> tuple[str, Dict[str, str]]:
    """Preprocess markdown to handle elements that Google's converter struggles with.
    
    Returns:
        tuple: (preprocessed_content, footnote_map)
    """
    footnote_map = {}
    definition_pattern = re.compile(r'\[\^(\d+)\]:\s*(.+)$', re.MULTILINE)
    
    for match in definition_pattern.finditer(content):
        footnote_id = match.group(1)
        footnote_text = match.group(2).strip()
        footnote_map[footnote_id] = footnote_text
    
    if footnote_map:
        ref_pattern = re.compile(r'\[\^(\d+)\]')
        
        def replace_footnote(match):
            fn_id = match.group(1)
            if fn_id in footnote_map:
                return f"[{fn_id}]"
            return ""
        
        content = ref_pattern.sub(replace_footnote, content)
        content = definition_pattern.sub('', content)
    
    content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', content)
    
    return content, footnote_map

def convert_footnotes_to_real(doc_id: str, docs_service, footnote_map: Dict[str, str]) -> None:
    """Convert in-text footnote references to real Google Docs footnotes."""
    if not footnote_map:
        return
    
    doc = docs_service.documents().get(documentId=doc_id).execute()
    content = doc.get('body', {}).get('content', [])
    
    footnote_refs = []
    
    footnote_ref_pattern = re.compile(r'\[(\d+)\]')
    
    def is_footnote_definition(text: str) -> bool:
        stripped = text.strip()
        return bool(re.match(r'^\[\d+\]:\s*.+', stripped))
    
    for element in content:
        if 'paragraph' not in element:
            continue
            
        paragraph = element['paragraph']
        para_text = ''
        if 'elements' in paragraph:
            for elem in paragraph['elements']:
                if 'textRun' in elem and 'content' in elem['textRun']:
                    para_text += elem['textRun']['content']
        
        if is_footnote_definition(para_text):
            continue
        
        if 'elements' in paragraph:
            for elem in paragraph['elements']:
                if 'textRun' not in elem or 'content' not in elem['textRun']:
                    continue
                    
                text = elem['textRun']['content']
                
                for match in footnote_ref_pattern.finditer(text):
                    fn_id = match.group(1)
                    if fn_id not in footnote_map:
                        continue
                    
                    start_idx = elem['startIndex'] + match.start()
                    end_idx = elem['startIndex'] + match.end()
                    
                    footnote_refs.append({
                        'start': start_idx,
                        'end': end_idx,
                        'fn_id': fn_id,
                        'text': footnote_map[fn_id]
                    })
    
    footnote_refs.sort(key=lambda x: x['start'], reverse=True)
    
    requests = []
    footnote_contents = {}
    
    for ref in footnote_refs:
        requests.append({
            'createFootnote': {
                'location': {
                    'segmentId': '',
                    'index': ref['start']
                }
            }
        })
        requests.append({
            'deleteContentRange': {
                'range': {
                    'segmentId': '',
                    'startIndex': ref['start'],
                    'endIndex': ref['end']
                }
            }
        })
        footnote_contents[ref['start']] = ref['text']
    
    if not requests:
        logger.info("No footnote references found")
        remove_footnote_definitions(doc_id, docs_service)
        return
    
    result = docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()
    
    replies = result.get('replies', [])
    
    fn_id_map = {}
    req_idx = 0
    for ref in footnote_refs:
        if req_idx < len(replies) and 'createFootnote' in replies[req_idx]:
            fn_id = replies[req_idx]['createFootnote']['footnoteId']
            fn_id_map[ref['start']] = fn_id
        req_idx += 2
    
    updated_doc = docs_service.documents().get(documentId=doc_id).execute()
    footnotes = updated_doc.get('footnotes', {})
    
    for start_idx, fn_id in fn_id_map.items():
        if fn_id in footnotes:
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': [{
                    'insertText': {
                        'location': {'segmentId': fn_id, 'index': 0},
                        'text': footnote_contents[start_idx]
                    }
                }]}
            ).execute()
    
    logger.info(f"Created {len(fn_id_map)} real footnotes")
    remove_footnote_definitions(doc_id, docs_service)

def remove_footnote_definitions(doc_id: str, docs_service) -> None:
    """Remove footnote definition lines from the end of the document."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    content = doc.get('body', {}).get('content', [])
    
    def_pattern = re.compile(r'^\[\d+\]:\s*.+$', re.MULTILINE)
    requests = []
    
    for element in content:
        if 'paragraph' in element:
            paragraph = element['paragraph']
            if 'elements' in paragraph:
                for elem in paragraph['elements']:
                    if 'textRun' in elem and 'content' in elem['textRun']:
                        text = elem['textRun']['content']
                        if def_pattern.search(text):
                            requests.append({
                                'deleteContentRange': {
                                    'range': {
                                        'segmentId': '',
                                        'startIndex': elem['startIndex'],
                                        'endIndex': elem['endIndex']
                                    }
                                }
                            })
    
    if requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        logger.info("Removed footnote definitions from document")

def load_secrets() -> Dict[str, Optional[str]]:
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

def authenticate(secrets: Dict[str, Optional[str]]) -> Credentials:
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
    
    preprocessed_content, footnote_map = preprocess_markdown(markdown_content)
    
    # If template is specified, use the template workflow
    if template_doc_id and drive_service:
        try:
            # Export template as HTML
            template_html = drive_service.files().export(
                fileId=template_doc_id,
                mimeType='text/html'
            ).execute()
            
            # Convert markdown to HTML
            import markdown
            html_converter = markdown.Markdown(extensions=['extra'])
            content_html = html_converter.convert(preprocessed_content)
            
            # Replace the {{CONTENT}} placeholder in template
            template_html_str = template_html.decode('utf-8') if isinstance(template_html, bytes) else template_html
            final_html = template_html_str.replace('{{CONTENT}}', content_html)
            
            # Upload the final HTML and convert to Google Doc
            media = MediaIoBaseUpload(
                io.BytesIO(final_html.encode('utf-8')),
                mimetype='text/html',
                resumable=True
            )
            
            final_doc = drive_service.files().create(
                body={
                    'name': doc_name,
                    'mimeType': 'application/vnd.google-apps.document',
                    'parents': [output_folder_id] if output_folder_id else []
                },
                media_body=media
            ).execute()
            
            final_doc_id = final_doc['id']
            logger.info(f"Created document from template {template_doc_id} via HTML conversion: {final_doc_id}")
            
        except Exception as e:
            logger.warning(f"Could not use template HTML workflow: {str(e)}")
            # Fall back to creating blank document and inserting content
            final_doc_id = _create_blank_document_and_insert_content(drive_service, docs_service, doc_name, preprocessed_content, output_folder_id)
    else:
        # No template requested or Drive service not available
        final_doc_id = _create_blank_document_and_insert_content(drive_service, docs_service, doc_name, preprocessed_content, output_folder_id)
    
    if footnote_map:
        logger.info(f"Converting {len(footnote_map)} footnotes to real Google Docs footnotes")
        convert_footnotes_to_real(final_doc_id, docs_service, footnote_map)
    
    return final_doc_id


def _create_blank_document_and_insert_content(drive_service, docs_service, doc_name: str, content: str, output_folder_id: Optional[str] = None) -> str:
    """Create a blank document and insert content."""
    # Create blank document
    doc = drive_service.files().create(
        body={
            'name': doc_name,
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [output_folder_id] if output_folder_id else []
        }
    ).execute()
    doc_id = doc['id']
    logger.info(f"Created blank document: {doc_id}")
    
    # Insert content
    requests = [{
        'insertText': {
            'location': {'index': 1},
            'text': content
        }
    }]
    
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()
    
    logger.info(f"Inserted content into document: {doc_id}")
    return doc_id

def create_document(drive_service, docs_service, md_file: str, template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Create a Google Doc from markdown using simple upload."""
    return upload_markdown_to_docs(drive_service, docs_service, md_file, template_doc_id, output_folder_id)

def create_tabs_document(drive_service, docs_service, md_files: List[str], template_doc_id: Optional[str] = None, output_folder_id: Optional[str] = None) -> str:
    """Create a single doc with sections for each markdown file."""
    # If template is specified, use template workflow
    if template_doc_id and drive_service:
        try:
            # Export template as HTML
            template_html = drive_service.files().export(
                fileId=template_doc_id,
                mimeType='text/html'
            ).execute()
            
            # Convert markdown files to HTML and combine
            import markdown
            html_converter = markdown.Markdown(extensions=['extra'])
            
            combined_content_html = ""
            for md_file in md_files:
                tab_title = Path(md_file).stem
                
                # Read the markdown content
                with open(md_file, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                
                # Convert markdown to HTML
                content_html = html_converter.convert(markdown_content)
                
                # Add section heading and content
                combined_content_html += f'<h1>{tab_title}</h1>\n{content_html}\n\n'
            
            # Replace the {{CONTENT}} placeholder in template
            template_html_str = template_html.decode('utf-8') if isinstance(template_html, bytes) else template_html
            final_html = template_html_str.replace('{{CONTENT}}', combined_content_html)
            
            # Upload the final HTML and convert to Google Doc
            media = MediaIoBaseUpload(
                io.BytesIO(final_html.encode('utf-8')),
                mimetype='text/html',
                resumable=True
            )
            
            final_doc = drive_service.files().create(
                body={
                    'name': 'Markdown Batch Conversion',
                    'mimeType': 'application/vnd.google-apps.document',
                    'parents': [output_folder_id] if output_folder_id else []
                },
                media_body=media
            ).execute()
            
            doc_id = final_doc['id']
            logger.info(f"Created document from template {template_doc_id} via HTML conversion: {doc_id}")
            
            # Move to output folder if specified
            if output_folder_id:
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=output_folder_id,
                    fields='id, parents'
                ).execute()
                logger.info(f"Moved combined document to folder {output_folder_id}")
                
            return doc_id
            
        except Exception as e:
            logger.warning(f"Could not use template HTML workflow for tabs mode: {str(e)}")
            # Fall back to original method
            pass
    
    # Original implementation (fallback or when no template)
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