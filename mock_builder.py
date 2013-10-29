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
import logging
import logging.handlers

#TODO global variable bad
TOKENS = []
LOG = logging.getLogger(__name__)

def create_mock(client, server):
    ''' create mock functions from client and server data '''

    LOG.debug("Client data: %s", client)
    LOG.debug("Server data: %s", server)
    headers = get_headers(server)
    response = response_data(server)

    LOG.debug("HEADERS: %s", headers)
    LOG.debug("RESPONSE DATA: %s", response)

    tfer = "'Transfer-Encoding': 'chunked'"
    # note: a dict ending with a comma is valid
    for text in [tfer + ", ", tfer]:
        if text in headers:
            response = "\n".join(response.split("\n")[1:-1])
            headers = headers.replace(tfer, "")
            LOG.debug("removing Transfer-Encoding header")
            LOG.debug("New HEADERS: %s", headers)
            LOG.debug("New RESPONSE DATA: %s", response)
            break

    return "\n".join([
        create_def(client.split(" HTTP")[0]),
        "    return ('''%s''', %s, %s)" % (
            response, status_code(server), headers)])


def response_data(server):
    ''' Extract the response data from the server text '''
    header_body = server.split("\r\n\r\n")
    if len(header_body) > 1:
        return header_body[1].replace("\r", "")
    return ''


def status_code(server):
    ''' Extract the status code from the server text '''
    return server.split(" ")[1]


def get_headers(server):
    ''' Extract the response headers from the server text '''
    items = []
    for line in server.split("\r\n\r\n")[0].split("\r\n")[1:]:
        line = line.replace("\r", '')
        LOG.debug("Building headers line %s", line)
        if line:
            parts = line.split(": ")
            LOG.debug("Building headers split line %s", parts)
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
    LOG.debug("Method: %s", method)
    LOG.debug("Path: %s", path)

    #TODO: handle query string
    path = path.split("?")[0]
    LOG.debug("Path without query string: %s", path)

    path, parameters = params_from_path(path)
    LOG.debug("Path with parameters: %s", path)

    dec = '@app.route("%s", methods=["%s"])' % (path, method)
    LOG.debug("Flask decorator %s", dec)
    for char in '/.<>?=':
        path = path.replace(char, '_')
        LOG.debug("Replaced %s in path to get: %s", char, path)

    func_name = method.lower() + path
    LOG.debug("Function name: %s", func_name)
    param_string = ""
    for i in parameters:
        param_string += i + ", "
        LOG.debug("Building param string: %s", param_string)
    sig = 'def %s(%s):' % (func_name, param_string[:-2])
    LOG.debug("Function signature: %s", sig)

    return '\n'.join([dec, sig])


def main():
    ''' Run command while snooping then output Flask mock.'''

    parser = argparse.ArgumentParser(
            description="Generates HTTP mock from command")
    parser.add_argument("command", type=str)
    parser.add_argument("-p", dest="port", required=True, type=int)
    parser.add_argument("-i", dest="iface", default="any", type=str)
    parser.add_argument("-d", dest="debug", action="store_true")
    parser.add_argument("-t", dest="token", type=str)

    args = parser.parse_args()

    if args.debug:
        LOG.setLevel(logging.DEBUG)
        LOG.addHandler(logging.StreamHandler())

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

    verbs = ['OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'TRACE',
            'CONNECT']

    sigs = set()
    for client, server in client_server:
        client_text = client.read()
        server_text = server.read()
        client.close()
        server.close()

        LOG.debug("Text from client %s", client_text)
        LOG.debug("Text from server %s", server_text)

        verbs = " /|".join(['OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE',
                'TRACE', 'CONNECT'])

        req_regex = '^(%s).*?(?=^(%s)|\Z)' % (verbs, verbs)
        LOG.debug("Request regex %s", req_regex)

        requests = [match.group(0) for match in re.finditer(req_regex,
                client_text, flags=re.MULTILINE|re.DOTALL)]

        responses = ["HTTP/" + res for res in
                re.split("^HTTP/|\nHTTP/", server_text) if res]

        LOG.debug("The split requests %s", requests)
        LOG.debug("The split responsess %s", responses)

        for req, resp in zip(requests, responses):
            func = create_mock(req, resp)
            LOG.debug("The function: %s", func)
            sig = "".join(func.split("\n")[:2])
            if sig not in sigs:
                sigs.add(sig)
                mock_functions.append(func)

    mock_functions.append("\n".join(['if __name__ == "__main__":',
        '    app.run(host="127.1", debug=True, port=%s)' % port]))

    print "\n\n".join(mock_functions)

    shutil.rmtree(new_dir)

if __name__ == '__main__':
    main()
