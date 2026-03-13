#!/usr/bin/env python3
"""
Test script to verify Markdown parsing functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from md2gdocs import parse_markdown

def test_markdown_parsing():
    """Test the Markdown parsing with various elements"""
    
    # Test Markdown with headings, paragraphs, links, and formatting
    test_md = """
# Main Heading

This is a paragraph with some **bold text** and *italic text*.

## Subheading

Here's a link: [Google](https://www.google.com)

And some inline `code`.

### Sub-subheading

- List item 1
- List item 2
- List item 3

```
# Code block
print("Hello World")
```

Another paragraph with [another link](https://example.com).
"""

    print("Testing Markdown parsing...")
    print("Input Markdown:")
    print(test_md)
    print("\n" + "="*50 + "\n")
    
    try:
        requests = parse_markdown(test_md)
        print(f"Generated {len(requests)} requests:")
        
        for i, request in enumerate(requests):
            request_type = list(request.keys())[0]
            request_data = request[request_type]
            print(f"\nRequest {i+1}: {request_type}")
            print(f"  Data: {request_data}")
        
        print(f"\n✅ Successfully parsed Markdown into {len(requests)} requests")
        return True
        
    except Exception as e:
        print(f"❌ Error parsing Markdown: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_markdown_parsing()
    sys.exit(0 if success else 1)