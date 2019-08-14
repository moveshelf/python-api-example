import requests
import numpy as np
from io import BytesIO


class Dataset(object):
    def __init__(self, mvshlf_api):
        self.mvshlf_api = mvshlf_api

    def load_data(self, project_id):
        dataset = self.mvshlf_api.getProjectDatasets(project_id)
        url = dataset[0]['downloadUri']
        r = requests.get(url, stream = True)
        self.data = np.load(BytesIO(r.raw.read()))

    def get_training_set(self):
        return (self.data['train_patterns'], self.data['train_classes'])
    
    def get_test_set(self):
      return (self.data['test_patterns'], self.data['test_classes'])

    def get_labels(self):
      return self.data['class_labels']