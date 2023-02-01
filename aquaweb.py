#!/usr/bin/env python3
# aquaweb.py - Simulates Aqualink remotes with a web interface
# Earle F. Philhower, III <earlephilhower@yahoo.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import base64
import string
import serial
import struct
import threading
import sys
import time
import socket
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from email.message import Message
import urllib
from functools import reduce


# Configuration

RS485Device = "/dev/ttyUSB0"        # RS485 serial device to be used
debugData = False
debugRaw = False

# ASCII constants
NUL = 0x00
DLE = 0x10
STX = 0x02
ETX = 0x03

last_log = ""

JAVASCRIPT = """
<script language="Javascript">

if (window.XMLHttpRequest) {
    var xmlHttpReqKey = new XMLHttpRequest();
    var xmlHttpReqScreen = new XMLHttpRequest();
} else {
    var xmlHttpReqKey = new ActiveXObject("Microsoft.XMLHTTP");
    var xmlHttpReqScreen = new ActiveXObject("Microsoft.XMLHTTP");
}

function screen() {
    xmlhttpPost(xmlHttpReqScreen, "/screen.cgi", "", "screen");
}

function sendkey(key) {
    xmlhttpPost(xmlHttpReqKey, "/key.cgi", "key="+key);
}

function xmlhttpPost(xmlReq, strURL, params, update) {
    xmlReq.open('POST', strURL, true);
    xmlReq.setRequestHeader("Content-type","application/x-www-form-urlencoded");
    xmlReq.send(params);
    if (update != "") {
      xmlReq.onreadystatechange = function() {
        if (xmlReq.readyState == 4) {
            updatepage(xmlReq.responseText, update);
        }
      }
    }
    xmlReq.send();
}

function updatepage(str, div){
    document.getElementById(div).innerHTML = str;
    setTimeout(window[div](), 250);
}
</script>
"""

FAVICON = base64.b64decode("""AAABAAEAEBACAAEAAQCwAAAAFgAAACgAAAAQAAAAIAAAAAEAAQAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAwAAAAAAAP//AAD//wAA/r8AANAHAACKiQAAH3AAAD68AAAR1AAAn6EAANFXAAD6pgAA
99EAAP/LAAD/3wAA//8AAP//AAD//wAA//8AAP6/AADQBwAAiokAAB9wAAA+vAAAEdQAAJ+hAADR
VwAA+qYAAPfRAAD/ywAA/98AAP//AAD//wAA""")

SQUAREHTML = "<html><head><title>Pool Controller</title>" + JAVASCRIPT + """
</head>
<body onload="screen();">
<table>
<tr>
<td>
<table><tr><td height="80px" align="right"><button onclick="sendkey('pgup');">Page Up</button></td></tr><tr><td align="right" height="80px"><button onclick="sendkey('back');">Back</button></td></tr><tr><td align="right" height="80px"><button onclick="sendkey('pgdn');">Page Down</button></td></tr></table>
</td>
<td>
<font size="+2"><div id="screen"></div> </font>
</td>
<td>
    <table><tr><td align="left" height="80px"><button onclick="sendkey('up');">Up</button></td></tr><tr><td align="left" height="80px"><button onclick="sendkey('down');">Down</button></td></tr></table>
</td>
</tr>
<tr><td colspan="3" align="center"><button onclick="sendkey('select');">Select</button></td></tr>
</table>
</body>
</html>
"""


PDAHTML = "<html><head><title>Pool Controller</title>" + JAVASCRIPT + """
</head>
<body onload="screen();">
<table>
<tr><td style="border:1px solid black;"><font size="+2"><div id="screen"></div></font></td></tr>
<tr><td>
  <table>
    <tr><td align="left"><button onclick="sendkey('back');">Back</button</td><td align="center"><button onclick="sendkey('up');">Up</button></td><td align="right"><button>&nbsp;</button></td></tr>
    <tr><td align="left">&nbsp;</td><td align="center"><button onclick="sendkey('select');">Select</button></td><td align="right">&nbsp;</td></tr>
    <tr><td align="left"><button onclick="sendkey('pgup');">1</button></td><td align="center"><button onclick="sendkey('down');">Down</button></td><td align="right"><button onclick="sendkey('pgdn');">2</button></td></tr>
  </table>
</table>
</body>
</html>
"""

INDEXHTML = ""


SPAHTML = """
<html>
<head>
<title>SpaLink Controller</title>
<script language="Javascript">

if (window.XMLHttpRequest) {
    var xmlHttpReqKey = new XMLHttpRequest();
    var xmlHttpReqScreen = new XMLHttpRequest();
    var xmlHttpReqStatus = new XMLHttpRequest();
} else {
    var xmlHttpReqKey = new ActiveXObject("Microsoft.XMLHTTP"); 
    var xmlHttpReqScreen = new ActiveXObject("Microsoft.XMLHTTP");
    var xmlHttpReqStatus = new ActiveXObject("Microsoft.XMLHTTP");
}

function screen() { /* Ping-pong between lights and lcd */
    xmlhttpPost(xmlHttpReqStatus, "/spastatus.cgi", "", "cstat");
}

function cstat() {
    xmlhttpPost(xmlHttpReqScreen, "/spascreen.cgi", "", "screen");
}

function sendkey(key) {
    xmlhttpPost(xmlHttpReqKey, "/spakey.cgi", "key="+key);
}

function xmlhttpPost(xmlReq, strURL, params, update) {
    xmlReq.open('POST', strURL, true);
    xmlReq.setRequestHeader("Content-type","application/x-www-form-urlencoded");
    xmlReq.send(params);
    if (update != "") {
      xmlReq.onreadystatechange = function() {
        if (xmlReq.readyState == 4) {
            updatepage(xmlReq.responseText, update);
        }
      }
    }
    xmlReq.send();
}

function updatepage(str, div){
    document.getElementById(div).innerHTML = str;
    setTimeout(window[div](), 125);
}

</script>
</head>
<body onload="cstat(); screen();">
<table>
<tr>
<td><div id="screen"></div></td>
<td>
<table>
<tr>
<td>&nbsp;</td>
<td><button onclick="sendkey('1')";>Spa</button></td>
<td><button onclick="sendkey('2')";>Spa Heat</button></td>
<td><button onclick="sendkey('3')";>Jet Pump</button></td>
<td><button onclick="sendkey('4')";>Waterfall</button></td>
</tr>
<tr>
<td><button onclick="sendkey('*')";>*</button></td>
<td><button onclick="sendkey('5')";>Pool Light (+)</button></td>
<td><button onclick="sendkey('6')";>Spa Light (-)</button></td>
<td><button onclick="sendkey('7')";>Waterfall Light</button></td>
<td><button onclick="sendkey('8')";>Aux 6</button></td>
</tr>
</table>
</td>
</tr>
<tr><td>STATUS:</td><td colspan="4"><div id="cstat"></div></td></tr>
</table>

</body>
</html>
"""

PORT = 80


class webHandler(BaseHTTPRequestHandler):
    """CGI and dummy web page handler to interface to control objects."""
    screen = None
    spa = None

    def log_request(self, code='-', size='-'):
        """Don't log anything, we're on an embedded system"""
        pass

    def log_error(self, fmt, *args):
        """This was an error, dump it."""
        self.log_message(fmt, *args)

    #Handler for the GET requests
    def do_GET(self):
        """HTTP GET handler, only the html files allowed."""
        if self.path == "/":
            self.path = "/index.html"
        if (self.path  == "/favicon.ico") or (self.path == "favicon.ico"):
            self.send_response(200);
            self.send_header('Content-Type', "image/vnd.microsoft.icon")
            self.end_headers()
            self.wfile.write(FAVICON)
        # We only serve some static stuff
        elif (self.path.startswith("/spa.html") or
           self.path.startswith("/index.html")):
            mimetype = 'text/html'
            ret = ""
            if self.path.startswith("/index.html"):
                ret = INDEXHTML
            elif self.path.startswith("/spa.html"):
                ret = SPAHTML
            self.send_response(200)
            self.send_header('Content-Type', mimetype)
            self.end_headers()
            self.wfile.write(bytearray(ret, "UTF-8"))
        else:
            self.send_error(404, 'File Not Found: %s' % self.path)

    def do_POST(self):
        """HTTP POST handler.  CGI "scripts" handled here."""
        #ctype, pdict = urllib.parse_header(self.headers.get('content-type'))
        m = Message()
        m['content-type'] = self.headers.get('content-type')
        ctype = m.get_params()[0][0]
        try:
            pdict = m.get_params()[1]
        except:
            pdict = {}
        try:
            if ctype == 'multipart/form-data':
                postvars = urllib.parse_multipart(self.rfile, pdict)
            elif ctype == 'application/x-www-form-urlencoded':
                length = int(self.headers.get('content-length'))
                data = self.rfile.read(length).decode("UTF-8")
                postvars = urllib.parse.parse_qs(data, keep_blank_values=1)
            else:
                postvars = {}
        except:
            postvars = {}
        if (self.path.startswith("/key.cgi") or
           self.path.startswith("/spakey.cgi") or
           self.path.startswith("/spabinary.cgi") or
           self.path.startswith("/screen.cgi") or
           self.path.startswith("/spascreen.cgi") or
           self.path.startswith("/status.cgi") or
           self.path.startswith("/spastatus.cgi")):
            mimetype = 'text/html'
            ret = ""
            if self.path.startswith("/key.cgi"):
                if 'key' in postvars:
                    key = postvars['key'][0]
                    self.screen.sendKey(key)
                ret = "<html><head><title>key</title></head><body>"+key+"</body></html>\n"
            elif self.path.startswith("/spakey.cgi"):
                if 'key' in postvars:
                    key = postvars['key'][0]
                    self.spa.sendKey(key)
#                    print "SPA - key "+key
                    ret = "<html><head><title>key</title></head><body>"+key+"</body></html>\n"
            elif self.path.startswith("/spabinary.cgi"):
                ret = self.spa.text() + "|" + time.strftime("%_I:%M%P %_m/%d") + "|"
                if (self.spa.status['spa']=="ON"): ret += "1"
                else: ret += "0"
                if (self.spa.status['heat']=="ON"): ret += "1"
                else: ret += "0"
                if (self.spa.status['jets']=="ON"): ret += "1"
                else: ret += "0"
            elif self.path.startswith("/screen.cgi"):
                ret = self.screen.html()
            elif self.path.startswith("/spascreen.cgi"):
                ret = self.spa.html()
            elif self.path.startswith("/status.cgi"):
                ret = self.screen.status
            elif self.path.startswith("/spastatus.cgi"):
                ret = self.spa.status
            self.send_response(200)
            self.send_header('Content-Type', mimetype)
            self.end_headers()
            self.wfile.write(bytearray(ret, "UTF-8"))
        else:
            self.send_error(404, 'File Not Found: %s' % self.path)


class MyServer(HTTPServer):
    """Override some HTTPServer procedures to allow instance variables and timeouts."""
    def serve_forever(self, screen, spa):
        """Store the screen and spa objects and serve until end of times."""
        self.RequestHandlerClass.screen = screen 
        self.RequestHandlerClass.spa = spa 
        HTTPServer.serve_forever(self)
    def get_request(self):
        """Get the request and client address from the socket."""
        self.socket.settimeout(1.0)
        result = None
        while result is None:
            try:
                result = self.socket.accept()
            except socket.timeout:
                pass
        result[0].settimeout(1.0)
        return result

webServer = False;
def startServer(screen, spa):
    """HTTP Server implementation, to be in separate thread from main code."""
    global webServer
    try:
        webServer = MyServer(('', PORT), webHandler)
        print('Started httpserver on port' , PORT)
        # Wait forever for incoming http requests
        webServer.serve_forever(screen, spa)
    except KeyboardInterrupt:
        print('^C received, shutting down the web server')
#        server.socket.close()
        webServer.shutdown()


class Spa(object):
    """Emulate spa-side controller with LCD display."""
    lock = None
    nextAck = 0x00
    status = {}
    ID = 0x20
    ACK = 0x00

    def __init__(self):
        self.screen = "---"
        self.status = {'spa': "UNK", 'jets': "UNK", 'heat': "UNK"}
        self.nextAck = 0x00
        self.lock = threading.Lock()

    def sendAck(self, i):
        """Tell controller we got messag, including keypresses in response."""
        i.sendMsg(0x00, 0x01, [self.ACK, self.nextAck])
        self.nextAck = 0x00

    def setNextAck(self, nextAck):
        """Set value to send on next controller ping."""
        self.nextAck = nextAck

    def sendKey(self, key):
        """Send a key on the next ack"""
        keyToAck = {'1': 0x09, '2': 0x06, '3': 0x03, '4': 0x08, '5': 0x02, '6': 0x07, '7': 0x04, '8': 0x01, '*': 0x05}
        if key in list(keyToAck.keys()):
            self.setNextAck(keyToAck[key])

    def update(self, args):
        """Update the 7-segment LCD display."""
#        print "SPAUPDATE"
        self.lock.acquire()
        try:
            text = args[1:4]
            if args[1:7] == " . . .":
                self.screen = "... ..."
            else:
                self.screen = text
                if ord(args[5:6]) == 1:
                    self.screen += " SET"
                elif ord(args[9:10]) == 33:
                    self.screen += " AIR"
                elif ord(args[7:8]) == 33:
                    self.screen += " H2O"
                else:
                    print(args.encode("UTF-8").hex())
                if text == "0FF":
                    self.screen = "OFF H2O"
        finally:
            self.lock.release()
#            print "SPATEXT: "+text

    def setStatus(self, stat):
        """Process the status into a string for HTML return"""
        try:
            if ord(stat[0:1]) & 16:
                self.status['spa'] = 'ON'
            else:
                self.status['spa'] = 'OFF'
            if ord(stat[0:1]) & 1:
                self.status['jets'] = 'ON'
            else:
                self.status['jets'] = 'OFF'
            if ord(stat[0:1]) & 8:
                self.status['heat'] = 'ON'
            else:
                self.status['heat'] = 'OFF'
        except:
            self.status = {'spa': "UNK", 'jets': "UNK", 'heat': "UNK"}

    def html(self):
        """Return HTML formatted 7-segment display"""
        self.lock.acquire()
        try:
            ret = "<pre>"
            ret += self.screen
            ret += "</pre>"
        finally:
            self.lock.release()
        return ret

    def text(self):
        """Return plain 7-character display"""
        ret = self.screen
        return ret

    def processMessage(self, ret, i):
        """Handle controller messages to us"""
        if ret['cmd'] == 0x03:  # Text status
#            print "SPA-TEXT"
            self.sendAck(i)
            self.update(ret['args'])
        elif ret['cmd'] == 0x09:  # Change send ??
#            print "SPA-CHANGE"
            self.sendAck(i)
            try:
                equip = ord(ret['args'][0:1])
                state = ord(ret['args'][1:2])
            except:
                pass
        elif ret['cmd'] == 0x02:  # Status binary
#            print "SPA-BSTATUS"
            self.sendAck(i)
            self.setStatus(ret['args'])
        elif ret['cmd'] == 0x00:  # Probe
#            print "SPA-PROBE"
            self.sendAck(i)
        else:
#            print "SPA-UNKCMD"
            self.sendAck(i)


class Screen(object):
    """Emulates the square remote control unit."""
    W = 16
    H = 12
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    lock = None
    nextAck = 0x00
    ID = 0x40
    ACK = 0x8b

    def __init__(self):
        """Set up the instance"""
        self.dirty = 1
        self.screen = self.W * [self.H * " "]
        self.invert = {'line':-1, 'start':-1, 'end':-1}
        self.status = "00000000"
        self.lock = threading.Lock()
        global INDEXHTML
        INDEXHTML = SQUAREHTML

    def setStatus(self, status):
        """Stuff status into a variable, but not used presently."""
        self.status = status

    def cls(self):
        """Clear the screen."""
        self.lock.acquire()
        try:
            for i in range(0, 12):
                self.screen[i] = ""
            self.invert['line'] = -1
            self.dirty = 1
        finally:
            self.lock.release()

    def scroll(self, start, end, direction):
        """Scroll screen up or down per controller request."""
        self.lock.acquire()
        try:
            if direction == 255:  #-1
                for x in range(start, end):
                    self.screen[x] = self.screen[x+1]
                self.screen[end] = self.W*" "
            elif direction == 1:  # +1
                for x in range(end, start, -1):
                    self.screen[x] = self.screen[x-1]
                self.screen[start] = self.W*" "
            self.dirty = 1
        finally:
            self.lock.release()

    def writeLine(self, line, text):
        """"Controller sent new line for screen."""
        self.lock.acquire()
        try:
            self.screen[line] = text + self.W*" "
            self.screen[line] = self.screen[line][:self.W]
            self.dirty = 1
        finally:
            self.lock.release()

    def invertLine(self, line):
        """Controller asked to invert entire line."""
        self.lock.acquire()
        try:
            self.invert['line'] = line
            self.invert['start'] = 0
            self.invert['end'] = self.W
            self.dirty = 1
        finally:
            self.lock.release()

    def invertChars(self, line, start, end):
        """Controller asked to invert chars on a line."""
        self.lock.acquire()
        try:
            self.invert['line'] = line
            self.invert['start'] = start
            self.invert['end'] = end
            self.dirty = 1
        finally:
            self.lock.release()

    def show(self):
        """Print the screen to stdout."""
        self.lock.acquire()
        try:
            if self.dirty:
                self.dirty = 0
                os.system("clear")
                for i in range(0, self.H):
                    if self.invert['line'] == i:
                        sys.stdout.write(self.UNDERLINE)
                    sys.stdout.write(self.screen[i])
                    sys.stdout.write(self.END)
                    sys.stdout.write("\n")
                sys.stdout.write(self.W*"-" + "\n")
                sys.stdout.write("STATUS: " + self.status + "\n")
        finally:
            self.lock.release()

    def html(self):
        """Return the screen as a HTML element (<PRE> assumed)"""
        self.lock.acquire()
        try:
            ret = "<pre>"
            for x in range(0, self.H): 
                if x == self.invert['line']:
                    for y in range(0, self.W):
                        if y == self.invert['start']:
                            ret += "<span style=\"background-color: #FFFF00\"><b>"
                        ret += self.screen[x][y:y+1]
                        if y == self.invert['end']:
                            ret += "</b></span>"
                    if self.invert['end'] == self.W:
                        ret += "</b></span>"
                    ret += "\n"
                else:
                    ret += self.screen[x] + "\n"
            ret += "</pre>"
        finally:
            self.lock.release()
        return ret

    def sendAck(self, i):
        """Controller talked to us, send back our last keypress."""
        i.sendMsg( 0x00, 0x01, [self.ACK, self.nextAck] )
        self.nextAck = 0x00

    def setNextAck(self, nextAck):
        """Set the value we will send on the next ack, but don't send yet."""
        self.nextAck = nextAck

    def sendKey(self, key):
        """Send a key (text) on the next ack."""
        keyToAck = { 'up': 0x06, 'down': 0x05, 'back': 0x02, 'select': 0x04, 'pgup': 0x01, 'pgdn': 0x03 }
        if key in list(keyToAck.keys()):
            self.setNextAck(keyToAck[key])

    def processMessage(self, ret, i):
        """Process message from a controller, updating internal state."""
        if ret['cmd'] == 0x09:  # Clear Screen
            # What do the args mean?  Ignore for now
            if (ord(ret['args'][0:1])==0):
                self.cls()
            else:  # May be a partial clear?
                self.cls()
#                print "cls: "+ret['args'].encode("UTF-8").hex()
            self.sendAck(i)
        elif ret['cmd'] == 0x0f:  # Scroll Screen
            start = ord(ret['args'][:1])
            end = ord(ret['args'][1:2])
            direction = ord(ret['args'][2:3])
            self.scroll(start, end, direction)
            self.sendAck(i)
        elif ret['cmd'] == 0x04:  # Write a line
            line = ord(ret['args'][:1])
            offset = 1
            text = ""
            while ((offset < len(ret['args'])) and (ord(ret['args'][offset:offset+1]) != 0)):
                text += ret['args'][offset:offset+1]
                offset = offset + 1
            # The PDA has a special (double-wide?) mode identified by the MSBs.  Just move them to the top for now
            if line == 64: line = 1   # Time (hex=40)
            if line == 130: line = 2  # Temp (hex=82)
            self.writeLine(line, text)
            self.sendAck(i)
        elif ret['cmd'] == 0x05:  # Initial handshake?
            # ??? After initial turn on get this, rela box responds custom ack
#            i.sendMsg( (chr(0), chr(1), "0b00".decode("hex")) )
            self.sendAck(i)
        elif ret['cmd'] == 0x00:  # PROBE
            self.sendAck(i)
        elif ret['cmd'] == 0x02:  # Status?
            self.setStatus(ret['args'].encode("UTF-8").hex())
            self.sendAck(i)
        elif ret['cmd'] == 0x08:  # Invert an entire line
            self.invertLine( ord(ret['args'][:1]) )
            self.sendAck(i)
        elif ret['cmd'] == 0x10:  # Invert just some chars on a line
            self.invertChars( ord(ret['args'][:1]), ord(ret['args'][1:2]), ord(ret['args'][2:3]) )
            self.sendAck(i)
        else:
            print("unk: cmd=" + toHex(ret['cmd']) + " args=" + ret['args'].encode("UTF-8").hex())
            self.sendAck(i)

class PDA(Screen):
    """Emulates the new PDA-style remote control unit."""
    ID = 0x60
    ACK = 0x40

    def __init__(self):
        """Set up the instance"""
        global INDEXHTML
        super(PDA, self).__init__()
        INDEXHTML = PDAHTML


def log(*args):
    """Set the last log message"""
    global last_log
    message = "%-16s: " % args[0]
    for arg in args[1:]:
        message += arg.__str__() + " "
    print(message)
    last_log =  message + "\n"

def toHex(blist):
    return ''.join(format(x, "02x") for x in blist)

class Interface(object):
    """ Aqualink serial interface """

    def __init__(self, theName):
        """Initialization.
        Open the serial port and find the start of a message."""
        self.name = theName
        if debugData:
            log(self.name, "opening RS485 port", RS485Device)
        self._open()
        self.msg = [0x00, 0x00]
        self.debugRawMsg = []
        # skip bytes until synchronized with the start of a message
        while (self.msg[-1] != STX) or (self.msg[-2] != DLE):
            self.msg += self.port.read(1)
            if debugRaw:
                self.debugRaw(self.msg[-1])
        self.msg = self.msg[-2:]
        if debugData:
            log(self.name, "synchronized")
        # start up the read thread
        log(self.name, "ready")

    def _open(self):
        """Try and connect to the serial port, if it exists.  If not, then
        add a small delay to avoid CPU hogging"""
        try:
            if not os.path.exists(RS485Device):
                print('Serial port \'' + RS485Device + '\' not found.\n')
                sys.exit(-1)
            self.port = serial.Serial(RS485Device, baudrate=9600, 
                                  bytesize=serial.EIGHTBITS, 
                                  parity=serial.PARITY_NONE, 
                                  stopbits=serial.STOPBITS_ONE,
                                  timeout=0.1)
        except:
            self.port = None
         
        
    def readMsg(self):
        """ Read the next valid message from the serial port.
        Parses and returns the destination address, command, and arguments as a 
        tuple."""
        if (self.port == None):
            self._open()  # Try and re-open port
        if (self.port == None):  # We failed, return garbage
            return {'dest':"ff", 'cmd':"ff", 'args':""}

        while True:                                         
            dleFound = False
            # read what is probably the DLE STX
            try:
                self.msg += self.port.read(2)
            except serial.SerialException:
                self.msg += [0x00, 0x00]
                self._open()
            except KeyboardInterrupt:
                print("Keyboard exit requested.")
                return {'stop':'1'}
            while len(self.msg) < 2:
                self.msg += [0x00]
            if debugRaw: 
                self.debugRaw(self.msg[-2])
                self.debugRaw(self.msg[-1])
            while (self.msg[-1] != ETX) or (not dleFound) or (len(self.msg)>128):  
                # read until DLE ETX
                try:
                    if (self.port == None):
                        return {'dest':"ff", 'cmd':"ff", 'args':""}
                    self.msg += self.port.read(1)
                except serial.SerialException:
                    self.msg += [0x00]
                    self._open()
                except KeyboardInterrupt:
                    print("Keyboard exit requested.")
                    return {'stop':'1'}
                if debugRaw:
                    self.debugRaw(self.msg[-1])
                if self.msg[-1] == DLE:                     
                    # \x10 read, tentatively is a DLE
                    dleFound = True
                if (self.msg[-2] == DLE) and (self.msg[-1] == NUL) and dleFound: 
                    # skip a NUL following a DLE
                    self.msg = self.msg[:-1]
                    # it wasn't a DLE after all
                    dleFound = False                        
            # skip any NULs between messages
            while self.msg[0] == 0x00:
                self.msg = self.msg[1:]
            # parse the elements of the message              
            dlestx = self.msg[0:2]
            dest = self.msg[2:3]
            cmd = self.msg[3:4]
            args = self.msg[4:-3]
            ascii_args = str([chr(x) for x in args if chr(x) in string.printable])
            checksum = self.msg[-3:-2]
            dleetx = self.msg[-2:]
            if debugData:
                debugMsg = toHex(dlestx)+" "+toHex(dest)+" "+\
                           toHex(cmd)+" "+toHex(args)+" \""+str(ascii_args)+"\" " +\
                           toHex(checksum)+" "+toHex(dleetx)
            self.msg = []
            # stop reading if a message with a valid checksum is read
            if self.checksum(dlestx + dest + cmd + args) == checksum[0]:
                if debugData:
                    log(self.name, "-->", debugMsg)
                argstr = ""
                for a in args:
                    argstr += chr(a)
                return {'dest': dest[0], 'cmd': cmd[0], 'args':argstr}
            else:
                if debugData:
                    log(self.name, "-->", debugMsg, "*** bad checksum ***")

    def sendMsg(self, dest, cmd, args):
        """ Send a message. """
        msg = [DLE, STX, dest, cmd]
        msg += args
        msg += [self.checksum(msg), DLE, ETX]
        for i in range(2, len(msg) - 2):                       
            # if a byte in the message has the value \x10 insert a NUL after it
            if msg[i] == DLE:
                msg = msg[0:i+1] + [0x00] + msg[i+1:]
        if debugData:
            log(self.name, "<--", toHex(msg[0:2]), 
                toHex(msg[2:3]), toHex(msg[3:4]), 
                toHex(msg[4:-3]), toHex(msg[-3:-2]), 
                toHex(msg[-2:]))
        n = self.port.write(msg)

    def checksum(self, msg):
        """ Compute the checksum of a string of bytes."""
        sum = 0
        for s in msg:
            sum += s
        return sum % 256

    def debugRaw(self, byte):
        """ Debug raw serial data."""
        self.debugRawMsg += [byte]
        if ((len(self.debugRawMsg) == 48) or (byte==ETX)):
            log(self.name, toHex(self.debugRawMsg))
            self.debugRawMsg = []


def parseArgs():
    parser = argparse.ArgumentParser( formatter_class=argparse.RawDescriptionHelpFormatter,
    description="A Python daemon to present a web interface for Jandy pool controls.",
    epilog="Requirements:\n* RS485 interface (default = /dev/ttyUSB0)\n* Jandy remote PDA or OneLink Controller")
    parser.add_argument("--device", "-d", dest = "device", default="/dev/ttyUSB0", 
        help="RS485 device, default=dev/ttyUSB0", required=False)
    parser.add_argument("--spalink", "-s", dest="spalink", action='store_true',
        help="Enable a SPALINK emulator at http://localhost/spa.html", default=False,
        required=False)
    parser.add_argument("--pda", "-p", dest="pda", action='store_true',
        help="Enable a PDA emulator at http://localhost/", default=False,
        required=False)
    parser.add_argument("--aqualink", "-a", dest="aqualink", action='store_true',
        help="Enable a AQUALINK emulator at http://localhost/", default=False, required=False)
    args = parser.parse_args()
    if not os.path.exists( args.device ):
        print("ERROR: Unable to open RS485 device: " + args.device + "\n")
        sys.exit(2)
    if args.pda and args.aqualink:
        print("ERROR: Only one of --pda or --aqualink may be specified, not both.")
        sys.exit(2)
    return args

def main():
    args = parseArgs()
    RS485Device = args.device
    print("Creating RS485 port...")
    i = Interface("RS485")

    if (not args.spalink) and (not args.aqualink) and (not args.pda):
        print("Attempting to auto-detect emulation settings, wait 15 seconds...")
        endTime = time.time() + 15
        while (time.time() < endTime):
            ret = i.readMsg()
            if (ret['dest'] == Screen.ID) and (not args.aqualink):
                print("...Detected old-style Aqualink pad.")
                args.aqualink = True
            if (ret['dest'] == PDA.ID) and (not args.pda):
                print("...Detected new-style Aqualink PDA.")
                args.pda = True
            if (ret['dest'] == Spa.ID) and (not args.spalink):
                print("...Detected SpaLink controller.")
                args.spalink = True
        if args.pda:
            args.aqualink = False
        print("Detection completed...")

 
    """Start the listener for a screen and spa, run webserver."""
    if args.aqualink:
        print("Creating screen emulator...")
        screen = Screen()
    elif args.pda:
        print("Creating PDA emulator...")
        screen = PDA()
    if args.spalink:
        print("Creating spa emulator...")
        spa = Spa()
    else:
        spa = None
    if (not args.spalink) and (not args.aqualink) and (not args.pda):
        print("ERROR: Please specify one or more interfaces to emulate.")
        sys.exit(-1)

    print("Creating web server...")
    server = threading.Thread(target=startServer, args=(screen, spa))
    server.start()

    print("Main loop begins...")
    while True:
        ret = i.readMsg()
        if 'stop' in ret:
            global webServer
            webServer.shutdown()
            return
#        print "ATTN: "+ret['dest'];
        if args.aqualink or args.pda:
            if ret['dest'] == screen.ID:
                screen.processMessage(ret, i)
        if args.spalink:
            if ret['dest'] == spa.ID:
                spa.processMessage(ret, i)

if __name__ == "__main__":
    main()
