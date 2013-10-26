Http Network Capture to Mock Builder
------------------------------------

Starts tcpflow to listen on the network then wraps the commands that you want
to mock up in a test server.

usage::
    sudo ./mock_buider.py -p 8081 "swift -A http://127.0.0.1:8081/auth/v1.0 -U test:tester -K testing post new_bucket" > swift_mock.py
    sudo ./mock_buider.py -p 8081 -i eth2 -t test "swift -A http://127.0.0.1:8081/auth/v1.0 -U test:tester -K testing post new_bucket" > swift_mock.py


Mock builder will then produce a Flask server that responds to requests with the same API and results as the command.
In the second example -t is a comma separated list of strings to look for in the path and replace with variables.


Dependencies
____________
`sudo apt-get install tcpflow`

