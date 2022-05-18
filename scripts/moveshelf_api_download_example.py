# install required packages: pip install -r ../requirements.txt
import os, sys, json
parentFolder = os.path.dirname(os.getcwd())
sys.path.append(parentFolder)
from api import MoveshelfApi, Metadata
import util
import requests

## Readme
# The datastructure of Moveshelf is organized as follows:
# * Project: Projects are the highest level and associated to a single organization in Moveshelf.
# * Subjects: Each project contains a list of subjects. At project level, access to the Electronic Health Record (EHR) of a subject can be made.
# * Sessions: A session contains the relevant information for a specific measurement session and is typically defined by the date of the measurement.
# * Conditions: Conditions specify a group of trials that were performed within a session.
# * Trials: Trials, aka clips, are containers used to store our data. It consists of metadata and 'Additional Data', where the actual data of a trial is stored.

# Projects, Subjects and sessions are defined by their ID. When uploading data, a clip id is needed, which can be generated for new trial/clip, or obtained from the existing clips. Using this id, additional data can be uploaded using the provided upload url.
#
# For the data to be uploaded, the type needs to be specified. Within Moveshelf, we support the following data types (to be specified in the upload):
# * video: .mp4, .mov, .mpg, .avi
# * motion: .bvh, .fbx, .trc, .glb, .mox, c3d, xlsx
# * doc: .pdf
# * data: .csv, .json, .txt
# * img: .png, .jpg
# * camera: .xcp
# * raw: anything not specified above

# To access the API, you need an API key (the API key can be obtained from your account settings in Moveshelf or was provided to you beforehand. Make sure your API key ('mvshlf-api-key.json') is stored in the root folder of this project
# If needed, you can point the API to a specific location (e.g. staging) in mvshlf-config.json.


## Specify the details of your data to be uploaded and where it should go
myProject = '<user>/<projectName>'                      # e.g. support/demoProject
mySubject = '<name>'                                    # subject name, e.g. Subject1
mySession = '<session_name(typical date)>'              # session name, e.g. 2021-01-01
myCondition = '<condition_name>'                        # condition name, e.g. 2-min walk
myTrial = '<trial_name>'                                # trial name, e.g. Trial-1

dataFolderSave = r'C:\temp\1'                           # data folder wh
dataTypesToDownload = ['data']              # Provide data types to download or leave empty if all is needed
fileExtensionsToDownload = ['.h5', '.txt']    # Provide file extensions to download or leave empty if all is needed
stopProcessing = False

## Setup the API
# Load config
with open(os.path.join(parentFolder,'mvshlf-config.spec.json'), 'r') as configFile:
    data = json.load(configFile)

# And overwrite if available
personalConfig = os.path.join(parentFolder,'mvshlf-config.json')
if os.path.isfile(personalConfig):
    with open(personalConfig, 'r') as configFile:
        data.update(json.load(configFile))

api = MoveshelfApi(api_key_file = os.path.join(parentFolder,data['apiKeyFileName']), api_url = data['apiUrl'])

## Get available projects
projects = api.getUserProjects()
projectNames = [project['name'] for project in projects if len(projects) > 0]
print('Available projects:')
print(*projectNames, sep='\n')

## Select the project
try:
    iMyProject = projectNames.index(myProject)
    myProjectId = projects[iMyProject]['id']
    print('Project ID is: ' + myProjectId)

except:
    print('The project you are looking for is not found, searching for: ' + myProject)
    stopProcessing = True


## Find the subject
if not stopProcessing:
    subjects = api.getProjectSubjects(myProjectId)
    subjectNames = [s['name'] for s in subjects]
    print('Available subjects:')
    print(*subjectNames, sep='\n')


    if mySubject not in subjectNames:
        print('The subject you are looking for is not found, searching for: ' + mySubject)
        stopProcessing = True
    else:
        # get subject data
        iMySubject = subjectNames.index(mySubject)
        mySubjectId = subjects[iMySubject]['id']

        # Extract subject details
        subjectDetails = api.getSubjectDetails(mySubjectId)
        subjectName = subjectDetails['name']

        print('Subject found, name is: ' + subjectName + ', subject ID is: ' + mySubjectId)

## Get session
if not stopProcessing:
    sessions = subjectDetails['sessions']
    sessionExists = False
    for session in sessions:
        try:
            sessionName = session['projectPath'].split('/')[2]
        except:
            sessionName = ""
        if sessionName == mySession:
            sessionId = session['id']
            sessionExists = True
            break

    if sessionExists:
        session = api.getSessionById(sessionId)

        sessionName = session['projectPath'].split('/')[2]
        print('Session found, name is: ' + sessionName + ', session ID is: ' + sessionId)
    else:
        print('The session you are looking for is not found, searching for: ' + mySession)
        stopProcessing = True


## Get condition
if not stopProcessing:

    conditions = []
    conditions = util.getConditionsFromSession(session, conditions);

    condition = {}
    for c in conditions:
        if (c['path'] == myCondition):
            condition = c
            break

    if (not condition):
        print('The condition you are looking for is not found, searching for: ' + myCondition)
        stopProcessing = True

    else:
        ## Get clip id
        trialCount = len(condition['clips'])
        trialNames = [clip['title'] for clip in condition['clips'] if trialCount > 0]
        if myTrial in trialNames:
            # return existing clip
            iClip = trialNames.index(myTrial)
            clipId = condition['clips'][iClip]['id']
        else:
            print('The trial you are looking for is not found, searching for: ' + myTrial)
            stopProcessing = True

if not stopProcessing:
    ## Check for existing data
    existingAdditionalData = api.getAdditionalData(clipId)
    existingFileNames = [data['originalFileName'] for data in existingAdditionalData if len(existingAdditionalData) > 0]

    print('Existing data for clip: ')
    print(*existingFileNames, sep = "\n")

    ## Download data
    for data in existingAdditionalData:
        if not (len(dataTypesToDownload) == 0 or data['dataType'] in dataTypesToDownload):
            continue

        filename, file_extension = os.path.splitext(data['originalFileName'])
        if not (len(fileExtensionsToDownload) == 0 or file_extension in fileExtensionsToDownload):
            continue

        uploadStatus = data['uploadStatus']
        if uploadStatus == 'Processing':
            print('File ' + data['originalFileName'] + ' is still being processed, skipping download')
        elif uploadStatus == 'Complete':
            file_data = requests.get(data['originalDataDownloadUri']).content
            # create the file in write binary mode, because the data we get from net is in binary
            filenameSave = os.path.join(dataFolderSave, data['originalFileName'])
            with open(filenameSave, "wb") as file:
                file.write(file_data)


            print('Downloaded ' + data['originalFileName'] + ' into ' + filenameSave)
        else:
            print('File ' + data['originalFileName'] + ' status is : ' + uploadStatus  + ', skipping download')

