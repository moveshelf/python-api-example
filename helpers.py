import os
import logging
import requests
import json
import pandas as pd

logger = logging.getLogger('moveshelf-api')

class Helpers:

    @staticmethod
    def timeToCycle(series):
        series = (series - series.min()) / (series.max() - series.min())
        return series * 100

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
    def parseParametersFile(paramsFile):
        with open(paramsFile) as f:
          params = json.load(f)
    
        params_df = pd.DataFrame.from_dict(params['data'])
        values_df = params_df['values'].apply(pd.Series)
        params_df = pd.concat([ params_df.drop(['values'], axis=1), values_df], axis=1)
    
        return params_df

    @staticmethod
    def parseEventFile(eventsFile):
        with open(eventsFile) as f:
          events = json.load(f)
      
        return pd.DataFrame.from_dict(events['events'])

    @staticmethod
    def parseKinematicsFile(kinematicsFile):
        with open(kinematicsFile) as f: #let's open and parse kinamatic angles 
          kin = json.load(f)
      
        return pd.DataFrame.from_dict(kin['data']) #create a panda DataFrame for easy manipulation
    
    @staticmethod
    def downloadDataToPath(data, dirpath):
        for d in data:
            url = d['previewDataUri']
            filename = d['originalFileName']
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)

            Helpers.download_file(url, dirpath + '/' + filename)