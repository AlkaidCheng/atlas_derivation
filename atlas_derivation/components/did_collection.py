from functools import partial
from typing import Union, Optional, List, Dict

import numpy as np
import pandas as pd

from atlas_derivation.components import DID
from atlas_derivation.utils.did_utils import filter_dids_by_tags, list_dids
from atlas_derivation.utils.system_utils import bytes_to_readable
from atlas_derivation.utils.common_utils import filter_dataframe_by_column_values, make_multiline_text

class DIDCollection:
    
    DEFAULT_DISPLAY = ['name', 'type', 'nevent']
    
    DEFAULT_TABLE_STYLE = 'fancy_grid'
    DEFAULT_TABLE_ALIGN = 'left'
    
    def __init__(self, names:Union[List, str],
                 metadata:bool=True, filedata:bool=True):
        self.load(names,
                  metadata=metadata,
                  filedata=filedata)
    
    def load(self, names:Union[List, str],
             metadata:bool=True,
             filedata:bool=True):
        if isinstance(names, str):
            names = list_dids(names)
        dids = [DID(name, metadata=metadata, filedata=filedata) for name in names]
        self.dids = dids
        self.df = self.create_dataframe()
        
    def create_dataframe(self):
        return pd.DataFrame([did.attributes for did in self.dids])

    def update_dataframe(self, df):
        if len(df) == 0:
            raise RuntimeError('can not update with an empty dataframe')
        names = df['name'].values
        self.df = df
        dids = [did for did in self.dids if did.name in names]
        self.dids = dids
        
    def get_dids(self):
        return self.df['name'].values

    @staticmethod
    def _filter_by_attributes(df, **attributes):
        if len(df) == 0:
            return df
        did_type = attributes.pop('did_type', None)
        if isinstance(did_type, str):
            did_type = did_type.upper()
            if did_type == 'ALL':
                did_type = None
        attributes['type'] = did_type
        data_type = attributes.get('data_type', None)
        if isinstance(data_type, str):
            if data_type.upper() == 'ALL':
                data_type = None
            if data_type == 'DAOD':
                data_type = 'DAOD_\w+'
        attributes['data_type'] = data_type
        df = filter_dataframe_by_column_values(df, attributes)
        return df
    
    def filter_by_attributes(self, scope:Optional[str]=None, run_number:Optional[str]=None,
                             stream_name:Optional[str]=None, prod_step:Optional[str]=None,
                             data_type:Optional[str]=None, version:Optional[str]=None,
                             did_type:Optional[str]=None, inplace:bool=True, **kwargs):
        attributes = {
            'scope'      : scope,
            'run_number' : run_number,
            'stream_name': stream_name,
            'prod_step'  : prod_step,
            'data_type'  : data_type,
            'version'    : version,
            **kwargs
        }
        df = self._filter_by_attributes(self.df, **attributes)
        if inplace:
            self.update_dataframe(df)
        else:
            return df
    
    @staticmethod
    def _filter_by_tags(df, **kwargs):
        if len(df) == 0:
            return df
        names = df['name'].values
        valid_names = filter_dids_by_tags(names, **kwargs)
        df = df[df['name'].isin(valid_names)]
        df = df.reset_index(drop=True)
        return df
        
    def filter_by_tags(self,
                       single_etag:bool=False,
                       single_stag:bool=False,
                       single_rtag:bool=False,
                       single_ptag:bool=False,
                       latest_ptag:bool=False,
                       esrp_tags_only:bool=False,
                       inplace:bool=True):
        df = self._filter_by_tags(self.did_df,
                                  single_etag=single_etag,
                                  single_stag=single_stag,
                                  single_rtag=single_rtag,
                                  single_ptag=single_ptag,
                                  latest_ptag=latest_ptag,
                                  esrp_tags_only=esrp_tags_only)
        if inplace:
            self.update_dataframe(df)
        else:
            return df
        
    def filter_daods(self,
                     single_etag:bool=True,
                     single_stag:bool=True,
                     single_rtag:bool=True,
                     single_ptag:bool=True,
                     latest_ptag:bool=False,
                     esrp_tags_only:bool=True,
                     did_type:str='container',
                     not_empty:bool=False,
                     inplace:bool=True):
        return self.filter_derived_samples(single_etag=single_etag,
                                           single_stag=single_stag,
                                           single_rtag=single_rtag,
                                           single_ptag=single_ptag,
                                           latest_ptag=latest_ptag,
                                           esrp_tags_only=esrp_tags_only,
                                           did_type=did_type,
                                           not_empty=not_empty,
                                           inplace=inplace,
                                           data_type=r'DAOD')
    
    def filter_ntup_pileups(self,
                            single_etag:bool=True,
                            single_stag:bool=True,
                            single_rtag:bool=True,
                            single_ptag:bool=True,
                            latest_ptag:bool=False,
                            esrp_tags_only:bool=True,
                            did_type:str='container',
                            not_empty:bool=False,
                            inplace:bool=True):
        return self.filter_derived_samples(single_etag=single_etag,
                                           single_stag=single_stag,
                                           single_rtag=single_rtag,
                                           single_ptag=single_ptag,
                                           latest_ptag=latest_ptag,
                                           esrp_tags_only=esrp_tags_only,
                                           did_type=did_type,
                                           not_empty=not_empty,
                                           inplace=inplace,
                                           data_type='NTUP_PILEUP')
            
    def filter_derived_samples(self,
                               single_etag:bool=True,
                               single_stag:bool=True,
                               single_rtag:bool=True,
                               single_ptag:bool=True,
                               latest_ptag:bool=False,
                               esrp_tags_only:bool=True,
                               did_type:Optional[str]='container',
                               data_type:Optional[str]=None,
                               not_empty:bool=False,
                               inplace:bool=True):
        if len(self.df) == 0:
            return self.df
        df = self._filter_by_attributes(self.df,
                                        did_type=did_type,
                                        data_type=data_type)
        if not_empty:
            df = df[df['nevent'] > 0]
        df = self._filter_by_tags(df,
                                  single_etag=single_etag,
                                  single_stag=single_stag,
                                  single_rtag=single_rtag,
                                  single_ptag=single_ptag,
                                  esrp_tags_only=esrp_tags_only,
                                  latest_ptag=latest_ptag)
        df = df.reset_index(drop=True)
        if inplace:
            self.update_dataframe(df)
        else:
            return df
        
    def print_table(self, attributes:Optional[List[str]]=None,
                    tableformat:Optional[str]=None,
                    stralign:Optional[str]=None):
        if attributes is None:
            attributes = list(self.DEFAULT_DISPLAY)
        if tableformat is None:
            tableformat = self.DEFAULT_TABLE_STYLE
        if stralign is None:
            stralign = self.DEFAULT_TABLE_ALIGN
        columns = [attribute for attribute in attributes if attribute in self.df.columns]
        df_display = self.df[columns].copy()
        if 'name' in df_display.columns:
            func = partial(make_multiline_text, max_line_length=70)
            df_display['name'] = df_display['name'].apply(func)
        from tabulate import tabulate
        table = tabulate(df_display, showindex=False,
                         headers=df_display.columns, 
                         tablefmt=tableformat,
                         stralign=stralign)
        print(table)