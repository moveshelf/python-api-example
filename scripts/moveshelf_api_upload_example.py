# install required packages: pip install -r ../requirements.txt
import os, sys, json
parentFolder = os.path.dirname(os.getcwd())
sys.path.append(parentFolder)
from api import MoveshelfApi, Metadata
from util.util import *


## Specify the details of your data to be uploaded and where it should go
dataPath = r'<Path of folder where data is located>'  # e.g. r'C:\Users\testUser\Data\testTrial1'
filesToUpload = ['<list of files to upload>']  # list of files to be uploaded
dataType = '<data_type>'   # type of the data to be uploaded, see above for definition, e.g. 'data'

myProject = '<user>/<projectName>' # e.g. support/demoProject
mySubject = '<name>' # subject name, e.g. Subject1
mySession = '<session_name(typical date)>' # session name, e.g. 2021-01-01
myCondition = '<condition_name'   # condition name, e.g. 2-min walk
myTrial = '<trial_name>'   # trial name, e.g. Trial-1

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
projectNames = [p['name'] for p in projects]
iMyProject = projectNames.index(myProject)
myProjectId = projects[iMyProject]['id']
print('Project ID is: ' + myProjectId)

## Find the subject
subjects = api.getProjectSubjects(myProjectId)
subjectNames = [s['name'] for s in subjects]

if mySubject not in subjectNames:
    # create Subject
    subject = api.createSubject(myProject, mySubject)
    mySubjectId = subject['id']
else:
    # get subject data
    iMySubject = subjectNames.index(mySubject)
    mySubjectId = subjects[iMySubject]['id']

# Extract subject details
subjectDetails = api.getSubjectDetails(mySubjectId)
subjectName = subjectDetails['name']

print('Subject found, name is: ' + subjectName + ', subject ID is: ' + mySubjectId)

## Get session or create new
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

if not sessionExists:
    sessionPath = '/' + subjectName + '/' + mySession + '/'
    session = api.createSession(myProject, sessionPath, mySubjectId)
    sessionId = session['id']

session = api.getSessionById(sessionId)

sessionName = session['projectPath'].split('/')[2]
print('Session found, name is: ' + sessionName + ', session ID is: ' + sessionId)

## Get condition name or add new
conditions = []
conditions = getConditionsFromSession(session, conditions);

condition = {}
for c in conditions:
    if (c['path'] == myCondition):
        condition = c
        break

if (not condition):
    condition['path'] = myCondition
    condition['clips'] = []

## Get clip id

clipId = addOrGetTrial(api, session, condition, myTrial)
print('Clip id is: ' + clipId)


## Check for existing data
existingAdditionalData = api.getAdditionalData(clipId)
existingFileNames = [data['originalFileName'] for data in existingAdditionalData if len(existingAdditionalData) > 0]

print('Existing data for clip: ')
print(*existingFileNames, sep = "\n")

## Upload data
for fileName in filesToUpload:
    filePath = dataPath + '\\' + fileName

    if fileName in existingFileNames:
        print(fileName + ' was found in clip, will skip this data.')
        continue

    print('Uploading data for : ' + myCondition + ', ' + myTrial + ': ' + fileName)

    dataId = api.uploadAdditionalData(filePath, clipId, dataType, fileName)
