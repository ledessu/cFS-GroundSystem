#
#  GSC-18128-1, "Core Flight Executive Version 6.7"
#
#  Copyright (c) 2006-2019 United States Government as represented by
#  the Administrator of the National Aeronautics and Space Administration.
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#!/usr/bin/env python
#

import sys
import os
import socket
import zmq

from PyQt4 import QtGui, QtNetwork, QtCore
from struct import *
from time import sleep

# Receive port where the CFS TO_Lab app sends the telemetry packets
udpRecvPort = 1235

#
# Receive telemetry packets, apply the appropiate header
# and publish the message with zeroMQ
#
class RoutingService(QtCore.QThread):

    def __init__(self, mainWindow):
        QtCore.QThread.__init__(self)
        # Signal to update the spacecraft combo box (list) on main window GUI
        self.signalUpdateIpList = QtCore.SIGNAL("changeIpList")

        # Init lists
        self.ipAddressesList = ["All"]
        self.spacecraftNames = ["All"]
        self.specialPktId = []
        self.specialPktName = []

        # Init zeroMQ
        self.context   = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("ipc:///tmp/GroundSystem")

    # Run thread
    def run(self):
        # Init udp socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', udpRecvPort))

        print ('Attempting to wait for UDP messages')

        socketErrorCount = 0
        while socketErrorCount < 5:

            # Wait for UDP messages
            while True:
                try:
                    # Receive message
                    datagram, host = self.sock.recvfrom(4096) # buffer size is 1024 bytes

                    # Ignore datagram if it is not long enough (doesnt contain tlm header?)
                    if len(datagram) < 6:
                        continue

                    # Read host address
                    hostIpAddress = host[0]

                    #
                    # Add Host to the list if not already in list
                    #
                    if not any(hostIpAddress in s for s in self.ipAddressesList):
                        hostName = 'Spacecraft' + str(len(self.spacecraftNames))
                        my_hostName_as_bytes = str.encode(hostName)
                        print ("Detected " + hostName + " at " + hostIpAddress)
                        self.ipAddressesList.append(hostIpAddress);
                        self.spacecraftNames.append(my_hostName_as_bytes)
                        self.emit(self.signalUpdateIpList, hostIpAddress, my_hostName_as_bytes)

                    # Forward the message using zeroMQ
                    name = self.spacecraftNames[self.ipAddressesList.index(hostIpAddress)]
                    self.forwardMessage(datagram, name)

                # Handle errors
                except socket.error as v:
                    print ('Ignored socket error for attempt %s' % socketErrorCount)
                    socketErrorCount = socketErrorCount + 1
                    sleep(1)

    # Apply header using hostname and packet id and send msg using zeroMQ
    def forwardMessage(self, datagram, hostName):
        # Forward message to channel GroundSystem.<Hostname>.<pktId>
        pktId = self.getPktId(datagram)
        my_decoded_hostName = hostName.decode()
        header = "GroundSystem." + my_decoded_hostName + ".TelemetryPackets." + pktId
        my_header_as_bytes = str.encode(header)
        self.publisher.send_multipart([my_header_as_bytes, datagram])
        #print header


    # Read the packet id from the telemetry packet
    def getPktId(self, datagram):
        # Read the telemetry header
        streamId, Sequence, Length = unpack(">HHH",datagram[:6])
        # Uncomment the next line to debug
        # print "Packet ID = " , hex(streamId)
        return hex(streamId)

    # Close ZMQ vars
    def stop(self):
        self.sock.close()
        self.context.destroy()


