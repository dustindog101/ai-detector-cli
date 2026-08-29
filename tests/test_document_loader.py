"""
Tests for Document Loader Seam (load_document).
"""

import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ai_detector_cli.cli import load_document

class TestDocumentLoader(unittest.TestCase):
    def setUp(self):
        self.samples_dir = os.path.join(current_dir, "samples")

    def test_load_text_file(self):
        path = os.path.join(self.samples_dir, "ai_sample.txt")
        text = load_document(path)
        self.assertGreater(len(text), 20)
        self.assertIn("relational databases", text)

    def test_load_html_document(self):
        path = os.path.join(self.samples_dir, "test_doc.html")
        text = load_document(path)
        self.assertGreater(len(text), 20)
        self.assertIn("School Discussion Post", text)
        self.assertNotIn("<html>", text)
        self.assertNotIn("<p>", text)

    def test_load_missing_file_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            load_document("/non/existent/path/paper.docx")

if __name__ == "__main__":
    unittest.main()
