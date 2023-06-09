import time, asyncio, os, pytimeparse, datetime, requests, random, math,json
from datetime import datetime, timedelta
from octorest import OctoRest
from firebase_admin import credentials, initialize_app, storage, firestore
import firebase_admin
from firebase_admin import credentials

cred = credentials.Certificate(r"C:\Users\LOKrollJ51\Downloads\liminal-302-firebase-adminsdk-u4wul-dca5458090.json")
firebase_admin.initialize_app(cred,{'storageBucket': 'liminal-302.appspot.com'})
db = firestore.client()
prints_ref = db.collection('prints')
bucket = storage.bucket()
def make_client(url, apikey):
    """Creates and returns an instance of the OctoRest client.

    Args:
        url - the url to the OctoPrint server
        apikey - the apikey from the OctoPrint server found in settings
    """
    try:
        client = OctoRest(url=url, apikey=apikey)
        return client
    except ConnectionError as ex:
        # Handle exception as you wish
        print(ex)
class IndividualPrint():
    def __init__(self, file, creator, material, printerCode, nickname):
        self.file = file
        self.creator = creator
        self.material = material
        gcodeData = parseGCODE(file)[1]
        #TIME TO PRINT IS IN
        #self.timeToPrint = gcodeData[1]
        #self.nozzle = gcodeData[0]
        self.printerCode = printerCode.upper()
        self.nickname = nickname
        #Add implementation to check UUID to ensure it isn't the 0.007% chance they're the same
        passed_check = False
        while not passed_check:
            uuid = printerCode
            letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v',
             'w', 'x', 'y', 'z']
            for i in range(3):
                uuid += random.choice(letters).upper()

            current_year = datetime.now().year
            two_letter_year = str(current_year)[2:]
            uuid += two_letter_year
            query_ref = prints_ref.where('uuid', '==', uuid)

            if len(query_ref.get()) == 0:
                passed_check = True
            else:
                print(query_ref.count)

        self.uuid = uuid
class SinglePrinter():
    """"
    This creates a basic printer class with additional information
    """
    def __init__(self, nickname, url, key, code):
        self.nickname = nickname
        self.code = code
        self.url = url
        self.key = key
        self.state = None
        #Idle, Printing, Offline
       #self.color = color
        try:
            self.printer = make_client(url = url, apikey= key)
            self.printer.connect()
        except Exception:
            self.printer = None
        #self.printer.home()
        self.user = None
        self.currentFile = None
        if self.printer != None:
            self.state = self.printer.state()

        else:
            self.state = "offline"
        #operational
        #paused
        #printing
        #pausing
        #cancelling
        #sdReady means the printer’s SD card is available and initialized
        #error
        #ready
        #closedOrError means the printer is disconnected (possibly due to an error)
        self.queue = []



    def preheat(self):
        """
        Preheats to PLAs target temp
        """
        self.printer.bed_target(60)
        self.printer.tool_target(210)
    def cooldown(self):
        """
        Cools down the printer
        """
        self.printer.bed_target(0)
        self.printer.tool_target(0)

    def uploadLocal(self, filepath, fileName : str, uploader):
        """
        Only useful for testing. Will not work/will be useless in full implementation
        """
        file = open(filepath, "rb")
        file_contents = file.read()
        self.printer.upload(file = (fileName, file_contents), location= "local",print= True)
        self.printer.select(location= fileName, print= True)
        self.currentFile = file_contents
        self.user = uploader
    def upload(self, print : IndividualPrint):
        """
        Uploads using a IndividualPrint Object
        """

        file_contents = requests.get(print.file).text
        self.printer.upload(file = (print.nickname + ".gcode", file_contents), location= "local",print= True)
        time.sleep(1)
        self.printer.select(location= print.nickname + ".gcode", print= True)
        self.currentFile = file_contents
        self.user = print.creator

    def abort(self):
        self.printer.cancel()
        #Used for implementing LED Methods + Sending notifications
    def fetchNozzleTemp(self):
        return self.printer.tool(history = True, limit = 1)["tool0"]
    def fetchBedTemp(self):
        return self.printer.bed(history = True, limit = 1)["bed"]
    def fetchTimeRemaining(self):
        '''
        Returns time remaining in seconds
        '''
        if self.printer.job_info()["progress"]["printTimeLeft"] != None:
            return self.printer.job_info()["progress"]["printTimeLeft"]
        else:
            return -60

    def scheduler(self, gcode: IndividualPrint, requestedTime):
        times = []
        gaps = []
        for print in self.queue:
            times.append(print.estimatedStartTime)
            times.append(print.estimatedEndTime)
        times.pop(0)
        times.pop(-1)
        for item in range(0, len(times), 2):
            gaps += (times[item], times[item + 1], times[item + 1] - times [item])
            #Appends a tuple containing the gaps start, and the gaps end, and a timedelta object of the time between


    def addToQueueOld(self, gcode: IndividualPrint):
        officeHours = [(datetime.time(hour= 18), datetime.time(hour= 21))]

        info = self.printer.job_info()
        startTime = datetime.now()
        nextAvilableStart = 0
        printTime = gcode.timeToPrint
        if info["state"] == "Printing":
            remaining = info["progress"]["printTimeLeft"]
            remaining += (10 * 60) #Adds to minute buffer in seconds
            nextAvilableStart += remaining
        startTime += datetime.timedelta(seconds=nextAvilableStart)
        for set in officeHours:
            if datetime.time > set[0] and datetime < set[1] and startTime >= set[1]:
                print("yuh")
        #If we're within this set off office hours and the current print will end outside of them

        #Gap optimization algorithm
        for singlePrint in self.queue:
            #Calculating the timedelta between the requested print time and the current estimated next avilable start time
            #If that gap is greater than the time to print, slot that print in.
            if (singlePrint.estimatedStartTime - startTime) > gcode.timeToPrint:
                self.queue.insert(self.queue.index(singlePrint), gcode)
                #Setting the object it's estimated start time
                gcode.estimatedStartTime = startTime
                break



#class PrintUpload():
 #   def __init__(self, gcode, uploader):
  #      self.gcode = gcode
   #     self.uploader = uploader

class Liminal():

    def __init__(self):
        self.config = json.load(open("config.json"))
        self.printers = []
        self.accounts = list(self.config["students"].keys())
        for item in self.config:
            if "ipAddress" in self.config[item]:
                self.printers.append(SinglePrinter(item, self.config[item]["ipAddress"], self.config[item]["apiKey"], self.config[item]["prefix"]))
        self.state = "idle"
        self.estimatedBufferTime = 10
        self.approvalCode = "null"
        self.lastGenerated = None


        #State Map
        #Idle: All printers are OK, nothing printing
        #Printing: One or more printers are ongoing, printers OK
        #Error: The printers detected an issue, no connection or other
        #Stop: All printers have been immediately e-stopped
        #self.officeHours = [(datetime.hour(hour=18), datetime.time(hour=21))]
    async def genNewApprovalCode(self):
        while True:
            uuid = ""
            letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v',
                           'w', 'x', 'y', 'z']
            for i in range(4):
                uuid += random.choice(letters).upper()
            self.approvalCode = uuid
            self.lastGenerated = datetime.now()
            print(uuid)
            await asyncio.sleep(10)
    def estop(self):
        for printer in self.printers:
            printer.abort()
        #Implement methods for display & mobile notifications to dispatch





def parseGCODELocal(filepath):
    file = open(filepath, "r")
    file_contents = file.read()
    file_contents = file_contents.split(";")
    printTime = [item for item in file_contents if item.startswith(" estimated printing time (normal mode)")][0]
    #Above, getting the print time from the GCODE. Below, parsing the string to extract the timing
    printTime = printTime.strip(" estimated printing time (normal mode) = ")
    printTime = printTime.strip("\n")
    timeInSec = pytimeparse.parse(printTime)
    timeDelta = timedelta(seconds= timeInSec)
    #Below, getting nozzle diameter for print
    nozzleDiameter = [item for item in file_contents if item.startswith(" nozzle_diameter = ")][0]
    nozzleDiameter = nozzleDiameter.strip(" nozzle_diameter = ")
    nozzleDiameter = nozzleDiameter.strip("\n")

    return [nozzleDiameter, timedelta.seconds]
def parseGCODE(link):
    file = requests.get(link).text
    file_contents = file
    file_contents = file_contents.split(";")
    printTime = [item for item in file_contents if item.startswith(" estimated printing time (normal mode)")][0]
    #Above, getting the print time from the GCODE. Below, parsing the string to extract the timing
    printTime = printTime.strip(" estimated printing time (normal mode) = ")
    printTime = printTime.strip("\n")
    timeInSec = pytimeparse.parse(printTime)
    timeDelta = timedelta(seconds= timeInSec)
    #Below, getting nozzle diameter for print
    nozzleDiameter = [item for item in file_contents if item.startswith(" nozzle_diameter = ")][0]
    nozzleDiameter = nozzleDiameter.strip(" nozzle_diameter = ")
    nozzleDiameter = nozzleDiameter.strip("\n")

    return [nozzleDiameter, timedelta.seconds]
#Left Printer,http://10.110.8.77 ,FCDAE0344C424542B80117AF896B62F6
#Middle Printer, http://10.110.8.110, 6273C0628B8B47E397CA4554C94F6CD5
#Right Printer,http://10.110.8.100 ,33A782146A5A48A7B3B9873217BD19AC

#spencer = SinglePrinter("Middle", "http://10.110.8.110","6273C0628B8B47E397CA4554C94F6CD5")
#spencer.printer.jog(x=5)

#myPrinter.printer.disconnect()

#Sort by queued prints and if time is now or past and state is unchanged, queue to print on printer
liminal = Liminal()
print(liminal.printers)


