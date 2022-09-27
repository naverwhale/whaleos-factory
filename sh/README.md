<!--
 # Copyright 2021 The Chromium OS Authors. All rights reserved.
 # Use of this source code is governed by a BSD-style license that can be
 # found in the LICENSE file.
-->

# `factory` Usage
`factory` contains miscellaneous factory commands to run on DUTs. This user
guide lists some commonly used `factory` commands.

## factory clear
This command stops all running tests and clears their states.

## factory device-data
This command shows the content of the device data dictionary.
```
localhost ~ # factory device-data
component:
  ...
fw_config: ...
program: <program>
project: <project>
...
```

To get a specific device data, use `-g` option.
```
localhost ~ # factory device-data -g fw_config
12345
```

device-data also supports setting or deleting keys.
```
localhost ~ # factory device-data --delete project
localhost ~ # factory device-data project=<project>
```

Or you can set the device data from a yaml file.
```
factory device-data --set-yaml FILE
```

To specify the output format, use `--format`. The supported formats are `yaml`,
`json` and `pprint`.

## factory dump-test-list
This command dumps a test list in certain format. For instance,
`factory dump-test-list main_<project>`. You can specify the output format by
`factory dump-test-list --format [format] <test_list>`. The supported formats
are: `yaml`, `csv`, `json`, `pprint`.

## factory phase
This command queries or sets the current phase.
```
localhost ~ # factory phase
PROTO
localhost ~ # factory phase --set EVT
[INFO] factory.py phase.py:180 2021-07-18 13:45:46.786 Setting phase to EVT in /var/factory/state/PHASE
EVT
localhost ~ # factory phase
EVT
```

## factory screenshot
This command takes a screenshot of the Goofy tab that runs the factory test UI.
By default, the images are stored under `/var/log/screenshot_<TIME>.png`.

## factory stop
This command stops all running tests.

## factory test-list
This command is able to set or get the active test list, and/or list all test
lists. Note that generic test list is allowed only when there is no main test
list.

To show current test-list:
```
localhost ~ # factory test-list
[INFO] factory.py manager.py:109 2021-07-18 13:39:17.601 No test list constants config found
[INFO] factory.py manager.py:254 2021-07-18 13:39:17.902 No active test list configuration is found, fall back to select the default test list.
main_<project>
```
To show all the test lists available.
```
localhost ~ # factory test-list --list
[INFO] factory.py manager.py:109 2021-07-18 14:12:32.408 No test list constants config found
[INFO] factory.py manager.py:254 2021-07-18 14:12:32.714 No active test list configuration is found, fall back to select the default test list.
main_<project>
[INFO] factory.py manager.py:254 2021-07-18 14:12:32.739 No active test list configuration is found, fall back to select the default test list.
 ACTIVE? ID                      PATH
         generic_main            /usr/local/factory/py/test/test_lists/generic_main.test_list.json
         generic_replacement_mlb /usr/local/factory/py/test/test_lists/generic_replacement_mlb.test_list.json
         generic_rf_station      /usr/local/factory/py/test/test_lists/generic_rf_station.test_list.json
         generic_rma             /usr/local/factory/py/test/test_lists/generic_rma.test_list.json
         generic_rrt             /usr/local/factory/py/test/test_lists/generic_rrt.test_list.json
         generic_tast            /usr/local/factory/py/test/test_lists/generic_tast.test_list.json
         generic_unprovisioned   /usr/local/factory/py/test/test_lists/generic_unprovisioned.test_list.json
(active) main_<project>          /usr/local/factory/py/test/test_lists/main_<project>.test_list.json
```

## factory tests
This command lists all the test on current test list.
```
localhost ~ # factory tests
main_<project>:SMT.CR50FirmwareUpdate.UpdateCR50Firmware
main_<project>:SMT.CR50FirmwareUpdate.RebootStep
...
```
You can also combine this command with `grep` to get desired tests.
For instance, if you want to show all the camera related tests, you can:
```
localhost ~ # factory tests | grep -i camera
main_<project>:FAT.FrontCamera
main_<project>:FAT.RearCamera
```
To get the running status of a test, run `factory tests --status`.
```
localhost ~ # factory tests --status | grep -i main_<project>:FAT.FrontCamera
main_<project>:FAT.FrontCamera: PASSED
```
To show current active run:
```
localhost ~ # factory tests --this-run
main_<project>:FAT.FrontCamera
```

To show detailed information in yaml format:
```
localhost ~ # factory tests --yaml | grep -i \'main_<project>:FAT.FrontCamera\'
  iterations: 1, iterations_left: 1, parent: false, path: 'main_<project>:FAT.FrontCamera',
```

## factory run
This command runs a certain test. This is the same as clicking the UI to run the test.
```
localhost ~ # factory run main_<project>:FAT.FrontCamera
Running test main_<project>:FAT.FrontCamera
Active test run ID: f8fd163f-5805-4c3d-99ee-23fadaca7818
```

## factory run-status
This command shows the information about the latest test.
```
localhost ~ # factory run-status
status: RUNNING
run_id: fb64e9b3-7da2-47ee-b967-afceb42f67a7
scheduled_tests:
main_<project>:FAT.FrontCamera: ACTIVE
```

## factory wait
This command waits for all tests to finish and displays tests' statuses.
```
localhost ~ # factory wait
main_<project>:FAT.FrontCamera: ACTIVE
main_<project>:FAT.FrontCamera: PASSED
done
```