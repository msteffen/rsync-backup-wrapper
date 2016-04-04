#!/usr/bin/python

import argparse
from datetime import date, time, datetime
import os
from os.path import abspath, exists, isabs, isdir, join, normpath
import re
import subprocess as proc
from sys import stdin

class Backup:
  """ Data structure with all information needed to create a backup """

  # NOTE: if this is ever changed, all existing backups will have to be renamed
  # or else this class won't be able to find the most recent backup in a
  # directory
  _DATE_FORMAT = "%d-%b-%Y"
  _LOG_FILE = "rsync_backup.log"

  def __init__(self, src, dst, prev_backup=None, backup_targets=["..."]):
    src = abspath(src)
    dst = abspath(dst)
    prev_backup = abspath(prev_backup) if prev_backup else None

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

    self.src = src
    self.dst = dst
    self.prev_backup = prev_backup
    self.backup_targets = backup_targets

  @staticmethod
  def FromBackupDrive(src, drive):
    """
      Initialize and return a Backup object from a directory containing
      previous backups created by this script

      Keyword arguments:
      drive -- a global path to a directory where an external backup drive has
          been mounted (or a subdirectory inside an external backup drive, if
          the drive is shared)
    """
    src = abspath(src)
    drive = abspath(drive)
    assert isdir(src), "src ({}) is not a dir".format(src)
    assert isdir(drive),  "drive ({}) is not a dir".format(drive)

    ## Scan previous backups and find the most recent
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

    most_recent_path = None
    if most_recent:
      print ("Using {} as the previous backup dir -- unchanged files will point "
            + "there").format(most_recent)
      most_recent_path = join(drive, most_recent.strftime(Backup._DATE_FORMAT))
    return Backup(src=src, prev_backup=most_recent_path,
        dst=join(drive, datetime.today().strftime(Backup._DATE_FORMAT)))

  def destination(self):
    return self.dst

  def handle_backup_targets():
    backup_targets = os.listdir(self.dst)
# TODO will this include hidden files? Test that case. must be the same as running rsync on the parent
# TODO Does rsync have an option to only copy certain children?

  def rsync_cmd(self, dry_run=False):
    """
      Backup the subtree under `self.src` to `self.dst`, linking against files
      in `self.prev_backup` if they're unchanged (i.e. if
      [self.src/.../file] == [prev_backup/.../file]).

      If `self.prev_backup` is unset, don't do any linking
    """
    args = [
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

    if self.prev_backup:
      args += [
        # If a file is the same in both `self.src` and `self.prev_backup`,
        # create a hardlink in `self.dst` to `self.prev_backup` instead of
        # copying the file
        '--link-dest={}'.format(self.prev_backup)
      ]
    if dry_run: args += ['--dry-run']

    cmd = ['rsync'] + args + [
      # append a "/" to `self.src`, so rsync copies its contents instead of the
      # directory itself. Note that `self.src` was already normalized in
      # __init__ by abspath()
      self.src + "/",
      self.dst,
    ]
    return cmd

  def run_rsync_cmd(self, dry_run=False, output_file=_LOG_FILE):
    """
      Runs the commands returned by "rsync_cmd", piping the output to
      "rsync_backup.log"
    """
    args = {}
    if output_file:
      args["stdout"] = open(join(self.dst, output_file), "w")
      args["stderr"] = proc.STDOUT
    proc.call(self.rsync_cmd(), **args)
