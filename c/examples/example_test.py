#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License
#

# Run the C examples and verify that they behave as expected.
# Example executables must be in PATH

import unittest, sys, time, re
from subprocess import Popen, PIPE, check_output, CalledProcessError, STDOUT

MESSAGES=10

def receive_expect_messages(n=MESSAGES): return ''.join(['{"sequence"=%s}\n'%i for i in range(1, n+1)])
def receive_expect_total(n=MESSAGES): return "%s messages received\n"%n
def receive_expect(n=MESSAGES): return receive_expect_messages(n)+receive_expect_total(n)
def send_expect(n=MESSAGES): return "%s messages sent and acknowledged\n" % n
def send_abort_expect(n=MESSAGES): return "%s messages started and aborted\n" % n

def wait_listening(p):
    return re.search("listening on ([0-9]+)$", p.stdout.readline()).group(1)

class Broker(Popen):
    def __init__(self):
        super(Broker, self).__init__(["broker", "", "0"], stdout=PIPE)

    def __enter__(self):
        self.port = wait_listening(self)
        return self

    def __exit__(self, *args):
        self.kill()

class ExampleTest(unittest.TestCase):

    def runex(self, name, port, messages=MESSAGES):
        """Run an example with standard arguments, return output"""
        return check_output([name, "", str(port), "xtest", str(messages)], stderr=STDOUT)

    def test_send_receive(self):
        """Send first then receive"""
        with Broker() as b:
            self.assertEqual(send_expect(), self.runex("send", b.port))
            self.assertMultiLineEqual(receive_expect(), self.runex("receive", b.port))

    def test_receive_send(self):
        """Start receiving  first, then send."""
        with Broker() as b:
            self.assertEqual(send_expect(), self.runex("send", b.port))
            self.assertMultiLineEqual(receive_expect(), self.runex("receive", b.port))

    def test_send_direct(self):
        """Send to direct server"""
        d = Popen(["direct", "", "0"], stdout=PIPE)
        port = wait_listening(d)
        self.assertEqual(send_expect(), self.runex("send", port))
        self.assertMultiLineEqual(receive_expect(), d.communicate()[0])

    def test_receive_direct(self):
        """Receive from direct server"""
        d = Popen(["direct", "", "0"], stdout=PIPE)
        port = wait_listening(d)
        self.assertMultiLineEqual(receive_expect(), self.runex("receive", port))
        self.assertEqual("10 messages sent and acknowledged\n", d.communicate()[0])

    def test_send_abort_broker(self):
        """Sending aborted messages to a broker"""
        with Broker() as b:
            self.assertEqual(send_expect(), self.runex("send", b.port))
            self.assertEqual(send_abort_expect(), self.runex("send-abort", b.port))
            for i in xrange(MESSAGES):
                self.assertEqual("Message aborted\n", b.stdout.readline())
            self.assertEqual(send_expect(), self.runex("send", b.port))
            expect = receive_expect_messages(MESSAGES)+receive_expect_messages(MESSAGES)+receive_expect_total(20)
            self.assertMultiLineEqual(expect, self.runex("receive", b.port, "20"))

    def test_send_abort_direct(self):
        """Send aborted messages to the direct server"""
        d = Popen(["direct", "", "0", "examples", "20"], stdout=PIPE)
        port = wait_listening(d)
        self.assertEqual(send_expect(), self.runex("send", port))
        self.assertEqual(send_abort_expect(), self.runex("send-abort", port))
        self.assertEqual(send_expect(), self.runex("send", port))
        expect = receive_expect_messages() + "Message aborted\n"*MESSAGES + receive_expect_messages()+receive_expect_total(20)
        self.maxDiff = None
        self.assertMultiLineEqual(expect, d.communicate()[0])

    def test_send_ssl_receive(self):
        """Send with SSL, then receive"""
        try:
            with Broker() as b:
                got = self.runex("send-ssl", b.port)
                self.assertIn("secure connection:", got)
                self.assertIn(send_expect(), got)
                self.assertMultiLineEqual(receive_expect(), self.runex("receive", b.port))
        except CalledProcessError as e:
            print "FIXME", e.output
            if e.output.startswith("error initializing SSL"):
                print("Skipping %s: SSL not available" % self.id())
            else:
                raise

if __name__ == "__main__":
    unittest.main()
