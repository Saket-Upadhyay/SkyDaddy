"""
Pytest module for testing hashing and file validation in skydaddy

MIT License

Copyright (c) 2023 Saket Upadhyay

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from app import ALLOWED_EXT, allowed_file, get_sha256


class TestHash(unittest.TestCase):
    def test_hash(self):
        content = b"skydaddy test content"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            self.assertEqual(get_sha256(tmp), expected)
        finally:
            tmp.unlink(missing_ok=True)

    def test_hash_large(self):
        content = os.urandom(200_000)
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            self.assertEqual(get_sha256(tmp), expected)
        finally:
            tmp.unlink(missing_ok=True)


class TestAllowedExt(unittest.TestCase):
    def test_allowed_extensions(self):
        for ext in ALLOWED_EXT:
            self.assertTrue(allowed_file("somefile." + ext))
            self.assertTrue(allowed_file("somefile." + ext.upper()))

    def test_blocked_extensions(self):
        for ext in ("exe", "sh", "bat", "js", "php", "py"):
            self.assertFalse(allowed_file("malicious." + ext))

    def test_no_extension(self):
        self.assertFalse(allowed_file("nodotfile"))

    def test_empty_string(self):
        self.assertFalse(allowed_file(""))
