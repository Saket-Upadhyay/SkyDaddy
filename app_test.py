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

import unittest
from app import skydaddy
import os


class TestHash(unittest.TestCase):
    # Testing Hash Function
    def test_hash(self):
        self.assertEqual(skydaddy.gethash("app/tests/hashtestfile5M", "sha1file") \
                         , "5bd40acb51a030a338ec4fbcd0e814c8aa774573")
        self.assertEqual(skydaddy.gethash("app/tests/hashtestfile19M", "sha1file") \
                         , "e629195b8667a1448077028ee679fb4561cc4f46")

    # Testing ALLOWED_EXT check
    def test_allowedext(self):
        for ext in skydaddy.ALLOWED_EXT:
            self.assertFalse(skydaddy.allowed_file(str(os.urandom(16))))
            self.assertTrue(skydaddy.allowed_file(str(os.urandom(16)) + "." + ext))
