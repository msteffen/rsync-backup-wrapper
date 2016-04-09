#!/usr/bin/python
import unittest

from backup_lib import *

import os
from os.path import isdir, isfile, join, exists
import subprocess as proc

def put(output_file, lines):
  """
    Convenience function to succinctly write "lines" to "output_file", for
    populating test files
  """
  with open(output_file, "w") as outf:
    outf.writelines(lines)

class TestBackup(unittest.TestCase):
  """
    This isn't really a unit test, (it creates directories, runs the whole
    script, and the inspects the files on disk) but the whole thing is just
    an rsync wrapper anyway.
  """
  _test_files = ["regular_file", "~chars file", ".hidden file", "-flag file"]
  _test_dirs = ["regular_dir", "~chars dir", ".hidden dir", "-flag dir" ]

  def setUp(self):
    # Create tmp dir for the test to take place in
    self.start_dir = os.getcwd()
    self.tmpd = proc.check_output(
        ["mktemp", "-d", "./tmp.rsync_test.XXXXXXXXX"]).strip()
    os.chdir(self.tmpd);

  def tearDown(self):
    os.chdir(self.start_dir)
    proc.check_output(["rm", "-r", self.tmpd])

  def createDefaultSourceDir(self, root_dir):
    """
      Utility method to create a source dir with lots of test files and
      directories (including many with weird names)
    """
    os.mkdir(root_dir)
    for d in self._test_dirs:
      os.mkdir(join(root_dir, d))
      for f in self._test_files:
        put(join(root_dir, d, f), [join(d,f) + " data\n"] * 3)
    for f in self._test_files:
      put(join(root_dir, f), [f + " data\n"] * 3)

  def assertBackupSame(self, source, backup, extra_files=[]):
    """
      Utility method for testing whether source and backup are
      recursively equal.
    """
    self.assertEqual(
        (isdir(source), isfile(source)),
        (isdir(backup), isfile(backup)),
        "different file types. source: {}, dst: {}".format(source, backup))
    if isdir(source):
      # Make sure contents of directories are the same
      existing_files = set(os.listdir(source))
      self.assertEqual(
          set(os.listdir(backup)),
          existing_files | set(extra_files),
          "Dir contents not equal. source: {}:\n{}\ndst: {}:\n{}"
              .format(source, existing_files | set(extra_files),
                      backup, set(os.listdir(backup))))
      # recursively compare subfiles and subdirectories
      for f in existing_files:
        self.assertBackupSame(join(source, f), join(backup, f), [])
    elif isfile(source):
      with open(source, "r") as src, open(backup, "r") as dst:
        self.assertEqual(src.readlines(), dst.readlines(),
            "file contents not equal. source: {}, dst: {}".format(src, dst))
    else:
      raise ValueError("Source file {} is neither a file nor a directory. Not "
          + "sure how to compare...".format(source))

  def test_new_backup(self):
    """
      Runs the backup script, explicitly setting `src` and `dst`.

      Note that the test files all have spaces in the names (since rsync has
      given me issues with that)
    """
    self.createDefaultSourceDir("source dir")
    b = Backup(src="source dir", dst="backup dir")
    b.run_rsync_cmds()
    # Inspect output
    self.assertBackupSame("source dir", "backup dir",
      extra_files = ["rsync_backup.log", Backup._DONE_FILE])

  def test_new_backup_to_drive(self):
    """
      Runs the backup script, using FromBackupDrive (i.e. --backup_drive),
      but without any previous backups present in the `drive` directory.
    """
    self.createDefaultSourceDir("source dir")
    b = Backup.FromBackupDrive(src="source dir", drive=".")
    b.run_rsync_cmds()
    # Inspect output
    for d in os.listdir("."):
      if d != "source dir": backup_dir = d
    self.assertBackupSame("source dir", backup_dir,
      extra_files = ["rsync_backup.log", Backup._DONE_FILE])

  def test_existing_backup(self):
    """
      Runs the backup script, using FromBackupDrive, against a simulated
      previous backup. The inode values of the created files are inspected to
      make sure that unchanged files are linked instead of copied.
    """
    # These deliberately have spaces to make sure rsync can handle them.
    # Rsync does additional processing of arguments and needs spaces to be
    # escaped.
    os.mkdir("source dir")
    os.mkdir("30-Jan-2000")

    # Populate fake file contents
    put("source dir/same contents", ["SAME\n"] * 3)
    put("source dir/diff contents", ["source dir\n"] * 3)
    put("source dir/source only", ["source dir\n"] * 3)
    put("30-Jan-2000/same contents", ["SAME\n"] * 3)
    put("30-Jan-2000/diff contents", ["old dir\n"] * 3)
    put("30-Jan-2000/old dest only", ["old dir\n"] * 3)

    # Take backup
    b = Backup.FromBackupDrive(src="source dir", drive=".")
    b.run_rsync_cmds()

    ### Inspect output
    self.assertEqual(len(os.listdir(".")), 3)
    # cd to backup dir, and inspect files there
    for d in os.listdir("."):
      if d in ["source dir", "30-Jan-2000"]: continue
      backup_dir = d

    # Check contents of backup directory
    self.assertBackupSame("source dir", backup_dir,
      extra_files = ["rsync_backup.log", Backup._DONE_FILE])
    # Make sure rsync linked files whose contents didn't change from source to
    # old_dest (by comparing inode numbers)
    self.assertEqual(
        os.stat(join(backup_dir, "same contents")).st_ino,
        os.stat("30-Jan-2000/same contents").st_ino)

  def test_ordered_backup(self):
    """
      Runs the backup script, specifying the first files/directories to be
      backed up. Make sure that the output is identical to the source.

      Note that this test includes both source files and source directories,
      since rsync is invoked multiple times, and we want to test that both such
      cases are handled correctly.
    """
    self.createDefaultSourceDir("source dir")
    b = Backup(src="source dir", dst="backup dir", backup_order=[
      join(self._test_dirs[0], self._test_files[0]),
      self._test_dirs[0], self._test_files[0],
      self._test_dirs[1], self._test_files[1],
      "..."])
    b.run_rsync_cmds()
    ### Inspect output
    self.assertBackupSame("source dir", "backup dir",
      extra_files = ["rsync_backup.log", Backup._DONE_FILE])

  def test_ordered_backup_with_prev(self):
    """ Similar to test_existing_backup, but tests backup_order option """
    os.mkdir("source dir")
    os.mkdir("30-Jan-2000")
    put("source dir/same contents", ["SAME\n"] * 3)
    put("source dir/diff contents", ["source dir\n"] * 3)
    put("source dir/source only", ["source dir\n"] * 3)
    put("30-Jan-2000/same contents", ["SAME\n"] * 3)
    put("30-Jan-2000/diff contents", ["old dir\n"] * 3)
    put("30-Jan-2000/old dest only", ["old dir\n"] * 3)

    # Take backup
    b = Backup.FromBackupDrive(src="source dir", drive=".",
                               backup_order=["diff contents", "..."])
    b.run_rsync_cmds()

    ### Inspect output
    self.assertEqual(len(os.listdir(".")), 3)
    # cd to backup dir, and inspect files there
    for d in os.listdir("."):
      if d in ["source dir", "30-Jan-2000"]: continue
      backup_dir = d

    # Check contents of backup directory
    self.assertBackupSame("source dir", backup_dir,
      extra_files = ["rsync_backup.log", Backup._DONE_FILE])
    # Make sure rsync linked files whose contents didn't change from source to
    # old_dest (by comparing inode numbers)
    self.assertEqual(
        os.stat(join(backup_dir, "same contents")).st_ino,
        os.stat("30-Jan-2000/same contents").st_ino)

  def test_partial_backup(self):
    """
      Runs the backup script, and only backup a few files/directories in the
      source directory. Make sure those are copied correctly.

      Test both with and without prev_backup specified
    """
    self.createDefaultSourceDir("source dir")
    to_back_up = [self._test_dirs[0], self._test_files[0],
                  self._test_dirs[2], self._test_files[2]]
    b = Backup(src="source dir", dst="backup dir", backup_order=to_back_up)
    b.run_rsync_cmds()
    ### Inspect output
    for f in to_back_up:
      self.assertBackupSame(join("source dir", f), join("backup dir", f))

    # Re-run test with a different subset
    proc.check_output(["rm", "-r", "backup dir"])
    to_back_up = [self._test_dirs[1], self._test_files[1],
                  self._test_dirs[3], self._test_files[3]]
    b = Backup(src="source dir", dst="backup dir", backup_order=to_back_up)
    b.run_rsync_cmds()
    ### Inspect output
    for f in to_back_up:
      self.assertBackupSame(join("source dir", f), join("backup dir", f))

if __name__ == "__main__":
  unittest.main()
