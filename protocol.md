# My protocol analysis of the old-style Jandy Remote Controls and SpaLink
The following information is my best guess and is in no way warranteed to be
correct or complete, but it seems to work well enough for my own system.
All information only pertains to the old-style square remotes and SpaLink
style controllers.  I have no access to any newer systems, sorry.

All numbers shown below are in hex, but they're obviously binary on the
wire with the appropriate RS485 encoding and checksusm, as described below.

Should there be any discrepencies between this document and the Python
code in aquaweb.py, then assume aquaweb.py is correct.  I've been running
it for several years already as my only remote control for my pool system.

## General notes
All intelligence in the system lies in the main Jandy control unit (i.e.
the big box outside).  The remote terminals, be they SpaLink of the old
Jandy Square remotes, are simply dumb display terminals that can also send
back a single keypress each time they receive new data.

## RS485 format
The wire format is as described much better than at TroubleFreePool.

## Protocol Sequence
JANDY sends: <id><command><data><checksum>

<id> is your device ID, <command> can be anything like "clear screen" or 
"hello" or "scroll up", <data> is variable and optional (often contains
the ASCII strings to display).

You then have XXX ms to respond with an ACK and potentially one-byte payload
containing a keypress, as so:

(REMOTE/SPALINK SENDS): 8b<keycode> (where keycode==0 if no buttons pressed)

The keycode is a binary-encoded version, so you need to identify the exact
pressed buttons.

If you take too long to respond then JANDY will re-send the same command
several times and then assume you've disconnected and you'll need to reconnect
by listening for the "probe" requests on the specific ID.

## Square Remote
The square remote contains a simple
ASCII-based screen of 16x12 characters where each character can be normal
or inverted (i.e. black-on-white or white-on-black).  On the left side
starting at the top there's a "Page Up", "Back", and "Page Down" button.
Underneath the display there's a large "Select" button which activates
the hilighted command, normally.  On the right hand side from the top there
is a "Up" and "Down" button.

The display itself keeps all 16x12 characters in memory, but the actual
intelligence as to what those mean, what a button does, etc. is handled
in the JANDY main control box.  After every command or ping, the remote can
send a single button event to the JANDY control box which will can, in
turn, cause another command to be sent to the remote ad. infinitum.

Note that there is only one global INVERT region.  Setting 

To draw the screen, the main JANDY box sends a "cls" and then sends a series
of "writeline" commands to populate all rows.

### Square Remote ID
My remote ID is "40" but there may be up to 4 from "40" to "43" active.

### Square Remote Commands
09<optional?>: CLEARSCREEN
* I have seen an optional data byte, but it doesn't seem to be needed to work properly.
* Clears the invert region

0f<start><end><direction>: SCROLLSCREEN
* If direction == ff => scroll up lines from [start, end]. Clear out the starting line.
* If direction == 01 => scroll down lines from [start, end]. Clear out the ending line.

04<line><byte1><byte2>...00 : WRITELINE
* Clear <line> then write the byte sequence to it (already ASCII encoded)

00: PROBE/HANDSHAKE
05: PROBE/HANDSHAKE
* Return an ACK to tell the JANDY controller you're present and ready to accept commands.

08<line> : INVERTLINE
* Set the entire screen <line> to inverted

10<line><startchar><endchar>: INVERTCHARS
* Set the characters from <startchar> to <endchar> on <line> to inverted

And that's all I've seen, really.  It's enough to display all menus and update all
settings like clock and schedules.

### Square Remote ACK/keypress values
When a button is pressed you need to record that fact and wait for a message back
to you.  The JANDY main unit will send periodic HANDSHAKE messages (>1 per second
in my experience) so there will be some lag, but it's boundd.

Once you get a message directed to you, any message at all, you send an ACK (8b)
byte followed by a keypress code.  The keypress codes I have on my remote are:
pageup: 01
back: 02
pagedown: 03
select: 04
down: 05
up: 06

## SpaLink ID
The SpaLink ID is "20" but again there may be multiple from "20" to "23".

The spalink "display" consists of an encoded 7 digit 7-segment LCD and several LED lights.
You get periodic updates on the equipment state and what to show on the LCD, and swnd
back any keypresses you've had since your last message just like the square remote.

### Spalink Remove Commands
