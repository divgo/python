#from boto3.s3.transfer import S3Transfer
import boto3
import imagehash
import os, sys
import pyinotify
from PIL import Image
import time
#from images2gif import writeGif
import imageio

if not "known_hash" in os.environ:
    os.environ["known_hash"] = "0" # Default this value

client = boto3.client("s3")
sourceDirectory = "/home/pi/Desktop/drop"
#transfer = S3Transfer(client)
class MotionFrame():
    def __init__(self, frameName, frameData):
        self.frameName = frameName
        self.frameData = frameData

class EventHandler(pyinotify.ProcessEvent):
    def __init__(self):
        print("EventHandler Started")
        
        self.fileCount = 0
        self.filePath = None
        self.sourceImage = None
        self.isTraining = True
        self.hasMotion = False # Do our hashes match or is there motion
        self.motionFrames = []
        self.motionStart = None

    def hammingDistance(self, hash1, hash2):
        if len(hash1) == len(hash2):
            assert len(hash1) == len(hash2)
            return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))    
        else:
            return len(hash1) - len(hash2)
        
    def processFile(self, filePath):
        #fileName = filePath.split("/")
        fileHash = 0
        fileName = filePath[filePath.rfind("/")+1:]
        print(fileName)
        try:
            image = Image.open(filePath)
            fileHash = str(imagehash.dhash(image))
        except:
            print("Exception opening file:" + sys.exc_info()[0])
            return None
        
        self.fileCount += 1 # Increment File Count
        
        known_hash = os.environ["known_hash"]
        hamming = self.hammingDistance(known_hash, fileHash)
        print("File Hash: [{}] - known_hash: [{}] - hamming: [{}]".format(fileHash, known_hash, str(hamming)))
        print("processed file [{}]: {}".format(str(self.fileCount), fileName))
        
        if self.isTraining == True:
            print("IsTraining On")
            if self.fileCount <= 10:
                if fileHash == known_hash or ( hamming>=0 and hamming <= 2):
                    if self.fileCount == 10:
                        self.isTraining = False
                    print("removing duplicate frame")
                    os.remove(filePath)
                else:
                    if known_hash == "0":
                        os.environ["known_hash"] = fileHash
                    print("motion detected in training frame")
                    self.fileCount = 0
                    os.remove(filePath)
        else:
            print("IsTraining Off")
            if fileHash == known_hash or hamming < 2:
                if self.hasMotion == True:
                    self.hasMotion=False
                    for frame in self.motionFrames:
                        print("Frame: " + frame.frameName)
                    self.framesToGIF(self.motionFrames, self.motionStart) # Write an Animated GIF
                    self.motionFrames = []
                os.remove(filePath)
            else:
                self.hasMotion=True
                self.motionStart = time.strftime("%Y%m%d-%H%M")
                #frame = MotionFrame(fileName, image)
                frame = MotionFrame(fileName, imageio.imread(filePath))
                self.motionFrames.append(frame)
                self.uploadToAWS(filePath, fileName)        
        
        return fileHash, fileName
    
    def framesToGIF(self, frames, fileName):
        FRAMEDATA = []
        for frame in frames:
            #FRAMES.append(imageio.imread(frame.frameData.tobytes(), "JPG"))
            FRAMEDATA.append(frame.frameData)
            # print(frame.frameData.tobytes())
        try:
            #writeGif(fileName, FRAMES, duration=0.5, dither=0)
            imageio.mimsave(self.motionStart + ".gif", FRAMEDATA)
        except:
            print("Exception creating animated gif")
# 031473
    def uploadToAWS(self, filePath, fileName):
        print("Uploading [" + filePath + "] to AWS")
        with open(filePath, 'rb') as data:
            client.upload_fileobj(data, "divgo-private", "SecurityCamera/" + self.motionStart + "/" + fileName)
            
        os.remove(filePath)
        
    def process_IN_CLOSE_WRITE(self, event):
        print("InCloseWrite Called on file: " + event.pathname)
        filePath = str(event.pathname)
        self.processFile(event.pathname)
        
    def process_IN_CREATE(self, event):
        print("Creating: " + event.pathname)
        filePath = str(event.pathname)
        #fileName = filePath[filePath.rfind("/")+1:]
        #print(fileName)
        #self.fileCount += 1 # Increment File Count
        #time.sleep(0.2)     # Sleep to allow time to write image
        #fileHash, fileName = self.processFile(event.pathname)
        #image = Image.open(event.pathname)
        #fileHash = str(imagehash.dhash(image))


#        if self.fileCount == 1:
#            print("setting initial file hash: " + fileHash)
#            os.environ["known_hash"] = fileHash
#            self.sourceImage = image
#            os.remove(filePath)
#        elif self.fileCount < 10:
#            if fileHash == known_hash:
#                print("incrementing initial file hash")
#                #self.fileCount += 1
#            elif hamming <= 2:
#                print("incrementing initial file hash")
#                #self.fileCount += 1                
#            else:
#                print("to much movement to derive standard hash")
#            os.remove(filePath)
#        else:
#            if fileHash == known_hash or hamming <=2:
#                os.remove(filePath)
#            else:
#                self.uploadToAWS(filePath, fileName)
        
        print("-" * 50)

# Initialize the Watcher on the Directory
wm = pyinotify.WatchManager()
handler = EventHandler()
notifier = pyinotify.Notifier(wm, handler)
wm.add_watch(sourceDirectory, pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE, rec=True)
notifier.loop()

#known_hash = os.environ["known_hash"]