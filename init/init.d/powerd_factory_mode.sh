#!/bin/sh
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

mkdir -p /var/lib/power_manager
echo 1 >/var/lib/power_manager/factory_mode
