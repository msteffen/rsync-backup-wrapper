#!/usr/bin/python
import unittest

from backup import *

import os
from os.path import *
from subprocess import *

class TestBackup(unittest.TestCase):
  """
    This isn't really a unit test, (it creates directories runs the whole
    script, and the inspects the files on disk) but the whole thing is just
    an rsync wrapper anyway.
  """

  def setUp(self):
    self.start_dir = os.getcwd()
    self.tmpd = check_output(["mktemp", "-d", "./tmp.rsync_test.XXXXXXXXX"]).strip()
    os.chdir(self.tmpd);

  def tearDown(self):
    os.chdir(self.start_dir)
    call(["rm", "-r", self.tmpd])
    
  def test_new_backup(self):
    """
      Attemptes to successfully run the backup script once, end-to-end.

      Note that the test files all have spaces in the names (since rsync has
      given me issues with that)
    """
    os.mkdir("source dir")

    # Populate fake file contents
    for f in ["file one", "file two", "file three"]:
      open(join("source dir", f), "w").writelines([f + " data\n"] * 3)
    
    b = Backup(src="source dir", dst="backup dir")
    b.backup_with_rsync()

    ### Inspect output
    # Check contents of backup directory
    self.assertEqual(set(os.listdir("backup dir")),
        set(["file one", "file two", "file three",
             "BACKUP_DONE", "rsync_backup.log"]))
    # Check contents match
    for f in ["file one", "file two", "file three"]:
      self.assertEqual(open(join("source dir", f), "r").readlines(),
          open(join("backup dir", f), "r").readlines())

  def test_existing_backup(self):
    """
      Attemptes to successfully run the backup script once, end-to-end.

      Note that the test files all have spaces in the names.
    """
    # These deliberately have spaces to make sure rsync can handle them.
    # Rsync does additional processing of arguments and needs spaces to be
    # escaped.
    os.mkdir("source dir")
    os.mkdir("01-Jan-2000")

    # Populate fake file contents
    open(join("source dir", "same contents"),      "w").writelines(["SAME\n"]       * 3)
    open(join("source dir", "different contents"), "w").writelines(["source dir\n"] * 3)
    open(join("source dir", "source only"),        "w").writelines(["source dir\n"] * 3)

    open(join("01-Jan-2000", "same contents"), "w").writelines(["SAME" + "\n"]*3)
    open(join("01-Jan-2000", "different contents"), "w").writelines(["old dest dir" + "\n"]*3)
    open(join("01-Jan-2000", "old dest only"),      "w").writelines(["old dest dir" + "\n"]*3)

    b = Backup.FromBackupDrive(src="source dir", drive="./")
    b.backup_with_rsync()

    ### Inspect output
    dirs = os.listdir(".")
    self.assertEqual(len(dirs), 3)

    # cd to backup dir, and inspect files there
    for d in dirs:
      if d in ["source dir", "01-Jan-2000"]: continue
      os.chdir(d)

    # Check contents of backup directory
    dirs = os.listdir(".")
    self.assertEqual(set(dirs),
        set(["same contents", "different contents", "source only",
             "BACKUP_DONE", "rsync_backup.log"]))

    # Make sure rsync linked files whose contents didn't change from source to
    # old_dest (by comparing inode numbers)
    self.assertEqual(
        os.stat("same contents").st_ino,
        os.stat(join("..", "01-Jan-2000", "same contents")).st_ino)
    # Make sure files that *did* change are copies from source
    self.assertEqual(
        open("different contents", "r").readlines(),
        open(join("..", "source dir", "different contents"), "r").readlines())
    self.assertEqual(
        open("different contents", "r").readlines(),
        open(join("..", "source dir", "different contents"), "r").readlines())

if __name__ == "__main__":
  unittest.main()
