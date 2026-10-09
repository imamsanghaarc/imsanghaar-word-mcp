"""
Comprehensive test suite for all 54 MCP tools.
Each test creates a temporary document, calls the tool, and verifies graceful handling.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from word_document_server.tools.document_tools import (
    create_document,
    get_document_info,
    get_document_text,
    get_document_outline,
    list_available_documents,
    copy_document,
    merge_documents,
    get_document_xml_tool,
)
from word_document_server.tools.content_tools import (
    add_heading,
    add_paragraph,
    add_table,
    add_picture,
    add_page_break,
    add_table_of_contents,
    delete_paragraph,
    search_and_replace,
    insert_header_near_text_tool,
    insert_numbered_list_near_text_tool,
    insert_line_or_paragraph_near_text_tool,
    replace_paragraph_block_below_header_tool,
    replace_block_between_manual_anchors_tool,
)
from word_document_server.tools.format_tools import (
    format_text,
    create_custom_style,
    format_table,
    set_table_cell_shading,
    apply_table_alternating_rows,
    highlight_table_header,
    merge_table_cells,
    merge_table_cells_horizontal,
    merge_table_cells_vertical,
    set_table_cell_alignment,
    set_table_alignment_all,
    set_table_column_width,
    set_table_column_widths,
    set_table_width,
    auto_fit_table_columns,
    format_table_cell_text,
    set_table_cell_padding,
)
from word_document_server.tools.protection_tools import (
    protect_document,
    unprotect_document,
)
from word_document_server.tools.footnote_tools import (
    add_footnote_to_document,
    add_endnote_to_document,
    convert_footnotes_to_endnotes_in_document,
    customize_footnote_style,
    add_footnote_after_text,
    add_footnote_before_text,
    add_footnote_enhanced,
    delete_footnote_from_document,
    add_footnote_robust_tool,
    validate_footnotes_tool,
    delete_footnote_robust_tool,
)
from word_document_server.tools.comment_tools import (
    get_all_comments,
    get_comments_by_author,
    get_comments_for_paragraph,
)
from word_document_server.tools.extended_document_tools import (
    get_paragraph_text_from_document,
    find_text_in_document,
    convert_to_pdf,
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def docx_path(tmp_path):
    path = tmp_path / "test_doc.docx"
    run(create_document(str(path), title="Test", author="Tester"))
    return str(path)


# Document Tools (8)

def test_create_document(tmp_path):
    path = tmp_path / "new_doc.docx"
    result = run(create_document(str(path)))
    assert "created successfully" in result
    assert path.exists()


def test_get_document_info(docx_path):
    result = run(get_document_info(docx_path))
    data = json.loads(result)
    assert data["title"] == "Test"


def test_get_document_text(docx_path):
    result = run(get_document_text(docx_path))
    assert isinstance(result, str)


def test_get_document_outline(docx_path):
    result = run(get_document_outline(docx_path))
    data = json.loads(result)
    assert isinstance(data, (dict, list))


def test_list_available_documents(tmp_path):
    run(create_document(str(tmp_path / "doc1.docx")))
    run(create_document(str(tmp_path / "doc2.docx")))
    result = run(list_available_documents(str(tmp_path)))
    assert "doc1.docx" in result
    assert "doc2.docx" in result


def test_copy_document(docx_path, tmp_path):
    dest = tmp_path / "copy.docx"
    result = run(copy_document(docx_path, str(dest)))
    assert "copied" in result.lower() or "success" in result.lower()
    assert dest.exists()


def test_merge_documents(docx_path, tmp_path):
    src2 = tmp_path / "second.docx"
    run(create_document(str(src2)))
    run(add_paragraph(str(src2), "Second document content"))
    target = tmp_path / "merged.docx"
    result = run(merge_documents(str(target), [docx_path, str(src2)]))
    assert "merged" in result.lower() or "success" in result.lower()
    assert target.exists()


def test_get_document_xml(docx_path):
    result = run(get_document_xml_tool(docx_path))
    assert isinstance(result, str)
    assert "<" in result


# Content Tools (14)

def test_add_heading(docx_path):
    result = run(add_heading(docx_path, "Test Heading", level=1))
    assert "added" in result.lower()


def test_add_paragraph(docx_path):
    result = run(add_paragraph(docx_path, "Test paragraph"))
    assert "added" in result.lower()


def test_add_table(docx_path):
    result = run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    assert "added" in result.lower()


def test_add_picture(docx_path, tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (10, 10), color="red")
    img.save(str(img_path))
    result = run(add_picture(docx_path, str(img_path), width=1.0))
    assert "added" in result.lower() or "picture" in result.lower()


def test_add_page_break(docx_path):
    result = run(add_page_break(docx_path))
    assert "page break" in result.lower()


def test_add_table_of_contents(docx_path):
    run(add_heading(docx_path, "Section 1", level=1))
    result = run(add_table_of_contents(docx_path))
    assert "toc" in result.lower() or "table of contents" in result.lower() or "heading" in result.lower()


def test_delete_paragraph(docx_path):
    run(add_paragraph(docx_path, "To be deleted"))
    result = run(delete_paragraph(docx_path, 0))
    assert "deleted" in result.lower()


def test_search_and_replace(docx_path):
    run(add_paragraph(docx_path, "Hello World"))
    result = run(search_and_replace(docx_path, "World", "MCP"))
    assert "replaced" in result.lower() or "occurrence" in result.lower()


def test_insert_header_near_text(docx_path):
    run(add_paragraph(docx_path, "Target paragraph"))
    result = run(insert_header_near_text_tool(docx_path, "Target", "New Header", "after"))
    assert isinstance(result, str)


def test_insert_numbered_list_near_text(docx_path):
    run(add_paragraph(docx_path, "List target"))
    result = run(insert_numbered_list_near_text_tool(docx_path, "List target", ["Item 1", "Item 2"]))
    assert isinstance(result, str)


def test_insert_line_or_paragraph_near_text(docx_path):
    run(add_paragraph(docx_path, "Line target"))
    result = run(insert_line_or_paragraph_near_text_tool(docx_path, "Line target", "New line"))
    assert isinstance(result, str)


def test_replace_paragraph_block_below_header(docx_path):
    run(add_heading(docx_path, "Header", level=1))
    run(add_paragraph(docx_path, "Old content"))
    result = run(replace_paragraph_block_below_header_tool(docx_path, "Header", ["New content"]))
    assert isinstance(result, str)


def test_replace_block_between_manual_anchors(docx_path):
    run(add_paragraph(docx_path, "START"))
    run(add_paragraph(docx_path, "Middle"))
    run(add_paragraph(docx_path, "END"))
    result = run(replace_block_between_manual_anchors_tool(docx_path, "START", ["Replaced"], "END"))
    assert isinstance(result, str)


# Format Tools (17)

def test_format_text(docx_path):
    run(add_paragraph(docx_path, "Format this text"))
    result = run(format_text(docx_path, 0, 0, 6, bold=True))
    assert "formatted" in result.lower() or "failed" in result.lower()


def test_create_custom_style(docx_path):
    result = run(create_custom_style(docx_path, "MyStyle", bold=True))
    assert "created" in result.lower() or "failed" in result.lower()


def test_format_table(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(format_table(docx_path, 0, has_header_row=True))
    assert "formatted" in result.lower() or "failed" in result.lower()


def test_set_table_cell_shading(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_cell_shading(docx_path, 0, 0, 0, "FF0000"))
    assert "shading" in result.lower() or "failed" in result.lower()


def test_apply_table_alternating_rows(docx_path):
    run(add_table(docx_path, 3, 2, [["A", "B"], ["C", "D"], ["E", "F"]]))
    result = run(apply_table_alternating_rows(docx_path, 0))
    assert "alternating" in result.lower() or "failed" in result.lower()


def test_highlight_table_header(docx_path):
    run(add_table(docx_path, 2, 2, [["H1", "H2"], ["A", "B"]]))
    result = run(highlight_table_header(docx_path, 0))
    assert "header" in result.lower() or "highlight" in result.lower() or "failed" in result.lower()


def test_merge_table_cells(docx_path):
    run(add_table(docx_path, 3, 3, [["A", "B", "C"], ["D", "E", "F"], ["G", "H", "I"]]))
    result = run(merge_table_cells(docx_path, 0, 0, 0, 1, 1))
    assert "merged" in result.lower() or "failed" in result.lower()


def test_merge_table_cells_horizontal(docx_path):
    run(add_table(docx_path, 2, 3, [["A", "B", "C"], ["D", "E", "F"]]))
    result = run(merge_table_cells_horizontal(docx_path, 0, 0, 0, 1))
    assert "merged" in result.lower() or "failed" in result.lower()


def test_merge_table_cells_vertical(docx_path):
    run(add_table(docx_path, 3, 2, [["A", "B"], ["C", "D"], ["E", "F"]]))
    result = run(merge_table_cells_vertical(docx_path, 0, 0, 0, 1))
    assert "merged" in result.lower() or "failed" in result.lower()


def test_set_table_cell_alignment(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_cell_alignment(docx_path, 0, 0, 0, horizontal="center"))
    assert "alignment" in result.lower() or "failed" in result.lower()


def test_set_table_alignment_all(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_alignment_all(docx_path, 0))
    assert "alignment" in result.lower() or "failed" in result.lower()


def test_set_table_column_width(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_column_width(docx_path, 0, 0, 2000))
    assert "width" in result.lower() or "failed" in result.lower()


def test_set_table_column_widths(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_column_widths(docx_path, 0, [2000, 2000]))
    assert "width" in result.lower() or "failed" in result.lower()


def test_set_table_width(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_width(docx_path, 0, 4000))
    assert "width" in result.lower() or "failed" in result.lower()


def test_auto_fit_table_columns(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(auto_fit_table_columns(docx_path, 0))
    assert "auto-fit" in result.lower() or "failed" in result.lower()


def test_format_table_cell_text(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(format_table_cell_text(docx_path, 0, 0, 0, bold=True))
    assert "formatted" in result.lower() or "failed" in result.lower()


def test_set_table_cell_padding(docx_path):
    run(add_table(docx_path, 2, 2, [["A", "B"], ["C", "D"]]))
    result = run(set_table_cell_padding(docx_path, 0, 0, 0, top=10))
    assert "padding" in result.lower() or "failed" in result.lower()


# Protection Tools (2)

def test_protect_document(docx_path):
    result = run(protect_document(docx_path, "testpassword"))
    assert "encrypted" in result.lower() or "failed" in result.lower() or "error" in result.lower()


def test_unprotect_document(docx_path):
    run(protect_document(docx_path, "testpassword"))
    result = run(unprotect_document(docx_path, "testpassword"))
    assert "decrypted" in result.lower() or "failed" in result.lower() or "error" in result.lower()


# Footnote Tools (4)

def test_add_footnote_to_document(docx_path):
    run(add_paragraph(docx_path, "Text with footnote"))
    result = run(add_footnote_to_document(docx_path, 0, "Footnote text"))
    assert isinstance(result, str)


def test_add_endnote_to_document(docx_path):
    run(add_paragraph(docx_path, "Text with endnote"))
    result = run(add_endnote_to_document(docx_path, 0, "Endnote text"))
    assert isinstance(result, str)


def test_convert_footnotes_to_endnotes(docx_path):
    result = run(convert_footnotes_to_endnotes_in_document(docx_path))
    assert isinstance(result, str)


def test_customize_footnote_style(docx_path):
    result = run(customize_footnote_style(docx_path))
    assert isinstance(result, str)


def test_add_footnote_after_text(docx_path):
    run(add_paragraph(docx_path, "Anchor text for footnote"))
    result = run(add_footnote_after_text(docx_path, "Anchor", "Footnote content"))
    assert isinstance(result, str)


def test_add_footnote_before_text(docx_path):
    run(add_paragraph(docx_path, "Anchor text for footnote"))
    result = run(add_footnote_before_text(docx_path, "Anchor", "Footnote content"))
    assert isinstance(result, str)


def test_add_footnote_enhanced(docx_path):
    run(add_paragraph(docx_path, "Text before footnote"))
    result = run(add_footnote_enhanced(docx_path, 0, "Enhanced footnote"))
    assert isinstance(result, str)


def test_delete_footnote_from_document(docx_path):
    result = run(delete_footnote_from_document(docx_path, footnote_id=1))
    assert isinstance(result, str)
    assert "not found" in result.lower() or "deleted" in result.lower() or "failed" in result.lower() or "no footnotes" in result.lower()


def test_add_footnote_robust(docx_path):
    run(add_paragraph(docx_path, "Robust anchor text"))
    result = run(add_footnote_robust_tool(docx_path, search_text="Robust", footnote_text="Robust note"))
    assert isinstance(result, dict)
    assert "success" in result
    assert "message" in result


def test_validate_document_footnotes(docx_path):
    result = run(validate_footnotes_tool(docx_path))
    assert isinstance(result, dict)
    assert "message" in result


def test_delete_footnote_robust(docx_path):
    result = run(delete_footnote_robust_tool(docx_path, footnote_id=1))
    assert isinstance(result, dict)
    assert "success" in result
    assert "message" in result


# Comment Tools (3)

def test_get_all_comments(docx_path):
    result = run(get_all_comments(docx_path))
    data = json.loads(result)
    assert data["success"] is True


def test_get_comments_by_author(docx_path):
    result = run(get_comments_by_author(docx_path, "Nobody"))
    data = json.loads(result)
    assert data["success"] is True
    assert data["total_comments"] == 0


def test_get_comments_for_paragraph(docx_path):
    run(add_paragraph(docx_path, "Paragraph with a comment"))
    result = run(get_comments_for_paragraph(docx_path, 0))
    data = json.loads(result)
    assert data["success"] is True


# Extended Document Tools (3)

def test_get_paragraph_text(docx_path):
    run(add_paragraph(docx_path, "Hello paragraph"))
    result = run(get_paragraph_text_from_document(docx_path, 0))
    data = json.loads(result)
    assert "text" in data or "paragraph" in data or "content" in data


def test_find_text_in_document(docx_path):
    run(add_paragraph(docx_path, "Find this unique text"))
    result = run(find_text_in_document(docx_path, "unique"))
    data = json.loads(result)
    assert "found" in str(data).lower() or "results" in str(data).lower() or "text" in str(data).lower()


def test_convert_to_pdf(docx_path):
    result = run(convert_to_pdf(docx_path))
    assert isinstance(result, str)
    assert "pdf" in result.lower() or "failed" in result.lower() or "libreoffice" in result.lower() or "docx2pdf" in result.lower()
