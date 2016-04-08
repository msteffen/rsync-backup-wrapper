#!/usr/bin/python

import argparse
from datetime import date, time, datetime
import os
from os.path import abspath, exists, isabs, isdir, join, normpath
import re
import subprocess as proc
from sys import stdin

_fixed_rsync_args = [
  # Archive mode (preserves most file attributes) and verbose logging
  '-av',

  # Ignore character and block device files, and special files (e.g.
  # sockets)
  '--no-D',

  # Use checksum to determine file equality (see man page; default bahavior
  # in rysnc is to compare timestamp and file size to determine equality,
  # but that's fragile. This is much slower though, so perhaps this should
  # be disabled later)
  '--checksum',

  # output lines:
  # %n The filename
  # %b The number of bytes actually transferred
  # %l The actual size of the file
  # %i info line (http://stackoverflow.com/questions/1113948/rsync-output)
  '--out-format="%n (%b/%l) %i"',
]

class Backup:
  """ Data structure with all information needed to create a backup """

  # NOTE: if this is ever changed, all existing backups will have to be renamed
  # or else this class won't be able to find the most recent backup in a
  # directory
  _DATE_FORMAT = "%d-%b-%Y"
  _LOG_FILE = "rsync_backup.log"
  _DONE_FILE = "BACKUP_DONE"

  def __init__(self, src, dst, prev_backup=None, backup_order=["..."]):
    """
      Default constructor of Backup. A Backup will generate one or more rsync
      commands to backup the files in src, subject to the constraints of
      "backup_order"

      Keyword arguments:
      src -- the directory (must be a directory) to back up
      dst -- the directory where the backup should be stored (does not need to
          exist)
      prev_backup -- Directory where a previous backup has been stored. If a
          file in "src" is also in "prev_backup" and hasn't changed (i.e. they
          are checksum-equal) then a hard link will be created in "dst"
          pointing to the copy in "prev_backup" to save space
          (Default value = None)
      backup_order -- List of files in "src" to be backed up, or "..." to back
          up all files not already mentioned. If "..." is not one of the
          elements of this list, files that are not listed will not be backed
          up.
          (Default value = ["..."])
    """
    src = abspath(src)
    dst = abspath(dst)
    prev_backup = abspath(prev_backup) if prev_backup else None
    clean_backup_order = []
    for i in range(len(backup_order)):
      f = backup_order[i]
      if f == "...":
        assert i == (len(backup_order) - 1), \
            "\"...\" must be last in backup order"
        clean_backup_order.append(f)
      else:
        assert exists(join(src, f)), \
            "file {} in backup order does not exist".format(join(src, f))
        clean_backup_order.append(f)

    # Validate & sanitize arguments
    assert isdir(src), "src({}) is not a dir".format(src)
    assert prev_backup is None or isdir(prev_backup), \
        "prev_backup ({}) is not a dir".format(prev_backup)
    if not exists(dst):
      os.mkdir(dst)
    else:
      assert isdir(dst), "dst exists and isn't dir: {}".format(dst)
      assert not exists(join(dst, Backup._DONE_FILE)), \
          "dst ({}) already contains a completed backup".format(dst)

    # Assign instance vars
    self.src = src
    self.dst = dst
    self.prev_backup = prev_backup
    self.backup_order = clean_backup_order

  @staticmethod
  def FromBackupDrive(src, drive, backup_order=["..."]):
    """
      Initialize and return a Backup object from a directory containing
      previous backups created by this script

      Keyword arguments:
      drive -- a global path to a directory where an external backup drive has
          been mounted (or a subdirectory inside an external backup drive, if
          the drive is shared)
      backup_order -- List of files in "src" to be backed up, or "..." to back
          up all files not already mentioned. If "..." is not one of the
          elements of this list, files that are not listed will not be backed
          up.
    """
    src = abspath(src)
    drive = abspath(drive)
    assert isdir(src), "src ({}) is not a dir".format(src)
    assert isdir(drive),  "drive ({}) is not a dir".format(drive)

    # Scan previous backups and find the most recent
    today = datetime.combine(date.today(), time())  # Need plain date (for ==)
    most_recent = None
    for d in os.listdir(drive):
      if not isdir(d): continue
      try:
        t = datetime.strptime(d.strip(), Backup._DATE_FORMAT)
        if t == today: continue
        if most_recent is None or t > most_recent:
          most_recent = t
      except:
        # "d" is not a backup dir -- skip it
        continue

    # Convert most recent date from prev. backup directories back into dir name
    most_recent_path = None
    if most_recent:
      print ("Using {} as the previous backup dir -- unchanged files will point "
            + "there").format(most_recent)
      most_recent_path = join(drive, most_recent.strftime(Backup._DATE_FORMAT))
    dst = join(drive, datetime.today().strftime(Backup._DATE_FORMAT))
    return Backup(src=src, prev_backup=most_recent_path, dst=dst,
                  backup_order=backup_order)

  def destination(self):
    return self.dst

# TODO will this include hidden files? Test that case. must be the same as running rsync on the parent
# TODO Does rsync have an option to only copy certain children?

  def rsync_cmds(self, dry_run=False):
    """
      Backup the subtree under `self.src` to `self.dst`, linking against files
      in `self.prev_backup` if they're unchanged (i.e. if
      [self.src/.../file] == [prev_backup/.../file]).

      If `self.prev_backup` is unset, don't do any linking
    """
    cmds = []
    visited = []
    for f in self.backup_order:
      # Argument that apply to all backups (copy permissions, etc)
      args = _fixed_rsync_args

      # Define --exclude arguments
      excluded_files = []
      for v in visited:
        if f == "...":
          excluded_files = visited
        elif v.startswith(f):
          excluded_files.append(visited) # Already backed up -- skip for now
        elif f.startswith(v):
          continue # Already backed up parent -- skip this
        else:
          pass # visited file has nothing to do with current backup
      for ex in excluded_files:
        args.append("--exclude={}".format(join(self.src, ex)))

      # Create hardlinks to previous backup if file is unchanged
      if self.prev_backup:
        args += [
          "--link-dest={}".format(self.prev_backup)
        ]
      if dry_run: args += ["--dry-run"]

      # Define command
      # Append a "/" to `self.src` (top-level copy), so rsync copies its
      # contents instead of the directory itself
      src = join(self.src, f) if f != "..." else self.src + "/"
      cmd = ["rsync"] + args + [src, self.dst]
      cmds.append(cmd)
      visited.append(f)
    return cmds

  def run_rsync_cmds(self, dry_run=False, output_file=_LOG_FILE):
    """
      Runs the commands returned by "rsync_cmd", piping the output to
      "rsync_backup.log"
    """
    io_args = {}
    if output_file:
      io_args["stdout"] = open(join(self.dst, output_file), "w")
      io_args["stderr"] = proc.STDOUT
    for cmd in self.rsync_cmds(dry_run):
      # We're logging -- append log command
      if "stdout" in io_args:
        io_args["stdout"].write(
            "{0}\n{1}\n{0}\n".format("-"*80, "\n    ".join(cmd)))
        io_args["stdout"].flush()
      # Run rsync cmd
      proc.call(cmd, **io_args)
    # touch BACKUP_DONE
    with open(join(self.dst, self._DONE_FILE), "w") as donefile: pass
