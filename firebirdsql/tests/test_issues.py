import os
import sys
import firebirdsql
import unittest

class TestIssues(unittest.TestCase):
    def setUp(self):
        if sys.platform in ('win32', 'darwin'):
            fbase = os.path.abspath('.') + '/test_issues'
        else:
            import tempfile
            fbase = tempfile.mktemp()
        TEST_HOST = 'localhost'
        TEST_PORT = 3050
        TEST_DATABASE = fbase + '.fdb'
        TEST_DSN = TEST_HOST + '/' + str(TEST_PORT) + ':' + TEST_DATABASE
        TEST_USER = 'sysdba'
        TEST_PASS = 'masterkey'
        self.connection = firebirdsql.create_database(dsn=TEST_DSN,
                            user=TEST_USER, password=TEST_PASS, page_size=2<<13)

    def test_issue_39(self):
        """
        .description attribute should be None when .execute has not run yet
        """
        cur = self.connection.cursor()
        self.assertEqual(None, cur.description)


    def test_issue_40(self):
        cur = self.connection.cursor()
        