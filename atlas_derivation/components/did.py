import numpy as np

from atlas_derivation.utils.common_utils import combine_dict
from atlas_derivation.utils.system_utils import bytes_to_readable
from atlas_derivation.utils.did_utils import (get_did_attributes,
                                              get_did_metadata,
                                              list_did_files)

class DID:
    
    METADATA_COLS = ['type']
    
    FILEDATA_COLS = ['nfiles', 'nevent', 'nbytes', 'size']
    
    @property
    def name(self) -> str:
        return self.attributes['name']
    
    def __init__(self, name:str, metadata:bool=True, filedata:bool=True):
        self.load(name,
                  metadata=metadata,
                  filedata=filedata)

    def load(self, name:str, metadata:bool=True, filedata:bool=True):
        self.attributes = {'name': name}
        self.update_name_attributes()
        if metadata:
            self.update_metadata()
        if filedata:
            self.update_filedata()
            
    def update_name_attributes(self):
        attributes = get_did_attributes(self.name)
        self.attributes = combine_dict(self.attributes, attributes)
        
    def update_metadata(self):
        metadata = get_did_metadata(self.name)
        self.attributes = combine_dict(self.attributes, metadata)
        
    def update_filedata(self):
        files = list_did_files(self.name)
        nevent = np.sum([data['events'] for data in files]).astype('int')
        nbytes = np.sum([data['bytes'] for data in files])
        size = bytes_to_readable(nbytes)
        self.attributes.update({
            'nfiles': len(files),
            'nevent': nevent,
            'nbytes': nbytes,
            'size': size
        })
        self.files = files