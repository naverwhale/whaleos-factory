#!/usr/bin/env python3
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from cros.factory.test.pytests import wireless_charge


class WirelessChargeHelperUnitTest(unittest.TestCase):

  def testGetPortStateFromChargeState(self):
    cases = [{
        'name': 'test irrelevant input',
        'input': 'random_string',
        'expected': wireless_charge.PortState.Unknown,
    }, {
        'name': 'test charge state is ENABLED',
        'input': wireless_charge.ChargeState.ENABLED,
        'expected': wireless_charge.PortState.Available,
    }, {
        'name': 'test charge state is CHARGING',
        'input': wireless_charge.ChargeState.CHARGING,
        'expected': wireless_charge.PortState.Occupied,
    }, {
        'name': 'test charge state is FULL',
        'input': wireless_charge.ChargeState.FULL,
        'expected': wireless_charge.PortState.Occupied,
    }]

    for c in cases:
      self.assertEqual(
          wireless_charge.GetPortStateFromChargeState(c['input']),
          c['expected'], msg=f'test failed at {c["name"]}')


if __name__ == '__main__':
  unittest.main()
