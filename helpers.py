import os
import logging
import requests

logger = logging.getLogger('moveshelf-api')

class Helpers:

    @staticmethod
    def download_file(url, local_filename):
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        # f.flush()
        return local_filename

    @staticmethod
    def downloadDataToPath(data, dirpath):
        for d in data:
            url = d['originalDataDownloadUri']
            filename = d['originalFileName']
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)

            Helpers.download_file(url, dirpath + '/' + filename)