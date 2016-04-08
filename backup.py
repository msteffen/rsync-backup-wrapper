#!/usr/bin/python

from backup_lib import *

def main():
  # Parse flags (which are used to initialize a Backup instance)
  arg_parser = argparse.ArgumentParser(
      description="Efficiently backup a directory tree using rsync.",
      epilog="""Examples:
    ./backup.py --src=/Users/msteffen --backup_drive="/Volumes/Seagate Backup Plus Drive/Macbook/"
    ./backup.py --src=/home/mjs/sensitive --dst=/net/backups/today --prev_backup=/net/backups/6_months_ago
      """,
      formatter_class=argparse.RawTextHelpFormatter)
  arg_parser.add_argument('--src', type=str, help="The directory to be backed "
      "up")
  # Either --backup_drive or --dst/--prev_backup should be specified
  arg_parser.add_argument('--backup_drive', type=str, help="A directory where "
      "the new backup should be placed, which follows this script's naming "
      "convention for incremental backups (backups are named with the date "
      "they were taken). --dst will be constructed and --prev_backup will be "
      "inferred if this flag is set. If this is set, don't set those flags")
  arg_parser.add_argument('--dst', type=str, help="The directory that will "
      "receive the backup")
  arg_parser.add_argument('--prev_backup', type=str, help="A directory used "
      "for a previous backup. To save space, if a file hasn't changed since "
      "this backup was taken, the file is backed up by creating a hard link to "
      "here from --dst, instead of being copied")
  args = arg_parser.parse_args()

  # Validate flag values
  assert args.src, "Must specify --src. Run `./backup.py --help` for usage info"
  assert args.backup_drive or args.dst, \
      "Must specify exactly one of --dst or --backup_drive. Run " \
      "`./backup.py --help` for usage info"
  assert not args.backup_drive or not args.dst, \
      "Must specify exactly one of --dst or --backup_drive. Run " \
      "`./backup.py --help` for usage info"
  assert not args.backup_drive or not args.prev_backup, \
      "Must specify at most one of --prev_backup or --backup_drive. Run " \
      "`./backup.py --help` for usage info"

  # Run backup using flag values
  if args.backup_drive:
    backup = Backup.FromBackupDrive(args.src, args.backup_drive)
  else:
    backup = Backup(args.src, args.dst, args.prev_backup)

  cmd = backup.rsync_cmd()
  print "Executing:"
  print " ".join(cmd)
  backup.run_rsync_cmd()
  print("\033[1;32mDONE!\033[0m")

if __name__ == "__main__":
  main()
