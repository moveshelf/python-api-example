import base64
import json
import logging
import re
import struct

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
    def __init__(self, api_key_file='mvshlf-api-key.json', api_url = 'https://api.moveshelf.com/graphql'):
        self._crc32c = mkPredefinedCrcFun('crc32c')
        self.api_url = api_url 
        if path.isfile(api_key_file) == False:
            raise 'No valid API key. Please check instructions on https://github.com/moveshelf/python-api-example'

        with open(api_key_file, 'r') as key_file:
            data = json.load(key_file)
            self._auth_token = BearerTokenAuth(data['secretKey'])

    def getUserProjects(self):
        data = self._dispatch_graphql(
            '''
            query {
                viewer {
                    projects {
                        name
                    }
                }
            }
            '''
        )
        return [p['name'] for p in data['viewer']['projects']]

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

    def updateClipMetadata(self, clip_id, metadata):
        logger.info('Updating metadata for clip: %s', clip_id)

        if metadata.get('startTimecode'):
            self._validateAndUpdateTimecode(metadata['startTimecode'])

        res = self._dispatch_graphql(
            '''
            mutation updateClip($input: UpdateClipInput!) {
                updateClip(clipData: $input) {
                    clip {
                        id
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

    def getProjectClips(self, project_id, limit):
        data = self._dispatch_graphql(
            '''
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
            ''',
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

    def _calculateCrc32c(self, file_path):
        with open(file_path, 'rb') as fp:
            crc = self._crc32c(fp.read())
            b64_crc = base64.b64encode(struct.pack('>I', crc))
            return b64_crc if six.PY2 else b64_crc.decode('utf8')

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
