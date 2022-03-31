import base64
import json
import logging
import re
import struct
import crcmod

from os import path
try:
    import enum
except ImportError:
    print('Please install enum34 package')
    raise

import requests
import six
from crcmod.predefined import mkPredefinedCrcFun
from mypy_extensions import TypedDict

logger = logging.getLogger('moveshelf-api')

class TimecodeFramerate(enum.Enum):
    FPS_24 = '24'
    FPS_25 = '25'
    FPS_29_97 = '29.97'
    FPS_30 = '30'
    FPS_50 = '50'
    FPS_59_94 = '59.94'
    FPS_60 = '60'
    FPS_1000 = '1000'


Timecode = TypedDict('Timecode', {
    'timecode': str,
    'framerate': TimecodeFramerate
    })


Metadata = TypedDict('Metadata', {
    'title': str,
    'description': str,
    'previewImageUri': str,
    'allowDownload': bool,
    'allowUnlistedAccess': bool,
    'startTimecode': Timecode
    },
    total=False)


class MoveshelfApi(object):
    def __init__(self, api_key_file, api_url = 'https://api.moveshelf.com/graphql'):
    #def __init__(self, api_key_file='mvshlf-api-key.json', api_url = 'https://api.moveshelf.com/graphql'):
        self._crc32c = mkPredefinedCrcFun('crc32c')
        self.api_url = api_url 

        if path.isfile(api_key_file) == False:
            raise ValueError("No valid API key. Please check instructions on https://github.com/moveshelf/python-api-example")

        with open(api_key_file, 'r') as key_file:
            data = json.load(key_file)
            self._auth_token = BearerTokenAuth(data['secretKey'])

    def getProjectDatasets(self, project_id):
        data = self._dispatch_graphql(
            '''
            query getProjectDatasets($projectId: ID!) {
            node(id: $projectId) {
                ... on Project {
                id,
                name,
                datasets {
                    name,
                    downloadUri
                }
                }
            }
            }
            ''',
            projectId = project_id
        )

        return [ d for d in data['node']['datasets']]

    def getUserProjects(self):
        data = self._dispatch_graphql(
            '''
            query {
                viewer {
                    projects {
                        id
                        name
                        id
                    }
                }
            }
            ''',
        )
        return [{k:v for k,v in p.items() if k in ['name','id']} for p in data['viewer']['projects']]

    def createClip(self, project, metadata=Metadata() ):
        creation_response = self._createClip(project, {
            'clientId': 'manual',
            'metadata': metadata
        })
        logging.info('Created clip ID: %s', creation_response['mocapClip']['id'])

        return creation_response['mocapClip']['id']


    def uploadFile(self, file_path, project, metadata=Metadata()):
        logger.info('Uploading %s', file_path)

        metadata['title'] = metadata.get('title', path.basename(file_path))
        metadata['allowDownload'] = metadata.get('allowDownload', False)
        metadata['allowUnlistedAccess'] = metadata.get('allowUnlistedAccess', False)

        if metadata.get('startTimecode'):
            self._validateAndUpdateTimecode(metadata['startTimecode'])

        creation_response = self._createClip(project, {
            'clientId': file_path,
            'crc32c': self._calculateCrc32c(file_path),
            'filename': path.basename(file_path),
            'metadata': metadata
        })
        logging.info('Created clip ID: %s', creation_response['mocapClip']['id'])

        with open(file_path, 'rb') as fp:
            requests.put(creation_response['uploadUrl'], data=fp)

        return creation_response['mocapClip']['id']

    def uploadAdditionalData(self, file_path, clipId, dataType, filename):
        logger.info('Uploading %s', file_path)

        creation_response = self._createAdditionalData(clipId, {
            'clientId': file_path,
            'crc32c': self._calculateCrc32c(file_path),
            'filename': filename,
            'dataType': dataType
        })
        logging.info('Created clip ID: %s', creation_response['data']['id'])

        with open(file_path, 'rb') as fp:
            requests.put(creation_response['uploadUrl'], data=fp)

        return creation_response['data']['id']

    def updateClipMetadata(self, clip_id, metadata):
        logger.info('Updating metadata for clip: %s', clip_id)

        if metadata.get('startTimecode'):
            self._validateAndUpdateTimecode(metadata['startTimecode'])

        res = self._dispatch_graphql(
            '''
            mutation updateClip($input: UpdateClipInput!) {
                updateClip(clipData: $input) {
                    clip {
                        id,
                        title
                    }
                }
            }
            ''',
            input = {
                'id': clip_id,
                'metadata': metadata
            }
        )
        logging.info('Updated clip ID: %s', res['updateClip']['clip']['id'])

    def createSubject(self, project_id, name):
        data = self._dispatch_graphql(
            '''
                mutation createPatientMutation($projectId: String!, $name: String!) {
                    createPatient(projectId: $projectId, name: $name) {
                        patient {
                            id
                            name
                        }
                    }
                }
            ''',
            projectId = project_id,
            name = name
        )

        return data['createPatient']['patient']

    def updateSubjectMetadataInfo(self, subject_id, info_to_save):
        data = self._dispatch_graphql(
            '''
                mutation updatePatientMutation($patientId: ID!, $metadata: JSONString) {
                    updatePatient(patientId: $patientId, metadata: $metadata) {
                        updated
                    }
                }
            ''',
            patientId = subject_id,
            metadata = info_to_save
        )

        return data['updatePatient']['updated']

    def getsubjectContext(self, subject_id):
        data = self._dispatch_graphql(
            '''
                query getPatientContext($patientId: ID!) {
                    node(id: $patientId) {
                        ... on Patient {
                            id,
                            name,
                            metadata,
                            project {
                                id
                                description
                                canEdit
                                unlistedAccess
                            }
                        }
                    }
                }
            ''',
            patientId = subject_id
        )

        return data['node']

    def createSession(self, project_id, session_path, subject_id):
        data = self._dispatch_graphql(
            '''
                mutation createSessionMutation($projectId: String!, $projectPath: String!, $patientId: ID!) {
                    createSession(projectId: $projectId, projectPath: $projectPath, patientId: $patientId) {
                        session {
                            id
                            projectPath
                        }
                    }
                }
            ''',
            projectId = project_id,
            projectPath = session_path,
            patientId = subject_id
        )

        return data['createSession']['session']

    def getProjectClips(self, project_id, limit, include_download_link = False):
        query = '''
            query getAdditionalDataInfo($projectId: ID!, $limit: Int) {
            node(id: $projectId) {
                ... on Project {
                id,
                name,
                clips(first: $limit) {
                edges {
                    node {
                        id,
                        title,
                        projectPath
                    }
                    }
                }
                }
            }
            }
            '''
        if include_download_link:
            query = '''
                query getAdditionalDataInfo($projectId: ID!, $limit: Int) {
                node(id: $projectId) {
                    ... on Project {
                    id,
                    name,
                    clips(first: $limit) {
                    edges {
                        node {
                            id,
                            title,
                            projectPath
                            originalFileName
                            originalDataDownloadUri
                        }
                        }
                    }
                    }
                }
                }
                '''

        data = self._dispatch_graphql(
            query,
            projectId = project_id,
            limit = limit
        )

        return [c['node'] for c in data['node']['clips']['edges']]

    def getAdditionalData(self, clip_id):
        data = self._dispatch_graphql(
            '''
            query getAdditionalDataInfo($clipId: ID!) {
            node(id: $clipId) {
                ... on MocapClip {
                id,
                additionalData {
                    id
                    dataType
                    originalFileName
                    previewDataUri
                    originalDataDownloadUri
                }
                }
            }
            }
            ''',
            clipId = clip_id
        )
        return data['node']['additionalData']

    def getProjectAndClips(self):
        data = self._dispatch_graphql(
            '''
            query {
                viewer {
                    projects {
                        id
                        name
                        clips(first: 20) {
                            edges {
                                node {
                                    id,
                                    title
                                    }
                                }
                            }
                    }
                }
            }
            '''
        )
        return [p for p in data['viewer']['projects']]

    def getProjectSubjects(self, project_id):
        data = self._dispatch_graphql(
            '''
            query getProjectPatients($projectId: ID!) {
                node(id: $projectId) {
                    ... on Project {
                        id,
                        name,
                        description,
                        canEdit,
                        patients {
                            id
                            name
                            metadata
                        }
                        sessions {
                            id
                            projectPath
                        }
                    }
                }
            }
            ''',
            projectId = project_id
        )
        return [{k:v for k,v in p.items() if k in ['name','id']} for p in data['node']['patients']]

    def getSubjectDetails(self, subject_id):
        data = self._dispatch_graphql(
            '''
            query getPatient($patientId: ID!) {
                node(id: $patientId) {
                    ... on Patient {
                        id,
                        name,
                        project {
                            id
                        }
                        reports {
                            id
                            title
                        }
                        sessions {
                            id
                            projectPath
                            clips {
                                id
                                title
                                created
                                projectPath
                                uploadStatus
                                hasCharts
                            }
                            norms {
                                id
                                name
                                uploadStatus
                                projectPath
                                clips {
                                    id
                                    title
                                }
                            }
                        }
                    }
                }
            }
            ''',
            patientId = subject_id
        )
        # return {k:v for k,v in data['node'].items() if k in ['name','id']}
        return data['node']

    def processGaitTool(self, clip_ids, trial_type):
        data = self._dispatch_graphql(
            '''
            mutation processGaitTool($clips: [String!], $trialType: String) {
                processGaitTool(clips: $clips, trialType: $trialType) {
                    jobId
                }
            }
            ''',
            clips = clip_ids,
            trialType = trial_type

        )
        return data['processGaitTool']['jobId']

    def getJobStatus(self, job_id):
        data = self._dispatch_graphql(
            '''
            query jobStatus($jobId: ID!) {
                node(id: $jobId) {
                    ... on Job {
                        id,
                        status,
                        result,
                        description
                    }
                }
            }
            ''',
            jobId = job_id
        )
        return data['node']

    def getSessionById(self, session_id):
        data = self._dispatch_graphql(
            '''
            query getSession($sessionId: ID!) {
                node(id: $sessionId) {
                    ... on Session {
                        id,
                        projectPath
                        project {
                            id
                            name
                            canEdit
                        }
                        clips {
                            id
                            title
                            created
                            projectPath
                            uploadStatus
                            hasCharts
                            hasVideo
                        }
                        norms {
                            id
                            name
                            uploadStatus
                            projectPath
                            clips {
                                id
                                title
                            }
                        }
                        patient {
                        id
                        name
                        }
                    }
                }
            }
            ''',
            sessionId = session_id
        )
        return data['node']


    def _validateAndUpdateTimecode(self, tc):
        assert tc.get('timecode')
        assert tc.get('framerate')
        assert isinstance(tc['framerate'], TimecodeFramerate)
        assert re.match('\d{2}:\d{2}:\d{2}[:;]\d{2,3}', tc['timecode'])
        tc['framerate'] = tc['framerate'].name

    def _createClip(self, project, clip_creation_data):
        data = self._dispatch_graphql(
            '''
            mutation createClip($input: ClipCreationInput!) {
                createClips(input: $input) {
                    response {
                        clientId,
                        uploadUrl,
                        mocapClip {
                            id
                        }
                    }
                }
            }
            ''',
            input = {
                'project': project,
                'clips': [clip_creation_data]
            }
        )
        return data['createClips']['response'][0]

    def _deleteClip(self, c_id):
        data = self._dispatch_graphql(
            '''
            mutation deleteClip($clipId: String) {
                deleteClip(clipId: $clipId) {
                    ok
                }
            }
            ''',
            clipId = c_id
        )
        return data['deleteClip']['ok']


    def _calculateCrc32c(self, file_path):
        with open(file_path, 'rb') as fp:
            crc = self._crc32c(fp.read())
            b64_crc = base64.b64encode(struct.pack('>I', crc))
            return b64_crc if six.PY2 else b64_crc.decode('utf8')

    def _createAdditionalData(self, clipId, metadata):
        data = self._dispatch_graphql(
            '''
            mutation createAdditionalData($input: CreateAdditionalDataInput) {
                createAdditionalData(input: $input) {
                uploadUrl
                data {
                    id
                    dataType
                    originalFileName
                    uploadStatus
                }
                }
            }
            ''',
            input = {
                'clipId': clipId,
                'dataType': metadata['dataType'],
                'crc32c': metadata['crc32c'],
                'filename': metadata['filename'],
                'clientId': metadata['clientId']
            })

        return data['createAdditionalData']

    def _dispatch_graphql(self, query, **kwargs):
        payload = {
            'query': query,
            'variables': kwargs
        }
        response = requests.post(self.api_url, json=payload, auth=self._auth_token)
        response.raise_for_status()

        json_data = response.json()
        if 'errors' in json_data:
            raise GraphQlException(json_data['errors'])

        return json_data['data']


class BearerTokenAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self._auth = 'Bearer {}'.format(token)

    def __call__(self, request):
        request.headers['Authorization'] = self._auth
        return request


class GraphQlException(Exception):
    def __init__(self, error_info):
        self.error_info = error_info
