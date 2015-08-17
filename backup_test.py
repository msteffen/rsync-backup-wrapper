#!/usr/bin/python
import unittest

from backup import *

import os
from os.path import *
from subprocess import *

class TestBackup(unittest.TestCase):
  """
    This isn't really a unit test, (it creates directories, runs the whole
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
      Runs the backup script, explicitly setting `src` and `dst`.

      Note that the test files all have spaces in the names (since rsync has
      given me issues with that)
    """
    os.mkdir("source dir")

    # Populate fake file contents (all files have distinct contents)
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

  def test_new_backup_to_drive(self):
    """
      Runs the backup script, using FromBackupDrive (i.e. --backup_drive),
      but without any previous backups present in the `drive` directory.
    """
    os.mkdir("source dir")

    # Populate fake file contents
    for f in ["file one", "file two", "file three"]:
      open(join("source dir", f), "w").writelines([f + " data\n"] * 3)
    
    b = Backup.FromBackupDrive(src="source dir", drive=".")
    b.backup_with_rsync()

    ### Inspect output
    # Find backup directory
    for d in os.listdir("."):
      if d != "source dir": backup_dir = d

    self.assertEqual(set(os.listdir(backup_dir)),
        set(["file one", "file two", "file three",
             "BACKUP_DONE", "rsync_backup.log"]))
    # Check contents match
    for f in ["file one", "file two", "file three"]:
      self.assertEqual(open(join("source dir", f), "r").readlines(),
          open(join(backup_dir, f), "r").readlines())

  def test_existing_backup(self):
    """
      Runs the backup script, using FromBackupDrive, against a simulated previous backup.
      The inode values of the created files are inspected to make sure that unchanged
      files are linked instead of copied.
    """
    # These deliberately have spaces to make sure rsync can handle them.
    # Rsync does additional processing of arguments and needs spaces to be
    # escaped.
    os.mkdir("source dir")
    os.mkdir("30-Jan-2000")

    # Populate fake file contents
    open("source dir/same contents", "w").writelines(["SAME\n"] * 3)
    open("source dir/diff contents", "w").writelines(["source dir\n"] * 3)
    open("source dir/source only", "w").writelines(["source dir\n"] * 3)
    
    open("30-Jan-2000/same contents", "w").writelines(["SAME" + "\n"] * 3)
    open("30-Jan-2000/diff contents", "w").writelines(["old dir" + "\n"] * 3)
    open("30-Jan-2000/old dest only", "w").writelines(["old dir" + "\n"] * 3)

    b = Backup.FromBackupDrive(src="source dir", drive=".")
    b.backup_with_rsync()

    ### Inspect output
    self.assertEqual(len(os.listdir(".")), 3)
    # cd to backup dir, and inspect files there
    for d in os.listdir("."):
      if d in ["source dir", "30-Jan-2000"]: continue
      os.chdir(d)

    # Check contents of backup directory
    dirs = os.listdir(".")
    self.assertEqual(set(dirs),
        set(["same contents", "diff contents", "source only",
             "BACKUP_DONE", "rsync_backup.log"]))

    # Make sure rsync linked files whose contents didn't change from source to
    # old_dest (by comparing inode numbers)
    self.assertEqual(
        os.stat("same contents").st_ino,
        os.stat("../30-Jan-2000/same contents").st_ino)
    # Make sure files that *did* change are copies from source
    self.assertEqual(
        open("diff contents", "r").readlines(),
        open("../source dir/diff contents", "r").readlines())
    self.assertEqual(
        open("diff contents", "r").readlines(),
        open("../source dir/diff contents", "r").readlines())

if __name__ == "__main__":
  unittest.main()
