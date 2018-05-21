# Basic example of using Moveshelf API to upload data from Python

The [Moveshelf](https://moveshelf.com) API uses [GraphQL](http://graphql.org)
for data access. This project demonstrates basic interaction with this API to
upload data to the Moveshelf platform.

## Setup

### Dependencies
The example code is compatible with Python 2.7 and 3+ and uses the
[Requests](http://docs.python-requests.org/en/master/) and
[crcmod](http://crcmod.sourceforge.net) libraries. If necessary these libraries
can be installed with:

```sh
pip install -r requirements.txt
```


### API key
To access the Moveshelf API an access key should be created:

1. Login to [Moveshelf](https://moveshelf.com)
2. Navigate to your profile
3. In the API Keys section under your avatar enter an ID for the new key, e.g. 'api_test'
4. Click on 'Generate API Key'
5. In the resulting modal dialog click 'Download Key' to save the API key in a JSON file.
Save the key as `mvshlf-api-key.json` in the project root directory.

**The API key should be kept secret.**

## Running

The `cli.py` file provides a simple command line interface to the API.
Commands can be run as `python cli.py <cmd>`.

You can get basic help on commands by using the `--help` option, i.e. `python cli.py --help`.

### Listing available projects

Listing projects demonstrates the use of GraphQL queries to request data. The
request is implemented in file the `api.py` by the `MoveshelfApi.getUserProjects()`
method:

```py
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
```

This query uses the `viewer` field to access the authenticated user's data.

You can list your available projects by running:

```sh
python cli.py list
```

### Uploading data

To upload data to Moveshelf requires four steps:

1. Create a metadata object describing the motion data.
2. Calculate a CRC32C of the data -- used to verify that no data corruption has occurred.
3. Create a record of the data via the API. This allocates a unique identifier for the data, and generates an upload URL.
4. Upload the data. Data is encrypted and stored redundantly in multiple data centers.

The clip metadata is described by a simple dictionary with a defined set of keys.
Note that all metadata fields are optional, but in this example we have explicitly
set them. The default values provided by the API are:

| Field                 | Default    |
| -------------------   | ---------- |
| `title`               | "Untitled" |
| `description`         | `null`     |
| `previewImageUri`     | `null`     |
| `allowDownload`       | `false`    |
| `allowUnlistedAccess` | `false`    |


The motion capture clip is uploaded using the `MoveshelfApi.uploadFile()` method:

```py
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
```

The API call for creating the motion capture clip record is implemented by the
`MoveshelfApi.createClip()` method, which uses a GraphQL mutation to update the
data stored on the Moveshelf platform:

```py
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
```
Note how the `response` query includes the `clientId`, `uploadUrl` and
`mocapClip.id` fields. Only the `uploadUrl` is strictly required for the upload
process, but the other fields are also often useful. The `clientId` can be used
to correlate the created clips to the user data in the case of multiple
uploads, while the `mocapClip.id` can be used to reference data from external
systems.

To test the upload process run the file upload command:

```sh
python cli.py up <filePath> <project>
```

For example:

```sh
python cli.py up test.fbx username/private --title test
```



