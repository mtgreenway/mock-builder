#!/usr/bin/env python

# This will sort of work but it wont show the data because
# pcap wont show the data on localhost always. I need to figure out 
# exactly what is going on there

import os
import subprocess
import time

def run(cmd):
    return subprocess.Popen(cmd, shell=True)
        #creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

def my_dir():
    return os.path.dirname(os.path.realpath(__file__))

def main():
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
