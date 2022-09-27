#!/usr/bin/env python3
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The tool to run a command with proper factory env path with mocked modules.

The tool sets up py_pkg to the env path properly, so that the cros.* is located
with mocked modules replacing real modules if it exists, whereas replaced real
modules can be accessed via real.cros.*. After env is set, it runs the command
directly.
"""

import os
import sys

from cros.factory.tools.unittest_tools import mock_loader


HELP_MSG = """
Usage :
       bin/factory_mocked_env program args...
       program can be a path to a executable program, or any executable that
       can be found in $PATH.
"""


def Main():
  with mock_loader.Loader() as loader:
    # mocked env only takes care mocked module, other env should be set by
    # factory_env and here we just copy env from outside
    child_env = dict(os.environ)
    child_env['PYTHONPATH'] = loader.GetMockedRoot()
    try:
      os.execvpe(sys.argv[1], sys.argv[1:], env=child_env)
    except OSError:
      print(HELP_MSG, end='')
      sys.exit(1)


if __name__ == '__main__':
  Main()
