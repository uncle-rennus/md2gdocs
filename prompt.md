
# AI Agent Prompt: Markdown to Google Docs Batch Converter
## Complete Specification for Code Generation

---

## PROJECT OVERVIEW

Build a **minimalist Python CLI tool** that converts markdown files to Google Docs with the following capabilities:

1. **Batch processing** of markdown files (single or multiple files)
2. **Two output modes:**
   - `--mode single-tabs`: All files converted to one Google Doc with multiple tabs
   - `--mode multi-docs`: Each file converted to a separate Google Doc
3. **Template support**: Apply consistent formatting across all generated documents
4. **Cross-platform secret management**: Secure handling of Google API credentials on Windows/Linux
5. **Minimalist dependencies**: Only use essential libraries, no unnecessary bloat

---

## REQUIREMENTS

### 1. Minimalist Dependency List

**REQUIRED (core functionality only):**
- `google-api-python-client` - Google Docs API
- `google-auth-oauthlib` - OAuth2 authentication for Google
- `google-auth-httplib2` - HTTP transport for auth
- `python-dotenv` - Environment variable management from `.env` files

**FORBIDDEN (do not use):**
- pandas, numpy, django, requests
- flask, fastapi
- Click, Typer (use argparse from stdlib)
- markdown2, showdown (use simple regex-based parsing)

**OPTIONAL (only if genuinely needed):**
- pathlib (stdlib, already imported)
- json (stdlib)
- os (stdlib)

### 2. Secret Management (Windows + Linux Cross-Platform)

**Approach: Tiered secret loading** (most secure → least secure):

#### Tier 1: Environment Variables (Recommended for production)
- Load from OS environment variables directly
- Linux: `export GOOGLE_CLIENT_ID=...` in shell
- Windows: Set via `setx GOOGLE_CLIENT_ID ...` or PowerShell
- Script reads via `os.getenv('GOOGLE_CLIENT_ID')`

#### Tier 2: .env File (Recommended for local development)
- Create `.env` file in project root (add to `.gitignore` immediately)
- Use `python-dotenv` to load at startup
- Format:
  ```
  GOOGLE_CLIENT_ID=your_client_id_here
  GOOGLE_CLIENT_SECRET=your_client_secret_here
  GOOGLE_REDIRECT_URI=http://localhost:8080
  TEMPLATE_DOC_ID=your_template_doc_id_here
  OUTPUT_FOLDER_ID=your_output_folder_id_here
  ```

#### Tier 3: OAuth2 Token Cache (Automatic)
- Store token in `token.json` after first OAuth login
- Automatically refresh on subsequent runs
- Never ask user to re-authenticate unless token expires or revoked

**Implementation pattern:**
```python
def load_secrets():
    """Load secrets with fallback chain: env vars → .env file → user input"""
    load_dotenv('.env', override=False)
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("ERROR: Secrets not found in environment or .env file")
        print("Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
        exit(1)
    
    return {'client_id': client_id, 'client_secret': client_secret}
```

**Security checklist:**
- [ ] Never hardcode secrets in source code
- [ ] `.gitignore` must include: `.env`, `token.json`, `client_secret.json`
- [ ] Provide `.env.example` template (with blank values) for reference
- [ ] Document setup: "Get credentials from Google Cloud → Save to .env or env vars → Run script"

### 3. Template Generation & Management

**Two-part system:**

#### Part A: Template Document (Google Docs Side)
1. User creates template Google Doc in their Google Drive with desired styles
2. User gets document ID from URL: `https://docs.google.com/document/d/{DOCUMENT_ID}/edit`
3. Script copies this template and fills with markdown content

#### Part B: Heading/Style Mapping (Script Side)
```python
STYLE_MAP = {
    'heading1': 'HEADING_1',
    'heading2': 'HEADING_2',
    'heading3': 'HEADING_3',
    'bold': 'bold',
    'italic': 'italic',
    'code': 'monospace',
    'link': 'link'
}
```

**Template copying workflow (multi-docs mode):**
```
1. Read markdown file → extract headings + content
2. Copy template Google Doc to new document
3. Clear template content (keep styles)
4. Insert markdown content with heading level → style mapping
5. Move new doc to output folder (if specified)
```

**Template usage in single-tabs mode:**
```
1. Create main document with template styles applied to first tab
2. For each additional markdown file:
   - Create new tab in main doc
   - Insert markdown content
   - Apply same heading/style mapping to new tab
```

---

## CLI INTERFACE

Use **stdlib argparse** (NOT Click or Typer):

```python
parser = argparse.ArgumentParser(
    description='Convert markdown files to Google Docs'
)
parser.add_argument('files', nargs='+', help='Markdown files to convert')
parser.add_argument('--mode', choices=['single-tabs', 'multi-docs'], 
                   default='multi-docs', help='Conversion mode')
parser.add_argument('--use-template', action='store_true', 
                   help='Apply template styles')
parser.add_argument('--output-folder', help='Google Drive folder ID')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--dry-run', action='store_true')
```

**Usage Examples:**
```bash
python md2gdocs.py README.md
python md2gdocs.py docs/*.md --mode single-tabs
python md2gdocs.py *.md --mode multi-docs --use-template
python md2gdocs.py chapter*.md --verbose --dry-run
```

---

## MARKDOWN PARSING (Minimalist Regex-Based)

**No markdown2/showdown library.** Use simple regex for core markdown syntax:

```python
def parse_markdown_simple(text):
    """
    Extract text and style actions without external markdown library.
    Returns: (plain_text, style_actions)
    style_actions = [(style_type, start_idx, end_idx), ...]
    """
    actions = []
    plain_text = text
    
    # Parse bold (**text**)
    for match in re.finditer(r'\*\*(.*?)\*\*', plain_text):
        actions.append(('bold', match.start(), match.end()))
    plain_text = re.sub(r'\*\*(.*?)\*\*', r'\1', plain_text)
    
    # Parse italic (*text*)
    for match in re.finditer(r'\*(.*?)\*', plain_text):
        actions.append(('italic', match.start(), match.end()))
    plain_text = re.sub(r'\*(.*?)\*', r'\1', plain_text)
    
    # Parse code blocks (```code```)
    for match in re.finditer(r'```(.*?)```', plain_text, re.DOTALL):
        actions.append(('monospace', match.start(), match.end()))
    plain_text = re.sub(r'```(.*?)```', r'\1', plain_text, flags=re.DOTALL)
    
    # Parse headings (# Heading)
    for match in re.finditer(r'^(#{1,3})\s+(.*?)$', plain_text, re.MULTILINE):
        level = len(match.group(1))
        actions.append((f'heading{level}', match.start(), match.end()))
    plain_text = re.sub(r'^#{1,3}\s+', '', plain_text, flags=re.MULTILINE)
    
    return plain_text, actions
```

---

## GOOGLE DOCS API INTEGRATION

### Authentication (OAuth2 with token caching)
```python
def authenticate(secrets):
    """
    Authenticate with Google APIs.
    First run: Opens browser for user consent, saves token.json.
    Subsequent runs: Uses saved token.json automatically.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    
    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = None
    
    # Load existing token if available
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(
                {'installed': secrets},
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save token for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    docs_service = build('docs', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    
    return docs_service, drive_service
```

### Document Creation (Multi-Docs Mode)
```python
def create_document_from_markdown(service, drive_service, md_file, template_doc_id=None):
    """Create a new Google Doc from markdown file"""
    
    # Read and parse markdown
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    plain_text, style_actions = parse_markdown_simple(content)
    doc_name = os.path.basename(md_file).replace('.md', '')
    
    # If template provided, copy it; otherwise create blank doc
    if template_doc_id:
        copied = drive_service.files().copy(
            fileId=template_doc_id,
            body={'name': doc_name}
        ).execute()
        doc_id = copied['id']
    else:
        doc = service.documents().create(body={'title': doc_name}).execute()
        doc_id = doc['documentId']
    
    # Insert text
    requests = [{'insertText': {'location': {'index': 1}, 'text': plain_text}}]
    service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    
    # Apply formatting
    apply_styles(service, doc_id, style_actions)
    
    return doc_id
```

### Tabs Mode (Single Document)
```python
def create_tabs_document(service, md_files, template_doc_id=None):
    """Create single doc with multiple tabs from markdown files"""
    
    # Create main document
    doc = service.documents().create(body={'title': 'Markdown Batch Conversion'}).execute()
    doc_id = doc['documentId']
    
    # For each markdown file, create a tab
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        plain_text, style_actions = parse_markdown_simple(content)
        tab_title = os.path.basename(md_file).replace('.md', '')
        
        # Create tab
        tab_req = {
            'insertTab': {
                'tabProperties': {'title': tab_title}
            }
        }
        result = service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [tab_req]}
        ).execute()
        
        # Get new tab ID from result
        new_tab_id = result['replies'][0]['insertTab']['tabProperties']['tabId']
        
        # Insert text into new tab
        insert_req = {
            'insertText': {
                'location': {'index': 1, 'tabId': new_tab_id},
                'text': plain_text
            }
        }
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [insert_req]}
        ).execute()
        
        # Apply styles to tab
        apply_styles(service, doc_id, style_actions, tab_id=new_tab_id)
    
    return doc_id
```

### Style Application
```python
def apply_styles(service, doc_id, style_actions, tab_id=None):
    """Apply heading/bold/italic styles via Google Docs API"""
    
    STYLE_MAP = {
        'bold': 'bold',
        'italic': 'italic',
        'monospace': 'weightedFontFamily',
        'heading1': 'headingId=HEADING_1',
        'heading2': 'headingId=HEADING_2',
        'heading3': 'headingId=HEADING_3',
    }
    
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
        else:
            requests.append({
                'updateTextStyle': {
                    'range': {'startIndex': start_idx, 'endIndex': end_idx},
                    'textStyle': {STYLE_MAP[style_type]: True},
                    'fields': STYLE_MAP[style_type]
                }
            })
    
    if requests:
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
```

---

## FILE DISCOVERY & GLOB PATTERNS

Support flexible file input:
```python
def discover_markdown_files(patterns):
    """
    Accept glob patterns like: *.md, docs/*.md, chapter*.md
    """
    import glob
    
    files = []
    for pattern in patterns:
        matched = glob.glob(pattern, recursive=True)
        files.extend(matched)
    
    if not files:
        logger.error(f"No markdown files found matching: {patterns}")
        exit(1)
    
    return sorted(files)
```

---

## ERROR HANDLING & LOGGING

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use throughout:
# logger.info(f"Converting {file}...")
# logger.error(f"Failed to process {file}: {str(e)}")
# logger.warning("Token expired, re-authenticating...")
```

**Error cases to handle:**
- Missing `.env` or credentials
- Invalid markdown file path
- Google API rate limits (add retry logic)
- Invalid Google Drive folder ID
- File encoding issues (default UTF-8)

---

## DELIVERABLES

### Required Files:

1. **`md2gdocs.py`** (main script)
   - All functions listed
   - ~400-500 lines total
   - Docstrings for all functions

2. **`.env.example`** (template for secrets)
   ```
   GOOGLE_CLIENT_ID=your-client-id-here
   GOOGLE_CLIENT_SECRET=your-client-secret-here
   TEMPLATE_DOC_ID=your-template-doc-id-here-optional
   OUTPUT_FOLDER_ID=your-output-folder-id-here-optional
   ```

3. **`requirements.txt`**
   ```
   google-api-python-client==1.12.5
   google-auth-oauthlib==1.2.1
   google-auth-httplib2==0.2.0
   python-dotenv==1.0.0
   ```

4. **`.gitignore`**
   ```
   .env
   token.json
   client_secret.json
   __pycache__/
   *.pyc
   .DS_Store
   ```

5. **`README.md`**
   - Setup instructions
   - Usage examples
   - Secret management guide

---

## SUCCESS CRITERIA

- [ ] Single file converts to Google Doc
- [ ] Multiple files → single-tabs mode (1 doc with tabs)
- [ ] Multiple files → multi-docs mode (separate docs)
- [ ] Template support works
- [ ] Heading markdown → Google Docs heading styles
- [ ] Bold/italic/code formatting applied
- [ ] Glob patterns work
- [ ] Secrets load from env vars first, then .env, then error
- [ ] OAuth2 token caches (no browser on second run)
- [ ] Works on Windows and Linux
- [ ] No external markdown libraries (regex only)
- [ ] Only 4 required dependencies
- [ ] Error messages clear and actionable
- [ ] Code clean and documented
- [ ] No hardcoded secrets
- [ ] .gitignore protects files

---

## IMPLEMENTATION NOTES

1. **Write minimalist, readable code**
   - Avoid over-engineering
   - Clear variable names
   - Comments only where non-obvious
   - Keep functions focused (<30 lines each)

2. **Cross-platform testing**
   - Ensure path handling works on Windows
   - Test .env loading on both Windows and Linux
   - Verify environment variable fallback on both

3. **Security**
   - Never log credentials
   - Ensure token.json has restricted permissions
   - Document OAuth2 scopes in README

---

## QUICK START EXAMPLES

```bash
# Single file
python md2gdocs.py README.md

# Multiple files to single doc with tabs
python md2gdocs.py docs/*.md --mode single-tabs

# Multiple files to separate docs with template
python md2gdocs.py *.md --mode multi-docs --use-template

# Preview without creating (dry-run)
python md2gdocs.py *.md --verbose --dry-run
```

---

## BUILD THIS TOOL EXACTLY AS SPECIFIED

- Minimalist Python (only 4 dependencies)
- Windows/Linux compatible
- Production-ready code
- No unnecessary complexity
- All functions fully implemented
- Error handling included
- Clean, documented code

**Start building now!** 🚀
