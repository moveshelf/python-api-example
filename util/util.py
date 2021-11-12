from api import Metadata

def getConditionsFromSession(session, conditions = []):
    sessionPath = session['projectPath']
    clips = session['clips']
    for c in clips:
        clipPath = c['projectPath'].split(sessionPath)
        if (len(clipPath) > 0 and len(clipPath[1]) > 0):
            conditionPath = clipPath[1]
            conditionFound = False
            for condition in conditions:
                if (condition['path'] == conditionPath):
                    condition['clips'].append(c)
                    conditionFound = True
                    break

            if (not conditionFound):
                condition = dict.fromkeys(['path', 'fullPath', 'norms', 'clips'])
                condition['path'] = conditionPath
                condition['fullPath'] = sessionPath + conditionPath
                condition['norms'] = []
                condition['clips'] = [c]
                conditions.append(condition)

    norms = session['norms']
    for n in norms:
        normPath = ''
        if (n['projectPath']):
            normPath = n['projectPath'].split(sessionPath)
            if (len(normPath) > 0):
                conditionPath = normPath[1]
                conditionFound = False
                for condition in conditions:
                    if (condition['path'] == conditionPath):
                        condition['norms'].append(n)
                        conditionFound = True
                        break
                if (not conditionFound):
                    condition = dict.fromkeys(['path', 'fullPath', 'norms', 'clips'])
                    condition['path'] = conditionPath
                    # condition['fullPath'] = sessionPath + conditionPath
                    condition['norms'] = [n]
                    condition['clips'] = []
                    conditions.append(condition)

    return conditions

def addOrGetTrial(api, session, condition, trialName = None):
    trialCount = len(condition['clips'])

    if trialName == None:
        trialNumbers = [clip['title'].split('-')[1] for clip in condition['clips'] if trialCount > 0]
        trialNumber = max(trialNumbers) if len(trialNumbers) > 0 else trialCount
        trialName = "Trial-" + str(trialNumber + 1)

    trialNames = [clip['title'] for clip in condition['clips'] if trialCount > 0]
    if trialName in trialNames:
        # return existing clip
        iClip = trialNames.index(trialName)
        clipId = condition['clips'][iClip]['id']
    else:
        # generate new clip
        metadata = Metadata()
        metadata['title'] = trialName
        metadata['projectPath'] = session['projectPath'] + condition['path']
        # metadata['allowDownload'] = False
        # metadata['allowUnlistedAccess'] = False
        clipId = api.createClip(session['project']['name'], metadata)

    return clipId