# ADB_Puller
Script for pulling files from android smartphones using ADB drivers. It implements some additional features that adb lacks like:

- Skipping already pulled files
- A timeout feature to skip files that takes more than 60 seconds to pull as it usually means that the command is stuck
- A `--dry-run` option to see which files will be pulled and where they will be saved
- The option to pull items from a file.

# Requirements
- Python 3.9+ for `BooleanOptionAction` from `argparse`.
- [Optional] tqdm for the progress bar

# Usage
Works on both Windows and Linux

`python ./adb_puller.py -s '/sdcardDCIM' '/sdcard/Music' -d . ` 
