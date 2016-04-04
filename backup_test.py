#!/usr/bin/python
import unittest

from backup_lib import *

import os
from os.path import isdir, isfile, join, exists
import subprocess as proc

def is_backup_same(source, backup):
  """
    Utility method for testing whether source and backup are
    recursively equal.
  """
  if (isdir(source), isfile(source)) != (isdir(backup), isfile(backup)):
    return False
  if isdir(source):
    existing_files = set(os.listdir(source))
    if set(os.listdir(backup)) \
        !=  (existing_files | set(["rsync_backup.log"])):
      return False
    # recursively compare subfiles and subdirectories
    is_equal = True
    for f in existing_files:
      is_equal &= is_backup_same(join(source, f), join(backup, f))
    return is_equal
  elif isfile(source):
    with open(source, "r") as src, open(backup, "r") as dst:
      return src.readlines() == dst.readlines()
  else:
    raise ValueError("Source file {} is neither a file nor a directory. Not "
        + "sure how to compare...".format(source))

def put(lines, output_file):
  """ Convenience function to succinctly write "lines" to "output_file" """
  with open(output_file, "w") as outf:
    outf.writelines(lines)

class TestBackup(unittest.TestCase):
  """
    This isn't really a unit test, (it creates directories, runs the whole
    script, and the inspects the files on disk) but the whole thing is just
    an rsync wrapper anyway.
  """

  def setUp(self):
    self.start_dir = os.getcwd()
    self.tmpd = proc.check_output(
        ["mktemp", "-d", "./tmp.rsync_test.XXXXXXXXX"]).strip()
    os.chdir(self.tmpd);

  def tearDown(self):
    os.chdir(self.start_dir)
    proc.call(["rm", "-r", self.tmpd])

  def test_new_backup(self):
    """
      Runs the backup script, explicitly setting `src` and `dst`.

      Note that the test files all have spaces in the names (since rsync has
      given me issues with that)
    """
    os.mkdir("source dir")

    # Populate fake file contents (all files have distinct contents)
    for f in ["file one", "file two", "file three"]:
      put([f + " data\n"] * 3, join("source dir", f))

    b = Backup(src="source dir", dst="backup dir")
    b.run_rsync_cmd()

    ### Inspect output
    is_backup_same("source dir", "backup dir")

  def test_new_backup_to_drive(self):
    """
      Runs the backup script, using FromBackupDrive (i.e. --backup_drive),
      but without any previous backups present in the `drive` directory.
    """
    # Create source dir
    os.mkdir("source dir")
    for f in ["file one", "file two", "file three"]:
      put([f + " data\n"] * 3, join("source dir", f))

    b = Backup.FromBackupDrive(src="source dir", drive=".")
    b.run_rsync_cmd()

    ### Inspect output
    for d in os.listdir("."):
      if d != "source dir": backup_dir = d
    is_backup_same("source dir", backup_dir)

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
    put(["SAME\n"] * 3, "source dir/same contents")
    put(["source dir\n"] * 3, "source dir/diff contents")
    put(["source dir\n"] * 3, "source dir/source only")
    put(["SAME\n"] * 3, "30-Jan-2000/same contents")
    put(["old dir\n"] * 3, "30-Jan-2000/diff contents")
    put(["old dir\n"] * 3, "30-Jan-2000/old dest only")

    # Take backup
    b = Backup.FromBackupDrive(src="source dir", drive=".")
    b.run_rsync_cmd()

    ### Inspect output
    self.assertEqual(len(os.listdir(".")), 3)
    # cd to backup dir, and inspect files there
    for d in os.listdir("."):
      if d in ["source dir", "30-Jan-2000"]: continue
      backup_dir = d

    # Check contents of backup directory
    is_backup_same("source dir", backup_dir)
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
    # Create backup source
    os.mkdir("source dir")
    for d in ["dir one", "dir two", "dir three"]:
      os.mkdir(join("source dir", d))
      for f in ["inner file one", "inner file two", "inner file three"]:
        open(join("source dir", d, f), "w").writelines(
            [join(d,f) + " data\n"] * 3)
    for f in ["file one", "file two", "file three"]:
      open(join("source dir", f), "w").writelines([f + " data\n"] * 3)
    b = Backup(src="source dir", dst="backup dir", backup_targets=[
      "dir one", "file one",  "dir two", "file two", "..."])
    b.run_rsync_cmd()
    ### Inspect output
    is_backup_same("source dir", "backup dir")

    # Same test, but now it needs to work with a previous backup
    # os.mkdir("prev backup dir")
    # os.mkdir("prev backup dir/dir one")
    # open(


  def test_partial_backup(self):
    """
      Runs the backup script, and only backup a few files/directories in the
      source directory. Make sure those are copied correctly.

      Test both with and without prev_backup specified
    """

  def test_partial_backup_hidden_files(self):
    """
      Runs the backup script, and only backup a few files/directories in the
      source directory. Make sure those were copied
    """

if __name__ == "__main__":
  unittest.main()
