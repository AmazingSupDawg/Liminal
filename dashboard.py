import datetime,json,random,time,string,os,sys, threading, cv2, requests
from flask import Flask, request, send_file, redirect, url_for, Response
from firebase_admin import credentials, initialize_app, storage
from main import IndividualPrint,SinglePrinter, Liminal
import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
liminal = Liminal()


auth = HTTPBasicAuth()

users = {
    "Jack": generate_password_hash("rat"),
    "Luke": generate_password_hash("rat"),
    "Katia": generate_password_hash("rat"),
    "Greysen": generate_password_hash("rat"),
    "Spencer": generate_password_hash("rat"),
    "Chris": generate_password_hash("rat"),
    "Dylan": generate_password_hash("rat"),
    "Mason": generate_password_hash("rat")

}
@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username



bucket = storage.bucket()
db = firestore.client()
prints_ref = db.collection('prints')

if sys.platform == "win32":
    cwd = "C:/Users/jackk/Desktop/Liminal"
else:
    cwd = "/home/jack/Documents/Liminal-master"
#CWD, current working directory, is the directory that the file is in
@app.route('/')
@auth.login_required()
def index():
    file = open((f"{cwd}/ref/values.json"))
    jsonValues = json.load(file)
    file.close()

    file =open((f"{cwd}/ref/config.json"))
    config = json.load(file)
    file.close()
    body = "<html><body style = background-color:black>"
    body += """
    <head>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter">
    </head>
    <style>
    body {
  font-family: "Inter", sans-serif;
    }
    </style>
    """
    for printer in liminal.printers:
        if printer.state == "offline" or printer.state == "closedOrError":
            liminal.printers.remove(printer)
            continue
        if printer.printer != None and printer.code not in jsonValues["printersDown"]:
            body += f'<h1 style="color:coral;"> <a href = {printer.url}>{printer.nickname}</a></h1>'
            body += f'''
            <form action = "{url_for("functions")}" method = post>
            <input type="hidden" name="printer" value="{printer.nickname}">
            <input type = "submit" value = "Preheat"> 
            </form>
            '''
            if "paused" in printer.printer.state().lower():
                body += f'''
                            <form action = "{url_for("resumePrint")}" method = post>
                            <input type="hidden" name="printer" value="{printer.nickname}">
                            <input type = "submit" value = "Resume Print"> 
                            </form>
                            '''
            elif "printing" in printer.printer.state().lower():
                body += f'''
                            <form action = "{url_for("pausePrint")}" method = post>
                            <input type="hidden" name="printer" value="{printer.nickname}">
                            <input type = "submit" value = "Pause Print"> 
                            </form>
                '''
            for camera in liminal.cameras:
                if camera.printer != None and camera.printer.nickname == printer.nickname:
                    body += f"""<img src="{url_for("video_feed", cameraNum = camera.cameraNumber)}" alt="Video Stream">"""
            if printer.fetchNozzleTemp() != None:
                body += f'<h3 style="color:white;">Nozzle: {printer.fetchNozzleTemp()["actual"]}</h3>'
            if printer.fetchBedTemp() != None:
                body += f'<h3 style="color:white;">Bed: {printer.fetchBedTemp()["actual"]}</h3>'
            if "printing" in printer.state.lower() and printer.fetchNozzleTemp()["actual"] >= 200:
                body += f'<h3 style="color:white;">Currently in use | {int(printer.fetchTimeRemaining()/60)} Minutes left</h3>'
                #Implement time remaining methods :)

            else:
                #Submission requrements:
                # printer : Printer Name ex. Left Printer
                # Gcode : The GCODE file
                # creator: The name of the uploader
                # material: The name of the filament, currently unused
                # printercode: unestablished right now, but is a needed input
                # nickname: The name of the print
                #<input type="hidden" name="creator" placeholder="notSet">
                body += f"""
    <form style="color:white" action="{url_for('uploadPrintURL')}" method="post" enctype="multipart/form-data">
    <input type="hidden" name="printer" value="{printer.nickname}">
    <input type="hidden" name="printercode" value="{printer.code}">
    <input type="hidden" name="creator" value="{auth.current_user()}">
    <input type="hidden" name="material" placeholder="notSet">
    <label for="url">GCODE File:</label>
    <input type="file" id="url" name="gcode" accept=".gcode">
    <label for="nickname">Print Name:</label>
    <input type="text" id="nickname" name="nickname" placeholder="nickname">
    <button type="submit">Upload</button>
    </form>
    """

    #Mk4 Printers
    for printer in liminal.MK4Printers:
        if printer.prefix not in jsonValues["printersDown"]:
            try:
                printer.refreshData()
            except Exception:
                if printer in liminal.printers:
                    liminal.printers.remove(printer)
                print(f"[ERROR] Error refreshing data when displaying dashboard for {printer.nickname}")
            else:
                body += f'<h1 style="color:coral;"><a href = http://{printer.ip}>{printer.nickname}</a> </h1>'
                for camera in liminal.cameras:
                    if camera.printer != None and camera.printer.nickname == printer.nickname:
                        body += f"""<img src="{url_for("video_feed", cameraNum=camera.cameraNumber)}" alt="Video Stream">"""
                body += f'<h3 style="color:white;">Nozzle: {printer.fetchNozzleTemp()}</h3>'
                body += f'<h3 style="color:white;">Bed: {printer.fetchBedTemp()}</h3>'
                if "printing" in printer.state.lower() and printer.fetchNozzleTemp() >= 200:
                    body += f'<h3 style="color:white;">Currently in use | {printer.progress}% Complete</h3>'
                else:
                    body += f"""
                    <form style="color:white" action="{url_for('uploadPrintURL')}" method="post" enctype="multipart/form-data">
                    <input type="hidden" name="printer" value="{printer.nickname}">
                    <input type="hidden" name="printercode" value="{printer.prefix}">
                    <input type="hidden" name="creator" value="{auth.current_user()}">
                    <input type="hidden" name="material" placeholder="notSet">
                    <label for="url">GCODE File:</label>
                    <input type="file" id="url" name="gcode" accept=".gcode,.bgcode">
                    <label for="nickname">Print Name:</label>
                    <input type="text" id="nickname" name="nickname" placeholder="nickname">
                    <button type="submit">Upload</button>
                    </form>
                    """

    body += "</body></html>"

    return body
@app.route('/heat', methods = ["GET", "POST"])
#This defines the webpage that will allow you to preheat printers
#You can pass ALL to preheat all of them, and an individual name to preheat that one
def functions():
    if request.method == "GET":
        return "You aren't supposed to be here you silly goose"
    else:
        #Implement API Key validation to ensure legitimate requests
        if request.form.get("printer") == "all":
            for printer in liminal.printers:
                printer.preheat()
            return redirect(url_for("index"))
        else:
            print(request.form.get(""))
            for printer in liminal.printers:
                if request.form.get("printer") == printer.nickname:
                    printer.preheat()
            return redirect(url_for("index"))
@app.route('/pause', methods = ["POST"])
@auth.login_required()
def pausePrint():
    if request.form.get("printer") == "all":
        for printer in liminal.printers:
            printer.pause()
        return redirect(url_for("index"))
    else:
        for printer in liminal.printers:
            if request.form.get("printer") == printer.nickname:
                printer.pause()
                return redirect(url_for("index"))
        for printer in liminal.MK4Printers:
            if request.form.get("printer") == printer.nickname:
                printer.pause()

@app.route('/resume', methods = ["POST"])
@auth.login_required()
def resumePrint():
    if request.form.get("printer") == "all":
        for printer in liminal.printers:
            printer.resume()
        return redirect(url_for("index"))
    else:
        for printer in liminal.printers:
            if request.form.get("printer") == printer.nickname:
                printer.resume()
                return redirect(url_for("index"))
        for printer in liminal.MK4Printers:
            if request.form.get("printer") == printer.nickname:
                printer.resume()
@app.route('/print', methods = ["GET", "POST"])
@auth.login_required()
#Form components nessesary:
#printer : Printer Name ex. Left Printer
#url : The GCODE URL (from firebase)
#creator: The name of the uploader
#material: The name of the filament, currently unused
#printercode: unestablished right now, but is a needed input
#nickname: The name of the print
def uploadPrintURL():

    if request.method == "GET":
        return redirect(url_for("index"))
    else:
        for printer in (liminal.printers + liminal.MK4Printers):
            if request.form.get("printer") == printer.nickname:
                print("[OPERATIONAL] Printer selected for printing")
                # Indivdual Print requirements: file (URL String), creator, material, printerCode, nickname
                try:
                    gcodeUpload = request.form.get("gcode")
                    user = request.form.get("creator")
                    material = request.form.get("material")
                    printerCode = request.form.get("printercode")
                    nickname = request.form.get("nickname")
                    print("[OPERATIONAL] Form data successfully gathered")
                except Exception as e:
                    print("[ERROR] Failed to gather form data")
                    return "Unable to get HTTP form data"


                    #printer.upload(individualPrint)
                    #print(gcodeUpload)

                file_contents = request.files["gcode"].stream.read()

                if nickname == "":
                    nickname = "Untitled"
                if printer in liminal.printers:
                    printer.printer.upload(file=(nickname + ".gcode", file_contents), location="local", print=True)
                    printer.printer.select(location=nickname + ".gcode", print=True)
                    print("[OPERATIONAL] Successfully printed onto a Mk3 printer")
                else:
                    if printer in liminal.MK4Printers:
                        if request.files["gcode"].filename.split(".")[-1] == "bgcode":
                            binaryGcode = True
                        else:
                            binaryGcode = False
                        printer.upload(file_contents, nickname, binaryGcode)
                        return redirect(url_for("mk4LoadingScreen"))
                        print("[OPERATIONAL] Successfully printed onto a Mk4 printer")
                    else:
                        print(f"[ERROR] The printer {request.form.get('printer')} is not registered")
                        return f"The printer {request.form.get('printer')} is not registered"
                    #Ensures a .00000000000000000000010661449% change of a UUID collision
                try:
                    chars = list(string.ascii_lowercase + string.ascii_uppercase + string.digits)
                    blobName = ""
                    for i in range(0,15):
                        blobName += random.choice(chars)
                    blob = bucket.blob(blobName)
                    blob.upload_from_string(file_contents)
                    blob.make_public()


                    fileURL = blob.public_url
                    individualPrint = IndividualPrint(fileURL, user, material, printerCode, nickname)

                    doc_ref = db.collection('prints').document(individualPrint.uuid)

                    doc_ref.set({
                        'gcode': individualPrint.file,
                        'creator': individualPrint.creator,
                        'material': individualPrint.material,
                        'printerCode': individualPrint.printerCode,
                        'nickname': individualPrint.nickname,
                        'uuid': individualPrint.uuid,
                        'year': individualPrint.uuid[-2::],
                        'created': firestore.SERVER_TIMESTAMP
                    })
                except Exception:
                    print("[WARNING] The print was not logged successfully to Firebase, but was uploaded to the printers")
                    return "Your print was successfully uploaded to the printer but was not saved to the cloud."

                return f"Your print was successfully uploaded and documented. The unique code for your print is: {individualPrint.uuid}"
@app.route('/db')
@auth.login_required()
def database():
    allPrints = prints_ref.get()
    body = ""
    body += """
    <form action="/map" method="post" enctype="multipart/form-data">
  <label for="id">Enter code:</label><br>
  <input type="text" id="id" name="id" value=""><br>
  <input type="submit" value="Submit">
</form> 
    
    """
    for singlePrint in allPrints:
        printData = singlePrint.to_dict()
        try:
            body += f"""
            <h1>{printData["nickname"]} by {printData["creator"]} at {printData["created"].strftime('%Y-%m-%d %H:%M:%S')}</h1>
            <a download href="{printData["gcode"]}">View GCODE</a>
            """
        except KeyError:
            body += f"""
            <h1>Document too old</h1>
            """
    return body
@app.route('/search/<id>')
@auth.login_required()
def search(id):
    print(id)
    query_ref = prints_ref.where('uuid', '==', id).get()
    body = ""
    for singlePrint in query_ref:
        printData = singlePrint.to_dict()
        print(singlePrint.to_dict())
        try:
            body += f"""
            <h1>{printData["nickname"]} by {printData["creator"]} at {printData["created"].strftime('%Y-%m-%d %H:%M:%S')}</h1>
            <a download href="{printData["gcode"]}">View GCODE</a>
            """
        except KeyError:
            body += f"""
            <h1>Document too old</h1>
            """
    return body

@app.route('/map', methods = ["POST"])
@auth.login_required()
def map():
    id = request.form.get("id")
    return redirect(f"/search/{id}")

@app.route('/dev/online',methods = ["GET", "POST"])
@auth.login_required()
def setPrinterOnline():
    if request.method == "GET":
        return redirect(url_for("setPrinterStatus"))
    else:
        with open(f"{cwd}/ref/values.json", "r") as f:
            setOnline = request.form.get("printer")
            jsonValues = json.load(f)
            jsonValues["printersDown"].remove(setOnline)
        with open(f"{cwd}/ref/values.json", "w") as f:
            json.dump(jsonValues,f,indent=4)
        return redirect(url_for("setPrinterStatus"))

@app.route('/dev/ip',methods = ["GET", "POST"])
@auth.login_required()
def changeIPAddr():
    if request.method == "GET":
        return redirect(url_for("setPrinterStatus"))
    else:
        with open(f"{cwd}/ref/config.json", "r") as f:
            changedIP = request.form.get("printer")
            newAddress = request.form.get("addr")
            jsonValues = json.load(f)
            jsonValues[changedIP]["ipAddress"] = newAddress
        with open(f"{cwd}/ref/config.json", "w") as f:
            json.dump(jsonValues,f,indent=4)
        return redirect(url_for("setPrinterStatus"))
@app.route('/dev/camera',methods = ["GET", "POST"])
@auth.login_required()
def changeCamMemory():
    if request.method == "GET":
        return redirect(url_for("setPrinterStatus"))
    else:
        with open(f"{cwd}/ref/config.json", "r") as f:
            changedPrinter = request.form.get("printer")
            newIndex = request.form.get("index")
            jsonValues = json.load(f)
            for item in jsonValues:
                if item["cameraIndex"] == newIndex:
                    jsonValues[item]["cameraIndex"] = None
            jsonValues[changedPrinter]["cameraIndex"] = newIndex
            for camera in liminal.cameras:
                if camera.index == newIndex:
                    for printer in liminal.printers + liminal.MK4Printers:
                        if printer.nickname == changedPrinter:
                            camera.printer = printer
        with open(f"{cwd}/ref/config.json", "w") as f:
            json.dump(jsonValues,f,indent=4)
        return redirect(url_for("setPrinterStatus"))
@app.route('/dev/ipMK4',methods = ["GET", "POST"])
@auth.login_required()
def changeIPAddrMK4():
    if request.method == "GET":
        return redirect(url_for("setPrinterStatus"))
    else:
        with open(f"{cwd}/ref/config.json", "r") as f:
            changedIP = request.form.get("printer")
            newAddress = request.form.get("addr")
            jsonValues = json.load(f)
            jsonValues[changedIP]["Mk4IPAddress"] = newAddress
        with open(f"{cwd}/ref/config.json", "w") as f:
            json.dump(jsonValues,f,indent=4)
        return redirect(url_for("setPrinterStatus"))
        
@app.route('/dev/offline',methods = ["GET", "POST"])
@auth.login_required()
def setPrinterOffline():
    if request.method == "GET":
        return redirect(url_for("setPrinterStatus"))
    else:
        with open(f"{cwd}/ref/values.json", "r") as f:
            setOnline = request.form.get("printer")
            jsonValues = json.load(f)
            jsonValues["printersDown"].append(setOnline)
        with open(f"{cwd}/ref/values.json", "w") as f:
            json.dump(jsonValues, f, indent=4)
        return redirect(url_for("setPrinterStatus"))

@app.route('/emergency/stop', methods = ["POST"])
@auth.login_required()
def emergencyStopWeb():
    liminal.estop()
    return "Printers Stopping"
@app.route('/2FA')
@auth.login_required()
def TwoFA():
    liminal.genNewApprovalCode()
    expTime = (liminal.lastGenerated + datetime.timedelta(minutes = 5))
    for printer in liminal.printers:
        printer.displayMSG(f"{liminal.approvalCode} EXP: {(expTime.time())}")
    return redirect(url_for("index"))

@app.route('/clearDisplays')
@auth.login_required()
def clean():
    for printer in liminal.printers:
        printer.displayMSG(f"")
    return redirect(url_for("index"))
@app.route('/ip',methods = ["GET"])
@auth.login_required()
def ipManagement():
    file = open(f"{cwd}/ref/config.json")
    jsonValues = json.load(file)
    file.close()
    body = "<html><body style = background-color:black>"
    body += """
    <head>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter">
    </head>
    <style>
    body {
        font-family: "Inter", sans-serif;
    }
    </style>
    """
    for item in jsonValues:
        if "ipAddress" in jsonValues[item]:
            body += f'<h1 style="color:coral"> {item} </h1>'
            body += f"""
            <form style="color:white" action="{url_for('changeIPAddr')}" method="post", enctype="multipart/form-data">
            <input type="hidden" name="printer" value="{item}">
            <input type="text" name="addr" value="{jsonValues[item]["ipAddress"]}">
            <button type="submit">Update IP Address</button>
            </form>
            """
        if "Mk4IPAddress" in jsonValues[item]:
            body += f'<h1 style="color:coral"> {item} </h1>'
            body += f"""
            <form style="color:white" action="{url_for('changeIPAddrMK4')}" method="post", enctype="multipart/form-data">
            <input type="hidden" name="printer" value="{item}">
            <input type="text" name="addr" value="{jsonValues[item]["Mk4IPAddress"]}">
            <button type="submit">Update IP Address</button>
            </form>
            """
    
    body += """
    '<h1 style="color:red"> WARNING: Changing these values may result in this software not recognizing printers, only do this if you know what you're doing </h1>'
    """
    return body

@app.route('/dev',methods = ["GET"])
@auth.login_required()
def setPrinterStatus():
    file = open(f"{cwd}/ref/values.json")
    jsonValues = json.load(file)
    file.close()
    printerOptions = []
    for printer in liminal.printers + liminal.MK4Printers:
        printerOptions.append(printer.nickname)
    if request.method == "GET":
        body = "<html><body style = background-color:black>"
        body += """
                    <head>
                    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter">
                    </head>
                    <style>
                    body {
                  font-family: "Inter", sans-serif;
                    }
                    </style>
                    """
        body += '<h1 style="color:coral"> Currently Online </h1>'
        for printer in liminal.printers:
            if printer.code not in jsonValues["printersDown"]:
                body += f'<h3 style="color:white"> {printer.nickname} </h3>'
                body += f"""
                        <form style="color:white" action="{url_for('setPrinterOffline')}" method="post", enctype="multipart/form-data">
                        <input type="hidden" name="printer" value="{printer.code}">
                        <button type="submit">Switch Offline</button>
                        </form>
                        """
        body += '<h1 style="color:coral"> Currently Offline </h1>'
        for printer in liminal.printers:
            if printer.code in jsonValues["printersDown"]:
                body += f'<h3 style="color:white"> {printer.nickname} </h3>'
                body += f"""
                    <form style="color:white" action="{url_for('setPrinterOnline')}" method="post" enctype="multipart/form-data">
                    <input type="hidden" name="printer" value="{printer.code}">
                    <input type="hidden" name="printer" value="{printer.code}">
                    <button type="submit">Switch Online</button>
                    </form>
                                """

        body += '<h1 style="color:coral"> Change Printer Camera </h1>'
        for camera in liminal.cameras:
            body += f"""<img src="{url_for("video_feed", cameraNum=camera.cameraNumber)}" alt="Video Stream">"""
            body += f"""
            <form style="color:white" action="{url_for('changeCamMemory')}" method="post" enctype="multipart/form-data">
            <input type="hidden" name="index" value="{camera.index}">
            <select name="printer">"""
            for printerOption in printerOptions:
                body+= f"""
                <option value="{printerOption}"> {printerOption} </option>
                """
            body += f"""
            </select>
            <button type="submit">Switch Camera to Printer</button>
            </form>
            """
        body += f'<a href="{url_for("clean")}">Clear all displays</a>'
        return body
@app.errorhandler(500)
def fallback(error):
    body = ""
    body += f'<h1> There was an error somewhere, he is a fallback to printer URLS: <\h1>'
    for printer in liminal.printers:
        try:
            body += f'<h1 style="color:coral;"><a href = http://{printer.url}>{printer.nickname}</a> </h1>'
        except Exception:
            print(f"[ERROR] Error adding printer to fallback")
    for printer in liminal.MK4Printers:
        try:
            body += f'<h1 style="color:coral;"><a href = http://{printer.ip}>{printer.nickname}</a> </h1>'
        except Exception:
            print("[ERROR] Error adding printer to falback")
    return body
@app.route('/camera/raw/<path:cameraNum>')
@auth.login_required()
def video_feed(cameraNum):
    selectedCam = liminal.cameras[int(cameraNum)]
    return Response(selectedCam.stream(), mimetype='multipart/x-mixed-replace; boundary=frame')
@app.route('/camera/fetchlast30/<path:cameraNum>')
@auth.login_required()
def last30Sec(cameraNum):
    selectedCam = liminal.cameras[int(cameraNum)]
    resolution = cv2.imdecode(np.frombuffer(selectedCam.buffer[-1], np.uint8), cv2.IMREAD_COLOR).shape
    result = cv2.VideoWriter(f"{cwd}/Clip.mp4", cv2.VideoWriter_fourcc(*'mp4v'), selectedCam.frameRate,(resolution[1],resolution[0]))
    for frame in selectedCam.buffer:
        result.write(cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR))
    result.release()
    return send_file(f"Clip.mp4")

@app.route('/cctv')
@auth.login_required()
def cctvView():
    body = "<html><body style = background-color:black>"
    for camera in liminal.cameras:
        if camera.printer == None:
            cameraTxt = "No printer Assigned"
        else:
            cameraTxt = camera.printer.nickname
        body += f"""<img src="{url_for("video_feed", cameraNum = camera.cameraNumber)}" alt="Video Stream">
                <h1> {cameraTxt} </h1>
                <a href='{url_for("last30Sec", cameraNum = camera.cameraNumber)}' download>
                <h1> Download last 30 Seconds </h1>
                </a>
        """
    return body
@app.route('/mk4Load/<path:printerNickname>')
@auth.login_required()
def mk4LoadingScreen(printerNickname):
    for printer in liminal.MK4Printers:
        if printer.nickname == printerNickname:
            printer.refreshData()

            if printer.transfer != None:
                return f"""
                <meta http-equiv="refresh" content="1" /> 
                Mk4 Transfer status:<br>{printer.transfer}% Complete"""
            else:
                return "<h1>Transfer status Complete?<\h1>"

if __name__ == '__main__':
    threads = []
    for camera in liminal.cameras:
        #Camera buffer
        camThread = threading.Thread(target=camera.backgroundLogger)
        threads.append(camThread)
        #Timelapse logger
        camThread = threading.Thread(target=camera.timelapseLogger)
        threads.append(camThread)

    for thread in threads:
        thread.start()
    app.run("0.0.0.0", 8000, True)
