import base64
import json
import logging
import struct

from os import path

import requests
from crcmod.predefined import mkPredefinedCrcFun

logger = logging.getLogger('moveshelf-api')

class Metadata(dict):
    def __init__(
                self,
                title=None,
                description=None,
                previewImageUri=None,
                allowDownload=False,
                allowUnlistedAccess=False,
                **ignored):
        super(Metadata, self).__init__(
            title=title,
            description=description,
            previewImageUri=previewImageUri,
            allowDownload=allowDownload,
            allowUnlistedAccess=allowUnlistedAccess
        )


class MoveshelfApi(object):
    def __init__(self, api_key_file='mvshlf-api-key.json'):
        self._crc32c = mkPredefinedCrcFun('crc32c')
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

        metadata['title'] = metadata['title'] or path.basename(file_path)

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
            return base64.b64encode(struct.pack('>I', crc))

    def _dispatch_graphql(self, query, **kwargs):
        api_url = 'https://api.moveshelf.com/graphql'
        payload = {
            'query': query,
            'variables': kwargs
        }
        response = requests.post(api_url, json=payload, auth=self._auth_token)
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
