# aquaweb
Control Jandy Aqualink via a web interface from anywhere in the world

## Warnings and Disclaimers
* USE AT YOUR OWN RISK
* DO NOT PUT YOUR POOL ON THE PUBLIC INTERNET.
* DO NOT NAT PORT-FORWARD FROM YOUR ROUTER TO THE CONTROLLER.
* DO NOT PUT THIS ON AN UNSECURED WIFI NETWORK.
* THIS MAY VOID YOUR POOL WARRANTY
* I AM NOT ASSOCIATED WITH JANDY OR RELATED COMPANIES

This Python script allows control of Jandy Aqualink pools with remotes
via a web interface.  Your existing setup needs to already have the 
new-style PDA, old-style square remote or SpaLink installed.

# Square Remote Image
![Square Remote](https://github.com/earlephilhower/aquaweb/blob/master/remote.jpg)

# PDA Remote Image
![PDA Remote](https://github.com/earlephilhower/aquaweb/blob/master/pda.jpg)

# SpaLink Image
![SpaLink Remote](https://github.com/earlephilhower/aquaweb/blob/master/spalink.jpg)

You will need a USB RS485 interface, a Raspberry Pi, and either a wireless
or wired connection to your home network.

It emulates a LCD controller and a SpaLink control panel on the web
interface as well as the RS485 bus.

# Square Remote Web Interface
![Web Interface](https://github.com/earlephilhower/aquaweb/blob/master/remoteweb.jpg)

# PDA Remote Web Interface
![PDA Interface](https://github.com/earlephilhower/aquaweb/blob/master/pdascreen.jpg)

# SpaLink Web Interface
![SpaLink Web](https://github.com/earlephilhower/aquaweb/blob/master/spalinkweb.jpg)

## Usage
With no parameters specified on the command line, it will attempt to use /dev/ttyUSB0
and run an auto-detect routine to see what controllers it can simulate.  To manually
specify which control models, or change the RS485 interface device, the following
options are available:
````
  -h, --help            show this help message and exit
  --device DEVICE, -d DEVICE
                        RS485 device, default=dev/ttyUSB0
  --spalink, -s         Enable a SPALINK emulator at http://localhost/spa.html
  --pda, -p             Enable a PDA emulator at http://localhost/
  --aqualink, -a        Enable a AQUALINK emulator at http://localhost/
````

Install and run it from /etc/local.rc on a RaspberryPi and go to:
* LCD Controller:  http://raspi/
* SpaLink:         http://raspi/spa.html
(where raspi is replaced with your RaspberryPi's IP or hostname)

There is no authentication, so anyone with access to your network has
**unrestricted access**.

Some of the RS485 protocol routine was borrowed from
  https://github.com/ericbuehl/pyaqualink
and some code on the excellent Trouble Free Pool forums:
  http://www.troublefreepool.com/threads/27391-Control-your-Jandy-equipment-from-your-PC-with-a-15-adapter
The PDA style codes were uncovered by @johnnytaco.

-Earle F. Philhower, III
 earlephilhower@yahoo.com
