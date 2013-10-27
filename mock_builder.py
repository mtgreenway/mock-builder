#!/usr/bin/env python
#  Copyright 2013 Open Cloud Consortium
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
''' Build Flask mock servers from snooping HTTP traffic '''


import argparse
import os
import re
import shutil
import subprocess
import tempfile

#TODO global variable bad
TOKENS = []

def create_mock(client, server):
    ''' create mock functions from client and server data '''

    headers = get_headers(server)
    response = response_data(server)

    tfer = "'Transfer-Encoding': 'chunked'"
    # note: a dict ending with a comma is valid
    for text in [tfer + ", ", tfer]:
        if text in headers:
            response = "\n".join(response.split("\n")[1:-1])
            headers = headers.replace(tfer, "")
            break

    return "\n".join([
        create_def(client.split(" HTTP")[0]),
        "    return ('''%s''', %s, %s)" % (
            response, status_code(server), headers)])


def response_data(server):
    ''' Extract the response data from the server text '''
    return server.split("\r\n\r\n")[1].replace("\r", "")


def status_code(server):
    ''' Extract the status code from the server text '''
    return server.split(" ")[1]


def get_headers(server):
    ''' Extract the response headers from the server text '''
    items = []
    for line in server.split("\r\n\r\n")[0].split("\r\n")[1:]:
        parts = line.split(": ")
        items.append("'%s': '%s'" % (parts[0], ": ".join(parts[1:])))
    return "{%s}" % ", ".join(items)


def uuid_format(uuid):
    ''' Return formatted uuid if this is a uuid otherwise None '''

    hexits = 5 * ("[a-fA-F0-9]",)
    dash = re.compile("%s{8}-%s{4}-%s{4}-%s{4}-%s{12}" % hexits)
    nodash = re.compile("%s{8}%s{4}%s{4}%s{4}%s{12}" % hexits)

    if dash.match(uuid):
        return uuid.replace("-", "")
    elif not nodash.match(uuid):
        return None
    return uuid


def params_from_path(path):
    ''' if there are things in the path that need to be parameters such as
    uuids or specified unique names to search for like usernames make those
    params '''

    path_parts = []
    params = []
    for part in path.split("/"):
        if uuid_format(part):
            param = "uuid%s" % len(params)
            params.append(param)
            path_parts.append("<%s>" % param)
        else:
            for token in TOKENS:
                new_part = part.replace(token, "<%s>" % token)
                if new_part != part:
                    params.append(token)
                    part = new_part
            path_parts.append(part)

    return "/".join(path_parts), params


def create_def(method_path):
    ''' using the first part of the HTTP request to generate the function
    signature '''
    method, path = method_path.split(" ")
    #TODO: handle query string
    path = path.split("?")[0]
    path, parameters = params_from_path(path)
    dec = '@app.route("%s", methods=["%s"])' % (path, method)
    for char in '/.<>?=':
        path = path.replace(char, '_')
    func_name = method.lower() + path
    param_string = ""
    for i in parameters:
        param_string += i + ", "
    sig = 'def %s(%s):' % (func_name, param_string[:-2])
    return '\n'.join([dec, sig])


def main():
    ''' Run command while snooping then output Flask mock.'''

    parser = argparse.ArgumentParser(
            description="Generates HTTP mock from command")
    parser.add_argument("command", type=str)
    parser.add_argument("-p", dest="port", required=True, type=int)
    parser.add_argument("-i", dest="iface", default="any", type=str)
    parser.add_argument("-t", dest="token", type=str)

    args = parser.parse_args()

    if args.token:
        global TOKENS
        TOKENS = args.token.split(',')

    new_dir = tempfile.mkdtemp()

    port = "%s" % args.port

    tcpflow_command = ["/usr/bin/tcpflow", "-i", args.iface, "port", port]
    dump_proc = subprocess.Popen(tcpflow_command, cwd=new_dir)

    run_proc = subprocess.Popen(["( %s ) 1>&2" % args.command], shell=True)
    run_proc.wait()

    dump_proc.kill()

    client_server = []
    for file_name in os.listdir(new_dir):
        if file_name.endswith("00000"[len(port):] + port):
            rev = file_name.split('-')
            rev.reverse()
            server_file = '-'.join(rev)
            client_server.append((open(os.path.join(new_dir, file_name)),
                open(os.path.join(new_dir, server_file))))

    mock_functions = [
        "#!/usr/bin/env python",
        "# Generated by mock-builder",
        "from flask import Flask, request",
        "app = Flask(__name__)"
    ]

    sigs = set()
    for client, server in client_server:
        func = create_mock(client.read(), server.read())
        sig = "".join(func.split("\n")[:2])
        if sig not in sigs:
            sigs.add(sig)
            mock_functions.append(func)
        client.close()
        server.close()

    mock_functions.append("\n".join(['if __name__ == "__main__":',
        '    app.run(host="127.1", debug=True, port=%s)' % port]))

    print "\n\n".join(mock_functions)

    shutil.rmtree(new_dir)

if __name__ == '__main__':
    main()
