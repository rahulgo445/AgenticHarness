import unittest
import subprocess
import tempfile
import os
import sys

class TestTaskman(unittest.TestCase):
    def setUp(self):
        self.temp_fd, self.temp_path = tempfile.mkstemp()
        os.close(self.temp_fd)
        self.env = os.environ.copy()
        self.env["TASKMAN_STORE"] = self.temp_path
        self.script_path = os.path.join(os.path.dirname(__file__), "taskman.py")

    def tearDown(self):
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)

    def run_cmd(self, *args):
        cmd = [sys.executable, self.script_path] + list(args)
        result = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        return result

    def test_01_list_empty(self):
        res = self.run_cmd("list")
        self.assertEqual(res.returncode, 0)
        self.assertIn("No tasks found.", res.stdout)

    def test_02_add_task(self):
        res = self.run_cmd("add", "Buy milk")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Added task 1: Buy milk", res.stdout)

    def test_03_list_tasks(self):
        self.run_cmd("add", "Buy milk")
        res = self.run_cmd("list")
        self.assertEqual(res.returncode, 0)
        self.assertIn("ID", res.stdout)
        self.assertIn("STATUS", res.stdout)
        self.assertIn("TITLE", res.stdout)
        self.assertIn("1  | pending | Buy milk", res.stdout)

    def test_04_add_multiple_tasks(self):
        self.run_cmd("add", "Draft Q3 marketing report")
        self.run_cmd("add", "Schedule dentist appointment")
        res = self.run_cmd("list")
        self.assertIn("1  | pending | Draft Q3 marketing report", res.stdout)
        self.assertIn("2  | pending | Schedule dentist appointment", res.stdout)

    def test_05_done_existing_task(self):
        self.run_cmd("add", "Draft Q3 marketing report")
        res = self.run_cmd("done", "1")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Task 1 marked as done.", res.stdout)
        list_res = self.run_cmd("list")
        self.assertIn("1  | done   | Draft Q3 marketing report", list_res.stdout)

    def test_06_done_nonexistent_task(self):
        res = self.run_cmd("done", "99")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Task 99 not found.", res.stderr)

    def test_07_rm_existing_task(self):
        self.run_cmd("add", "Draft Q3 marketing report")
        res = self.run_cmd("rm", "1")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Task 1 removed.", res.stdout)
        list_res = self.run_cmd("list")
        self.assertIn("No tasks found.", list_res.stdout)

    def test_08_rm_nonexistent_task(self):
        res = self.run_cmd("rm", "99")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Task 99 not found.", res.stderr)

    def test_09_stats_empty(self):
        res = self.run_cmd("stats")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Total:   0", res.stdout)
        self.assertIn("Pending: 0", res.stdout)
        self.assertIn("Done:    0", res.stdout)

    def test_10_stats_mixed(self):
        self.run_cmd("add", "Draft Q3 marketing report")
        self.run_cmd("add", "Schedule dentist appointment")
        self.run_cmd("done", "1")
        res = self.run_cmd("stats")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Total:   2", res.stdout)
        self.assertIn("Pending: 1", res.stdout)
        self.assertIn("Done:    1", res.stdout)

    def test_11_help_text(self):
        res = self.run_cmd("-h")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Taskman: A simple, file-backed CLI task manager.", res.stdout)
        self.assertIn("add", res.stdout)
        self.assertIn("list", res.stdout)
        self.assertIn("done", res.stdout)
        self.assertIn("rm", res.stdout)
        self.assertIn("stats", res.stdout)
        self.assertIn("export", res.stdout)
        self.assertIn("verify", res.stdout)

    def test_12_export_and_verify(self):
        self.run_cmd("add", "Draft Q3 marketing report")
        html_fd, html_path = tempfile.mkstemp(suffix=".html")
        os.close(html_fd)
        try:
            res_export = self.run_cmd("export", html_path)
            self.assertEqual(res_export.returncode, 0)
            self.assertIn("Exported dashboard to", res_export.stdout)
            
            res_verify = self.run_cmd("verify", html_path)
            self.assertEqual(res_verify.returncode, 0)
            self.assertIn("Self-review passed!", res_verify.stdout)
        finally:
            if os.path.exists(html_path):
                os.remove(html_path)

if __name__ == "__main__":
    unittest.main()
