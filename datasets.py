import requests
import numpy as np
from io import BytesIO


class Dataset(object):
    def __init__(self, mvshlf_api, project_id):
        self.mvshlf_api = mvshlf_api
        self.project_id = project_id

    def load_data(self):
        dataset = self.mvshlf_api.getProjectDatasets(self.project_id)
        url = dataset[0]['downloadUri']
        r = requests.get(url, stream = True)
        self.data = np.load(BytesIO(r.raw.read()))

    def get_training_set(self):
        return (self.data['train_patterns'], self.data['train_classes'])
    
    def get_test_set(self):
      return (self.data['test_patterns'], self.data['test_classes'])

    def get_labels(self):
      return self.data['class_labels']