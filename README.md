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
via a web interface.  

You will need a USB RS485 interface, a Raspberry Pi, and either a wireless
or wired connection to your home network.

It emulates a LCD controller and a SpaLink control panel on the web
interface as well as the RS485 bus.

Install and run it from /etc/local.rc on a RaspberryPi and go to:
* LCD Controller:  http://raspi/
* SpaLink:         http://raspi/spalink.html
(where raspi is replaced with your RaspberryPi's IP or hostname)

There is no authentication, so anyone with access to your network has
**unrestricted access**.

Some of the RS485 protocol routine was borrowed from
  https://github.com/ericbuehl/pyaqualink
and some code on the excellent Trouble Free Pool forums:
  http://www.troublefreepool.com/threads/27391-Control-your-Jandy-equipment-from-your-PC-with-a-15-adapter

-Earle F. Philhower, III
 earlephilhower@yahoo.com
