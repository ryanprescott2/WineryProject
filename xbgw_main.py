import os
import os.path
import fcntl
import sys
import atexit
sys.path.append("xbgw.zip")
sys.path.insert(0,"/userfs/WEB/python/awsmqttlib/")
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import asyncore
import logging
import xbee
from pubsub import pub
import pubsub.pub
import threading
import time
import base64
import re
import select
import socket
import datetime
from socket import *
from select import *
from datetime import datetime, timedelta
from collections import deque
from xbgw.xbee.manager import XBeeEventManager
from xbgw.xbee.ddo_manager import DDOEventManager
from xbgw.reporting.device_cloud import wrap, id_to_stream, get_type
from xbgw.command.rci import RCICommandProcessor
from xbgw.settings import SettingsRegistry, SettingsMixin, Setting
from xbgw.debug.echo import EchoCommand

from ConfigParser import SafeConfigParser

try:
    from build import version
except ImportError:
    version = "None"

SETTINGS_FILE = "xbgw_settings.json"
PID_FILE = "xbgw.pid"

awsClient = AWSIoTMQTTClient("connectport")
awsClient.configureEndpoint("a2uxgca99ev3iu-ats.iot.us-west-2.amazonaws.com", 8883)
awsClient.configureCredentials("/userfs/WEB/python/certs/AmazonRootCA1.pem", "/userfs/WEB/python/certs/965e2a8102-private.pem.key", "/userfs/WEB/python/certs/965e2a8102-certificate.pem.crt")
awsClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
awsClient.configureDrainingFrequency(2)  # Draining: 2 Hz
awsClient.configureConnectDisconnectTimeout(10)  # 10 sec
awsClient.configureMQTTOperationTimeout(5)  # 5 sec
awsClient.connect()

#ROUTER_ID_ARRAY = [("[0005]!"), ("[00:13:a2:00:41:93:b7:a8]!"), ("[00:13:a2:00:41:93:b8:88]!"), ("[00:13:a2:00:41:93:b8:81]!"), ("[00:13:a2:00:41:93:b8:96]!"), ("[00:13:a2:00:41:93:b8:c4]!"), ("[00:13:a2:00:41:93:b7:b7]!"), ("[00:13:a2:00:41:93:b7:a5]!"), ("[00:13:a2:00:41:93:b7:c0]!"), ("[00:13:a2:00:41:93:b8:db]!"), ("[00:13:a2:00:41:93:b9:23]!"), ("[00:13:a2:00:41:93:b7:a2]!"), ("[00:13:a2:00:41:93:b8:ed]!"), ("[00:13:a2:00:41:93:b7:84]!"), ("[00:13:a2:00:41:93:b8:74]!"), ("[00:13:a2:00:41:93:b7:9f]!")];
#ROOM_ID_ARRAY = [("Main"),("AWSTest10"),("AWSTest11"),("AWSTest12"),("AWSTest13"),("AWSTest14"),("AWSTest15"),("AWSTest16"),("AWSTest17"),("AWSTest18"),("AWSTest19"),("AWSTest20"), ("AWSTest21"), ("AWSTest22"), ("AWSTest23"), ("AWSTest24")];
#NumNodes = 16;

#READ config file
print("xbgw_main.py VERSION 7\n")
parser = SafeConfigParser()
parser.read('config.ini')
waketime = int(parser.get('node_config', 'wake_time'))
ROUTER_ID_ARRAY =  parser.get('gateway_config', 'ROUTER_ID_ARRAY').split('\n')
ROOM_ID_ARRAY = parser.get('gateway_config', 'ROOM_ID_ARRAY').split('\n')
REBOOT_STATUS_ARRAY = parser.get('node_config', 'REBOOT_STATUS_ARRAY').split('\n')
GATEWAY_ID = parser.get('gateway_config', 'gateway_name')
NumNodes = int(parser.get('gateway_config', 'node_count'))

facilityID = parser.get('gateway_config', 'facility_name')
PCFile = str("/userfs/WEB/python/" + facilityID + "_" + GATEWAY_ID + "_ParseFile.txt");
BatFile = str("/userfs/WEB/python/" + facilityID + "_" + GATEWAY_ID + "_BatFile.txt");
DustFile = str("/userfs/WEB/python/" + facilityID + "_" + GATEWAY_ID + "_DustFile.txt");
JCSLogFile = str("/userfs/WEB/python/" + facilityID + "_" + GATEWAY_ID + "_LogFile.txt");

logFileID = open(JCSLogFile,'a');
logFileID.write("Startup Initiated\r\n");
logFileID.close();

NumRcvBytes = 18;
NumDataBytes = 17;
NumSatBytes = 16;
NumBatBytes = 3;

BatArray = [0 for x in range(NumBatBytes)];
bufferArray = [[0 for x in range(NumDataBytes)] for x in range(NumNodes)];
bufferStatus = [0 for x in range(NumNodes)];
repeatStatus = [0 for x in range(NumNodes)];

writeData = 0;
repeatFlag = 0;
#waketime = 2;

#TODO for loop assigning all the reboot values
#TODO assign all the config values here, and then again every wake_time interval
#TODO add gateway ID to amazon data
#TODO make sure it is equipped for all 20 nodes
# get current time
def getClock():
	clock_temp = time.localtime();
	clock = [clock_temp[0] - 2000, clock_temp[1], clock_temp[2], clock_temp[3], clock_temp[4], clock_temp[5]];
	return clock;

# get current second
def getSecond():
	clock_temp = time.localtime();
	second = clock_temp[5];
	return second;

# get current minute
def getMinute():
	clock_temp = time.localtime();
	minute = clock_temp[4];
	return minute;

# send clock to specified address
def sendClock(src_addr_clock):
    print("Sending Clock to %s" %ROOM_ID_ARRAY[(ROUTER_ID_ARRAY.index(src_addr_clock[0]))] )
    logFileID = open(JCSLogFile,'a');
    logFileID.write("Sending Clock to " + ROOM_ID_ARRAY[(ROUTER_ID_ARRAY.index(src_addr_clock[0]))] + "\r\n");
    logFileID.close();
    clock = getClock();
    for k in range(6):
        if (clock[k] < 10):
            manager.socket.sendto('0',0,src_addr_clock);
        manager.socket.sendto(str(clock[k]),0,src_addr_clock);

class PubsubExceptionHandler(pub.IListenerExcHandler):
    def __init__(self):
        pass

    def __call__(self, raiser, topicObj):
        import traceback
        tb = traceback.format_exc()
        logger = logging.getLogger()
        logger.error("PubSub caught exception in listener %s:\n%s", raiser, tb)

def produce(buffer_in,src_addr):
    nodeID = None
    parser.read('config.ini')
    waketime = int(parser.get('node_config', 'wake_time'))
    ROUTER_ID_ARRAY =  parser.get('gateway_config', 'ROUTER_ID_ARRAY').split('\n')
    ROOM_ID_ARRAY = parser.get('gateway_config', 'ROOM_ID_ARRAY').split('\n')
    REBOOT_STATUS_ARRAY = parser.get('node_config', 'REBOOT_STATUS_ARRAY').split('\n')
    GATEWAY_ID = parser.get('gateway_config', 'gateway_name')
    NumNodes = int(parser.get('gateway_config', 'node_count'))

    facilityID = parser.get('gateway_config', 'facility_name')
    global writeData;
    count = 0
    for i in ROUTER_ID_ARRAY:
        if (i == src_addr[0]):
            nodeID = count
        count += 1
    logFileID = open(JCSLogFile,'a');
    ts = datetime.now().strftime('%m/%d/%Y %H:%M');
    logFileID.write("Received data: " + buffer_in + " - from: " + ROOM_ID_ARRAY[nodeID] + " at time " + ts + "\r\n");
    print(" >> Received data: %s - from %s" %(buffer_in,ROOM_ID_ARRAY[nodeID]))
    logFileID.close();

    if (len(buffer_in) == 1 and buffer_in == 'c'): #send clock if recv is C
        sendClock(src_addr);
    elif (len(buffer_in) == 1 and buffer_in == 'p'):
        temp = nodeID + 9; #add 9 for PSoC code use (so each node ID is 2 bytes)
        manager.socket.sendto(str(temp),0,src_addr);
        print("Node ID sent to %s" %ROOM_ID_ARRAY[nodeID]);
        logFileID = open(JCSLogFile,'a');
        logFileID.write("Sending node ID to " + ROOM_ID_ARRAY[nodeID] + "\r\n");
        logFileID.close();
        #TODO need to look at PSoC code to determine how this is read in
    #elif (len(buffer_in) == 1 and buffer_in == 'r'): #send back reboot status
        #manager.socket.sendto(REBOOT_STATUS_ARRAY[nodeID],0,src_addr);
    elif (len(buffer_in) == 1 and buffer_in == 'u'): #send back wake time change
        manager.socket.sendto(str(waketime), 0, src_addr);
    elif (len(buffer_in) == NumBatBytes):
        for k in range(NumBatBytes):
            BatArray[k] = ord(buffer_in[k]);

        bData = ((BatArray[0]-48) + (BatArray[1]-48)*0.1 + (BatArray[2]-48)*0.01);

        batPercent = -36.165*bData*bData*bData + 368.79*bData*bData - 1122.1*bData + 985.78;
        if (batPercent > 100):
            batPercent = 100;
        elif(batPercent < 0):
            batPercent = 0;
        strPercent = "%.1f" % batPercent;

        ts = datetime.now().strftime('%m/%d/%Y %H:%M');
        body = str(facilityID + "." + ROOM_ID_ARRAY[nodeID] + ".Bat," + ts + "," + strPercent);
        awsClient.publish("AWSTest", """{ \"FacilityID\": \"%s\", \n
                                        \"GatewayID\": \"%s\", \n
                                        \"NodeID\": \"%s\", \n
                                        \"Battery\": \"%s\", \n
                                        \"TimeSent\": \"%s\" \n }""" %(facilityID, GATEWAY_ID, ROOM_ID_ARRAY[nodeID], strPercent, ts), 0)
        fBatID = open(BatFile,'a');
        fBatID.write(body + "\r\n");
        fBatID.close(); #send battery data
    elif(repeatStatus[nodeID] == 1):    #TODO need to reset repeatStatus[] to zeros, don't know when
        manager.socket.sendto('g',0,src_addr);
        manager.socket.sendto('g',0,src_addr);
        manager.socket.sendto('g',0,src_addr);

        print("Data already sent!")

    elif (len(buffer_in) == NumSatBytes or len(buffer_in) == NumRcvBytes):
        checksumTotal = 0;
        for k in range(len(buffer_in) - 1):
            checksumTotal = checksumTotal + ord(buffer_in[k + 1])

        checksum = checksumTotal % 256;
        logFileID = open(JCSLogFile,'a');
        logFileID.write("Sent checksum is: " + str(ord(buffer_in[0])) + ", Checksum is: " + str(checksum) + "\r\n");
        logFileID.close();

        #print("Calced Checksum %s" %checksum)
        #print("Sent Checksum %s" %ord(buffer_in[0]))

        if (checksum == ord(buffer_in[0])): #and timeoutFlag == 0): #if valid checksum
            manager.socket.sendto('g',0,src_addr);
            manager.socket.sendto('g',0,src_addr);
            manager.socket.sendto('g',0,src_addr);
            print("Checksum matches for %s" %ROOM_ID_ARRAY[nodeID])
            logFileID = open(JCSLogFile,'a');
            logFileID.write("Checksum matches for " + ROOM_ID_ARRAY[nodeID] + "\r\n");
            logFileID.close();
            writeData = 1;
            bufferStatus[nodeID] = 1;   #data exists in this buffer
            repeatStatus[nodeID] = 1;
            for k in range(len(buffer_in) - 1):
                bufferArray[nodeID][k] = ord(buffer_in[k + 1]);
        else: # invalid checksum
            manager.socket.sendto('m',0,src_addr);
    else:
        manager.socket.sendto('i',0,src_addr); #incorrect amount of data sent

    if (writeData == 1): #we do not need to wait for the busy period for data to be written, as the API takes care of data queueing already for us.
        writeData = 0;
        logFileID = open(JCSLogFile,'a');
        logFileID.write("Uploading data to AWS.\r\n");
        print("Uploading data to AWS.")
        logFileID.close();
        fPCID = open(PCFile,'a');
        if(bufferStatus[nodeID] == 1): #if there is an item in the buffer
            bufferStatus[nodeID] = 0;
            hData = "%.1f" % ((bufferArray[nodeID][2]-48)*10 + (bufferArray[nodeID][3]-48) + (bufferArray[nodeID][4]-48)*0.1);
            tData = "%.1f" % ((bufferArray[nodeID][7]-48)*10 + (bufferArray[nodeID][8]-48) + (bufferArray[nodeID][9]-48)*0.1);
            zData = "%05i" % ((bufferArray[nodeID][10]-48)*10000 + (bufferArray[nodeID][11]-48)*1000 + (bufferArray[nodeID][12]-48)*100 + (bufferArray[nodeID][13]-48)*10 + (bufferArray[nodeID][14]-48));

            ts = datetime.now().strftime('%m/%d/%Y %H:%M');
            awsClient.publish("AWSTest", """{ \"FacilityID\": \"%s\", \n
                                           \"GatewayID \": \"%s\", \n
                                           \"NodeID\": \"%s\", \n
                                           \"Humidity\": \"%s\", \n
                                           \"Temperature\": \"%s\", \n
                                           \"CO2\": \"%s\", \n
                                           \"TimeSent\": \"%s\" \n }""" %(facilityID, GATEWAY_ID, ROOM_ID_ARRAY[nodeID], hData, tData, zData, ts), 0)

            logFileID = open(JCSLogFile,'a');
            logFileID.write("Upload complete.\r\n");
            print("Upload complete")
            logFileID.close();

            body = str(facilityID + "." + ROOM_ID_ARRAY[nodeID] + ".Humidity," + ts + "," + hData);
            fPCID.write(body + "\r\n");

            body = str(facilityID + "." + ROOM_ID_ARRAY[nodeID] + ".Temp," + ts + "," + tData);
            fPCID.write(body + "\r\n");

            body = str(facilityID + "." + ROOM_ID_ARRAY[nodeID] + ".CO2," + ts + "," + zData);
            fPCID.write(body + "\r\n");

            for j in range(NumDataBytes):
                bufferArray[nodeID][j] = 0;
        fPCID.close();

class AWSPush(SettingsMixin):
    def __init__(self, settings_registry, settings_binding="device cloud"):
        logger = logging.getLogger(__name__)
        logger.info("Initializing AWSReporter")

        settings_list = [
            # Should serial data be base64-encoded before upload?
            Setting(name="encode serial", type=bool, required=False,
                    default_value=False)
        ]

        # Necessary before calling register_settings to initialize state.
        SettingsMixin.__init__(self)
        self.register_settings(settings_registry, settings_binding,
                               settings_list)


        self._topic_registry = {}
        self._work = deque()
        self._work_event = threading.Event()
        self._work_lock = threading.RLock()
        self._last_upload = 0

        self._RETRY_TIME = 5  # seconds to wait upon upload failure
        self._RETRY_COUNT = 3  # Will attempt upload this many times
        # Below value is for DC Free/Developer tier.  Standard tier
        # and above can change this to one second
        self._RATE_LIMIT = 5  # seconds between uploads to DC, per DC throttles
        self._MAX_QUEUE_SIZE = 5000  # items

        # 249 because DC counts the header line, while we only count
        # the DataPoints, leading to an off-by-one disagreement
        self._MAX_PER_UPLOAD = 249  # datapoints per upload

        self._thread = threading.Thread(target=self.__thread_fn)
        self._thread.daemon = True
        self._thread.start()

    def start_reporting(self, topic):
        """Subscribe to pubsub data on the given topic name

        The topic must conform to the MDS documented in the
        DeviceCloudReporter class docstring (ident and value).
        """
        # Grab and hold a reference for just this topic to support
        # unregistration later
        listener = wrap(self.__my_listener)
        self._topic_registry[topic] = listener
        pubsub.pub.subscribe(listener, topic)

    def stop_reporting(self, topic):
        """Unsubscribe from pubsub data on the given topic name

        Will raise KeyError if the topic has not been subscribed to
        (see start_reporting).
        """
        # Removing reference unsubscribes from pubsub (unless owned elsewhere)
        del self._topic_registry[topic]

    def __my_listener(self, topic=pubsub.pub.AUTO_TOPIC, ident=None, value=None, **kwargs):

        # topic is a Topic object. We only care about the topic name.
        # Line confuses pylint; topic re-typed as TopicObj
        topic = topic.getName()  # pylint: disable=maybe-no-member
        logger = logging.getLogger(__name__)
        logger.debug("%s from %s", topic, ident)
        logger.debug(
            "Topic %s, ident %s, value %s with extra data %s",
            topic, ident, value, kwargs)

        with self._work_lock:
            if len(self._work) >= self._MAX_QUEUE_SIZE:
                self._purge_work()

            self._work.append((topic, ident, value, kwargs, time.time()))
            self._work_event.set()

    def _purge_work(self):
        logger.error("Max queue size exceeded, purging queue")
        self._work.clear()

    def __thread_fn(self):
        global repeatFlag
        while True:
            if len(self._work) == 0:
                while(self._work_event.isSet() == 0):
                    if ((getMinute() % waketime) == 0 and getSecond() == 0 and repeatFlag == 0): #2->15 TODO
                        for k in range(NumNodes):
                            repeatStatus[k] = 0;
                        repeatFlag = 1;
                    elif (not((getMinute() % waketime) == 0 and getSecond() == 0) and repeatFlag == 1): #2->15 TODO
                        repeatFlag = 0;
            # Avoid throttling
            next_report = self._last_upload + self._RATE_LIMIT - time.time()
            if next_report > 0:
                logger = logging.getLogger(__name__)
                print("\n Sleeping and receiving data for %f" %next_report)
                time.sleep(next_report)

            if len(self._work) == 0:
                logger.warning("Lost expected data while sleeping.")
            else:
                self._publish_stream()

            with self._work_lock:
                if len(self._work) == 0:
                    # Exhausted the work available
                    self._work_event.clear()

    def _publish_stream(self): # Performs an upload of all data, honoring limits

        filename = "DataPoint/upload.csv"
        #logger.info("Uploading data to %s", filename)
        logger = logging.getLogger(__name__)
        logger.info("Uploading data to AWS")

        body = self._build_body()

        self._upload(body, filename)
        self._last_upload = time.time()

    def _build_body(self):
        lines = ['#TIMESTAMP,DATA,DATATYPE,STREAMID']
        count = 0

        # pylint: disable=maybe-no-member
        while len(self._work) != 0 and count < self._MAX_PER_UPLOAD:
            # deque append and popleft are thread safe
            topic, ident, value, kwargs, timestamp = self._work.popleft()
            stream_id = "{}/{}".format(topic, id_to_stream(ident))
            logger = logging.getLogger(__name__)
            logger.debug("stream_id: %s", stream_id)

            logger.debug("data: %s", (stream_id, value, kwargs))

            datatype = get_type(value)
            #if type(value) == bool:  # Bools are special, report them as ints
            #    value = int(value)
            #elif type(value) == str:
            #    if self.get_setting("encode serial"):
            #        value = base64.b64encode(value)

            lines.append("{},{},{},{}".format(
                int(timestamp * 1000),
                value,
                datatype,
                stream_id))

            count = count + 1

        print("\n Upload contains %d datapoints" %count)
        logFileID = open(JCSLogFile,'a');
        logFileID.write("Upload contains " + str(count) + "datapoints.\r\n");
        logFileID.close();
        upload_body = ','.join(lines)
        return upload_body

    def _upload(self, body, filename):

        tempArr = body.split(",")
        del tempArr[0:5]
        if(len(tempArr) > 4):
            del tempArr[1::2]
        else:
            del tempArr[1]

        for i, s in enumerate(tempArr):
            if(i%2 == 1):
                tempArr[i] = s[14:]
            #tempArr[i] = tempArr[i].strip('!')

        x = 0
        parsedArr=[]
        while x<len(tempArr):
            parsedArr.append(tempArr[x:x+2])
            x = x + 2

        #print(parsedArr)
        for y in parsedArr:
            produce(y[0],(y[1].lower(),232,49413,17,1,0));
#clock = getClock();
#sendAddr = (y[1],232,49413,17,1,0) #same for every node except first element
#for k in range(6):
#    if(clock[k] < 10):
#        manager.socket.sendto('0',sendAddr)
#    manager.socket.sendto(str(clock[k]),sendAddr)

manager = XBeeEventManager()

logFileID = open(JCSLogFile,'a');
logFileID.write("System Startup.\r\n");
logFileID.close();

def main():
    #setup_logging()

    #logger = logging.getLogger()
    #logger.info("XBGW App Version: {}".format(version))

    # Make sure we're the only instance of the app on this system
    prevent_duplicate(PID_FILE)

    # Catch and log exceptions unhandled by listeners
    pub.setListenerExcHandler(PubsubExceptionHandler())

    # Create the settings file if it does not exist already.
    # TODO: Consider moving into load_from_json as managing the
    # settings file should arguably be done by the SettingsRegistry
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            f.write("{}")

    settings = SettingsRegistry()
    settings.load_from_json(SETTINGS_FILE)


    # Create PubSub participants
    #manager = XBeeEventManager()
    print("Data ready for input.")
    DDOEventManager()
    dcrep = AWSPush(settings, "devicecloud")



    for topic in manager.data_topics:
        dcrep.start_reporting(topic)


    # timeout is 30 seconds by default, but that is far too slow for our
    # purposes. Set the timeout to 100 ms. (Value may be fine tuned later)
    asyncore.loop(timeout=0.1)


def setup_logging():
    FORMAT = '%(message)s' #%(asctime)-15s %(levelname)s %(name)s:
    logging.basicConfig(format=FORMAT)
    logging.getLogger().setLevel(logging.DEBUG)


def prevent_duplicate(pid_filename):
    # Make sure we're the only instance of the app on this system
    pidfile = open(pid_filename, "a+", 0)
    try:
        fcntl.flock(pidfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        logging.getLogger().error(
            "Could not lock PID file, application may already be running")
        sys.exit(-1)

    # Write our PID out
    pidfile.seek(0)
    os.ftruncate(pidfile.fileno(), 0)
    pidfile.write(str(os.getpid()) + '\n')
    pidfile.flush()
    # Keep pidfile open so the lock is held by our process

    atexit.register(cleanup_pidfile, pidfile)


def cleanup_pidfile(pidfile):
    pidfile.close()
    os.remove(PID_FILE)


if __name__ == "__main__":
    main()
