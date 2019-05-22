#!/usr/bin/env python

#Address and port pair of controller, e.g. Pox, Ryu, Floodlight
#contr_addr = "CTRL_ADDR"
contr_addr = ""

# SAVI / OpenStack credentials
username = "netsoft45"
password = "199564a8"
tenant_name = "workshop-9"
region = "EDGE-CG-1"
auth_url = "http://iam.savitestbed.ca:5000/v2.0/"

# Parameters for booting VM
key_name = "netsoft45key"
flavor = "m1.small"
image = "ECE1508-overlay" # Default username/pass of this image is: ubuntu/savi

#  ----------------------- Topology Dictionary ------------------
# Do not connect two VXLANs to the same switch pair while running a simple
# switch controller. This will create a loop in the topology.
#
# The keys of the topology dictionary can only be switches
#
# The values represent the connection to/from that switch. To create a link
# to another switch, just write the switch's name. To represent a connection
# to a host, write down a tuple containing the host name and overlay IP address.
# The saviOverlay script will assume all overlay IPs have a /24 CIDR.
#
# All switch and host names must be unique
#
# Example:
# topology['switch name'] = [ ( 'host name' , 'overlay IP addr'), 'switch' ]

topology = {}
topology["sw1"] = ['sw2',('h1', '192.168.200.10')]
topology["sw2"] = [('h2', '192.168.200.11')]
#topology["sw2"] = ['sw3', ('h2', '192.168.200.11')]
#topology["sw3"] = [('h3', '192.168.200.12')]


