#!/usr/bin/env python3
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getopt
import grp
import logging
import os
import pwd
import sys

# derived from src/aosp/external/minijail/minijail0_cli.c
OPT_STRING = 'u:g:sS:c:C:P:b:B:V:f:m::M::k:a:e::R:T:vrGhHinNplLt::IUKwyYzd'
# TODO(pihsun): The uts argument is actually optional long option, but Python
# getopt doesn't support optional long option. All usage seems to be not
# passing a value to it, so we use 'uts' instead of 'uts=' here.
LONG_OPTIONS = [
    'help',
    'mount-dev',
    'ambient',
    'uts',
    'logging=',
    'profile=',
    'seccomp-bpf-binary',
]

# Only override these programs (find from /etc/init/*.conf)
ALLOWLIST = ['/usr/sbin/sslh-fork']

JAILED_DIR = '/run/jailed'


def minijail():
  opts, args = getopt.getopt(sys.argv[1:], OPT_STRING, LONG_OPTIONS)

  if not args or args[0] not in ALLOWLIST:
    original = os.path.join(JAILED_DIR, os.path.basename(sys.argv[0]))
    args = [original] + sys.argv[1:]
    os.execvp(args[0], args)

  opts = dict(opts)
  user = opts.get('-u')
  group = opts.get('-g')
  gid = 0
  if group:
    gid = grp.getgrnam(group).gr_gid
    os.setegid(gid)
  if user:
    if '-G' in opts:
      os.initgroups(user, gid)
    uid = pwd.getpwnam(user).pw_uid
    os.seteuid(uid)

  if '-i' in opts and os.fork() == 0:
    sys.exit()

  os.execvp(args[0], args)


if __name__ == '__main__':
  logging.basicConfig(
      filename='/var/log/minijail0.log', level=logging.INFO,
      format='[%(levelname)s] %(asctime)s.%(msecs)03d %(message)s',
      datefmt='%Y-%m-%d %H:%M:%S')
  try:
    minijail()
  except Exception:
    logging.exception('argument: %r', sys.argv)
    sys.exit(1)
