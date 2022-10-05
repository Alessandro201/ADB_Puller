# ADB_Puller
Script for pulling files from android smartphones using ADB drivers. It implements some additional features that adb lacks like:

- Skipping already pulled files
- A timeout feature to skip files that takes more than 60 seconds to pull as it usually means that the command is stuck
- A `--dry-run` option to see which files will be pulled and where they will be saved
- The option to pull items from a file, or skip them.

# Requirements
- `ADB` drivers that you can download [here](https://developer.android.com/studio/releases/platform-tools)
- Python 3.9+
- [Optional] tqdm for the progress bar

# Usage
Works on both Windows and Linux.
If you use the `-s` flag the folders will be saved in the destination folder with the same name they have in the smartphone.

### Pull some folders
You can add as many as you want after the `-s` flag. The folders in this case will be saved respectively in `~/abc/DCIM` and `~/abc/Recordings`: </br>
`python ./adb_puller.py -s '/sdcard/DCIM' '/sdcard/Music/Recordings' -d 'home/abc' `

***BEWARE*** The name of the directory will be used to create a folder inside the destination. If you pull from two directories with the same name they will be merged, and if two files have the same name one will be overwritten!
```
$ python ./adb_puller.py -s '/sdcard/DCIM/Camera' '/sdcard/Camera' -d '/home/abc' --dry-run
/sdcard/DCIM/Camera/IMG_1.jpg     ->  /home/abc/Camera/IMG_1.jpg
/sdcard/Camera/IMG_1.jpg          ->  /home/abc/Camera/IMG_1.jpg
/sdcard/Camera/IMG_2.jpg          ->  /home/abc/Camera/IMG_2.jpg
```

### Pull some files from a list
You can give as many files as you want with the `-i` command. The folders in this case will be saved respectively in `~/abc/DCIM` and `~/abc/Recordings`: </br>
`python ./adb_puller.py -i 'files_to_pull.txt' -d 'home/abc' `

***BEWARE*** When pulling files from a list the script cannot know which directory to use as root, and to avoid it from messing up the directory structure it will create all intermediate folders:
```
$ python ./adb_puller.py -i 'files_to_pull.txt' -d '/home/abc' --dry-run
/sdcard/DCIM/Screenshots/IMG_1.jpg          ->  /home/abc/sdcard/DCIM/Screenshots/IMG_1.jpg
/sdcard/Pictures/Screenshots/IMG_2.jpg      ->  /home/abc/sdcard/Pictures/Screenshots/IMG_2.jpg
/bin/test/IMG_2.jpg      ->  /home/abc/bin/test/IMG_2.jpg
```

### Skip files
If you want to skip some items you can supply them in a file with `--skip-from-file` flag. Conveniently, `adb_puller.py` saves in `done.txt` every file it pulls, so you can, for example, pull some files in a folder and stop the process, then redo it in another folder and skip the files already pulled. If you just want to skip some files you can use the `--skip` flag: </br>
`python ./adb_puller.py -s '/sdcard/DCIM' -d 'home/abc' --skip-from-file 'to_skip.txt' --skip '/sdcard/DCIM/to_skip.jpg' `

The command above will skip `/sdcard/DCIM/to_skip.jpg` and all items contained inside `to_skip.txt`.


All files containing paths like `files_to_pull.txt` or `to_skip.txt` just need to have a path every line:
```
/sdcard/1.jpg
/sdcard/2.jpg
/sdcard/DCIM/1.jpg
```


### Dry run
`--dry-run` will print the files that will be pulled and where they will be saved: </br>
```
$ python ./adb_puller.py -s '/sdcard/DCIM/Screenshots' -d '/home/abc' --dry-run
Building file list of "/sdcard/DCIM/Screenshots"
/sdcard/DCIM/Screenshots/IMG_1.jpg      ->  /home/abc/Screenshots/IMG_1.jpg
/sdcard/DCIM/Screenshots/IMG_2.jpg      ->  /home/abc/Screenshots/IMG_2.jpg
```
