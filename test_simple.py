#!/usr/bin/env python3
"""Simple test of the parsing functionality."""

from md2gdocs import parse_markdown

# Simple test
test_md = "# Test Heading\n\nThis is a **bold** test."

print("Testing markdown parsing...")
try:
    requests = parse_markdown(test_md)
    print(f"Success! Generated {len(requests)} requests")
    
    if requests:
        print("\nFirst request:")
        print(requests[0])
        
    # Test fallback
    print("\nTesting fallback parsing...")
    from md2gdocs import parse_markdown_fallback
    fallback_requests = parse_markdown_fallback(test_md)
    print(f"Fallback generated {len(fallback_requests)} requests")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()