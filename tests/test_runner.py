#!/usr/bin/env python

# This will sort of work but it wont show the data because
# pcap wont show the data on localhost always. I need to figure out
# exactly what is going on there
''' run test on mocks to converge to the same mock '''

import os
import subprocess
import time

def run(cmd):
    ''' subprocess wrapper '''
    return subprocess.Popen(cmd, shell=True)

def my_dir():
    ''' dir this source file is in '''
    return os.path.dirname(os.path.realpath(__file__))

def main():
    ''' start nova_mock.py and keystone_mock.py then run novaclient on them
    to confirm the output is the same as nova_mock.py'''

    nova_mock = "python %s/nova_mock.py" % my_dir()
    keystone_mock = "python %s/keystone_mock.py" % my_dir()

    run(nova_mock)
    run(keystone_mock)

    time.sleep(1)

    env = {
        "OS_TENANT_NAME": "test",
        "OS_USERNAME": "test",
        "OS_PASSWORD": "test",
        "OS_AUTH_URL": "http://127.1:5000/v2.0/",
    }

    builder = subprocess.Popen(
        'python %s/../mock_builder.py -p 8774 "nova list"' % my_dir(),
        env=env, shell=True)

    builder.wait()

    run("pkill -f '%s'" % nova_mock)
    run("pkill -f '%s'" % keystone_mock)

if __name__ == "__main__":
    main()
