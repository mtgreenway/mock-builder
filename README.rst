Http Network Capture to Mock Builder
------------------------------------

Starts tcpdump to listen on the network then wraps the commands that you want
to mock up in a test server.

usage::
    sudo ./mock_buider.py -p 8081 "swift -A http://127.0.0.1:8081/auth/v1.0 -U test:tester -K testing post new_bucket" > swift_mock.py


this will then produce a Flask server that responds to requests with the same
API and results as the command.


Dependencies
____________
`sudo apt-get install tcpflow`

TODO
----

Find parameters in urls
