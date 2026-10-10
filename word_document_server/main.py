"""
Main entry point for the Word Document MCP Server.
Acts as the central controller for the MCP server that handles Word document operations.
Supports multiple transports: stdio, sse, and streamable-http using standalone FastMCP.
"""

import os
import sys
from collections import namedtuple
from dotenv import load_dotenv

# Load environment variables from .env file
print("Loading configuration from .env file...")
load_dotenv()
# Set required environment variable for FastMCP 2.8.1+
os.environ.setdefault('FASTMCP_LOG_LEVEL', 'INFO')
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from word_document_server.tools import (
    document_tools,
    content_tools,
    format_tools,
    protection_tools,
    footnote_tools,
    extended_document_tools,
    comment_tools
)
from word_document_server.tools.content_tools import replace_paragraph_block_below_header_tool
from word_document_server.tools.content_tools import replace_block_between_manual_anchors_tool

def get_transport_config():
    """
    Get transport configuration from environment variables.
    
    Returns:
        dict: Transport configuration with type, host, port, and other settings
    """
    # Default configuration
    config = {
        'transport': 'stdio',  # Default to stdio for backward compatibility
        'host': '0.0.0.0',
        'port': 8000,
        'path': '/mcp',
        'sse_path': '/sse'
    }
    
    # Override with environment variables if provided
    transport = os.getenv('MCP_TRANSPORT', 'stdio').lower()
    print(f"Transport: {transport}")
    # Validate transport type
    valid_transports = ['stdio', 'streamable-http', 'sse']
    if transport not in valid_transports:
        print(f"Warning: Invalid transport '{transport}'. Falling back to 'stdio'.")
        transport = 'stdio'
    
    config['transport'] = transport
    config['host'] = os.getenv('MCP_HOST', config['host'])
    # Use PORT from Render if available, otherwise fall back to MCP_PORT or default
    config['port'] = int(os.getenv('PORT', os.getenv('MCP_PORT', config['port'])))
    config['path'] = os.getenv('MCP_PATH', config['path'])
    config['sse_path'] = os.getenv('MCP_SSE_PATH', config['sse_path'])
    
    return config


def setup_logging(debug_mode):
    """
    Setup logging based on debug mode.
    
    Args:
        debug_mode (bool): Whether to enable debug logging
    """
    import logging
    
    if debug_mode:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        print("Debug logging enabled")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )


# Initialize FastMCP server
mcp = FastMCP("Word Document Server")


# MCP tool hint profile: the four hints that must be declared on every tool.
HintProfile = namedtuple("HintProfile", ["read_only", "destructive", "idempotent", "open_world"])

_READ_ONLY_HINTS = HintProfile(
    read_only=True,
    destructive=False,
    idempotent=True,
    open_world=False,
)

_WRITE_HINTS = HintProfile(
    read_only=False,
    destructive=True,
    idempotent=False,
    open_world=False,
)

# (public tool name, handler function, human-readable title).
# Tool names are listed explicitly so the public API surface stays greppable
# and each entry resolves to a module-level handler function.
_READ_ONLY_TOOLS = [
    # Document tools
    ("get_document_info", document_tools.get_document_info, "Get Document Info"),
    ("get_document_text", document_tools.get_document_text, "Get Document Text"),
    ("get_document_outline", document_tools.get_document_outline, "Get Document Outline"),
    ("list_available_documents", document_tools.list_available_documents, "List Available Documents"),
    ("get_document_xml", document_tools.get_document_xml_tool, "Get Document XML"),
    # Footnote tools
    ("validate_document_footnotes", footnote_tools.validate_footnotes_tool, "Validate Footnotes"),
    # Extended document tools
    ("get_paragraph_text_from_document", extended_document_tools.get_paragraph_text_from_document, "Get Paragraph Text"),
    ("find_text_in_document", extended_document_tools.find_text_in_document, "Find Text"),
    # Comment tools
    ("get_all_comments", comment_tools.get_all_comments, "Get All Comments"),
    ("get_comments_by_author", comment_tools.get_comments_by_author, "Get Comments by Author"),
    ("get_comments_for_paragraph", comment_tools.get_comments_for_paragraph, "Get Comments for Paragraph"),
]

_WRITE_TOOLS = [
    # Document tools
    ("create_document", document_tools.create_document, "Create Word Document"),
    ("copy_document", document_tools.copy_document, "Copy Word Document"),
    # Content tools
    ("insert_header_near_text", content_tools.insert_header_near_text_tool, "Insert Header Near Text"),
    ("insert_line_or_paragraph_near_text", content_tools.insert_line_or_paragraph_near_text_tool, "Insert Line Near Text"),
    ("insert_numbered_list_near_text", content_tools.insert_numbered_list_near_text_tool, "Insert List Near Text"),
    ("add_paragraph", content_tools.add_paragraph, "Add Paragraph"),
    ("add_heading", content_tools.add_heading, "Add Heading"),
    ("add_picture", content_tools.add_picture, "Add Picture"),
    ("add_table", content_tools.add_table, "Add Table"),
    ("add_page_break", content_tools.add_page_break, "Add Page Break"),
    ("delete_paragraph", content_tools.delete_paragraph, "Delete Paragraph"),
    ("search_and_replace", content_tools.search_and_replace, "Search and Replace"),
    # Format tools
    ("create_custom_style", format_tools.create_custom_style, "Create Custom Style"),
    ("format_text", format_tools.format_text, "Format Text"),
    ("format_table", format_tools.format_table, "Format Table"),
    ("set_table_cell_shading", format_tools.set_table_cell_shading, "Set Table Cell Shading"),
    ("apply_table_alternating_rows", format_tools.apply_table_alternating_rows, "Apply Alternating Row Colors"),
    ("highlight_table_header", format_tools.highlight_table_header, "Highlight Table Header"),
    ("merge_table_cells", format_tools.merge_table_cells, "Merge Table Cells"),
    ("merge_table_cells_horizontal", format_tools.merge_table_cells_horizontal, "Merge Cells Horizontally"),
    ("merge_table_cells_vertical", format_tools.merge_table_cells_vertical, "Merge Cells Vertically"),
    ("set_table_cell_alignment", format_tools.set_table_cell_alignment, "Set Cell Alignment"),
    ("set_table_alignment_all", format_tools.set_table_alignment_all, "Set Table Alignment"),
    # Protection tools
    ("protect_document", protection_tools.protect_document, "Protect Document"),
    ("unprotect_document", protection_tools.unprotect_document, "Unprotect Document"),
    # Footnote tools
    ("add_footnote_to_document", footnote_tools.add_footnote_to_document, "Add Footnote"),
    ("add_footnote_after_text", footnote_tools.add_footnote_after_text, "Add Footnote After Text"),
    ("add_footnote_before_text", footnote_tools.add_footnote_before_text, "Add Footnote Before Text"),
    ("add_footnote_enhanced", footnote_tools.add_footnote_enhanced, "Add Footnote Enhanced"),
    ("add_endnote_to_document", footnote_tools.add_endnote_to_document, "Add Endnote"),
    ("customize_footnote_style", footnote_tools.customize_footnote_style, "Customize Footnote Style"),
    ("delete_footnote_from_document", footnote_tools.delete_footnote_from_document, "Delete Footnote"),
    ("add_footnote_robust", footnote_tools.add_footnote_robust_tool, "Add Footnote Robust"),
    ("delete_footnote_robust", footnote_tools.delete_footnote_robust_tool, "Delete Footnote Robust"),
    # Extended document tools
    ("convert_to_pdf", extended_document_tools.convert_to_pdf, "Convert to PDF"),
    # Content tools
    ("replace_paragraph_block_below_header", replace_paragraph_block_below_header_tool, "Replace Block Below Header"),
    ("replace_block_between_manual_anchors", replace_block_between_manual_anchors_tool, "Replace Block Between Anchors"),
    # Format tools
    ("set_table_column_width", format_tools.set_table_column_width, "Set Column Width"),
    ("set_table_column_widths", format_tools.set_table_column_widths, "Set Column Widths"),
    ("set_table_width", format_tools.set_table_width, "Set Table Width"),
    ("auto_fit_table_columns", format_tools.auto_fit_table_columns, "Auto-Fit Table Columns"),
    ("format_table_cell_text", format_tools.format_table_cell_text, "Format Cell Text"),
    ("set_table_cell_padding", format_tools.set_table_cell_padding, "Set Cell Padding"),
]


def _register_tool(name, handler, title, hints):
    """Register a single handler function as an MCP tool."""
    mcp.tool(
        name=name,
        annotations=ToolAnnotations(
            title=title,
            read_only_hint=hints.read_only,
            destructive_hint=hints.destructive,
            idempotent_hint=hints.idempotent,
            open_world_hint=hints.open_world,
        ),
    )(handler)


def register_tools():
    """Register every tool with the MCP server.

    The decorated function is the handler itself, so tool descriptions are read
    directly from the handler docstrings and static tooling can resolve each
    tool to its implementation.
    """
    for name, handler, title in _READ_ONLY_TOOLS:
        _register_tool(name, handler, title, _READ_ONLY_HINTS)

    for name, handler, title in _WRITE_TOOLS:
        _register_tool(name, handler, title, _WRITE_HINTS)


def run_server():
    """Run the Word Document MCP Server with configurable transport."""
    # Get transport configuration
    config = get_transport_config()
    
    # Setup logging
    # setup_logging(config['debug'])
    
    # Register all tools
    register_tools()
    
    # Print startup information
    transport_type = config['transport']
    print(f"Starting Word Document MCP Server with {transport_type} transport...")
    
    # if config['debug']:
    #     print(f"Configuration: {config}")
    
    try:
        if transport_type == 'stdio':
            # Run with stdio transport (default, backward compatible)
            print("Server running on stdio transport")
            mcp.run(transport='stdio')
            
        elif transport_type == 'streamable-http':
            # Run with streamable HTTP transport
            print(f"Server running on streamable-http transport at http://{config['host']}:{config['port']}{config['path']}")
            mcp.run(
                transport='streamable-http',
                host=config['host'],
                port=config['port'],
                path=config['path']
            )
            
        elif transport_type == 'sse':
            # Run with SSE transport
            print(f"Server running on SSE transport at http://{config['host']}:{config['port']}{config['sse_path']}")
            mcp.run(
                transport='sse',
                host=config['host'],
                port=config['port'],
                path=config['sse_path']
            )
            
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        if config['debug']:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    return mcp


def main():
    """Main entry point for the server."""
    run_server()


if __name__ == "__main__":
    main()
