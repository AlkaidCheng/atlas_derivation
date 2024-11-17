import os
import re
from time import sleep
from typing import Optional, Callable, List, Union, Dict

import numpy as np

from rucio.common.utils import extract_scope
from rucio.common.exception import RucioException

from atlas_derivation import clients
from atlas_derivation.utils.common_utils import filter_dataframe_by_column_values, get_colored_text

did_examples = {
    'DAOD': [
        'mc16_13TeV.700370.Sh_sig_1xSM_JO.merge.EVNT.e8324_e7400',
        'data16_13TeV.00303059.physics_Main.deriv.DAOD_HIGG1D1.r9264_p3083_p4205_tid21856266_00',
        'mc16_13TeV.364351.Sherpa_224_NNPDF30NNLO_Diphoton_myy_50_90.deriv.DAOD_HIGG1D1.e6452_e5984_a875_r10201_r10210_p5313'
    ],
    'AOD': [
        'mc16_13TeV.504554.aMCPy8EG_tty_yprod.merge.AOD.e8261_e7400_s3126_r10724_r10726'
    ]
}


did_regex = re.compile(r"(?P<scope>[\w_]+).(?P<run_number>[\w]+).(?P<stream_name>[\w]+)."
                       r"(?P<prod_step>[\w]+).(?P<data_type>[\w]+).(?P<version>[\w]+)")

def _call_did_method(method:str, name:str, cast:Optional[Callable]=None, **parameters):
    scope, did = get_did_scope(name)
    client = clients['did']
    method = getattr(client, method)
    if not method:
        client_name = client.__class__.split()[-1]
        raise ValueError(f'{client_name} does not contain the method "{method}"')
    result = method(scope, name, **parameters)
    if cast is not None:
        result = cast(result)
    return result

def is_valid_did_name(name:str):
    match = did_regex.match(name)
    if not match:
        return False
    return True

def get_account_name():
    return clients['did'].account

def list_scopes(account:Optional[str]=None):
    client = clients['scope']
    if account is None:
        return client.list_scopes()
    return client.list_scopes_for_account(account)

def list_my_scopes():
    account = get_account_name()
    return list_scopes(account)

def get_did_scope(name:str):
    try:
        scope, name = extract_scope(name)
        return scope, name
    except TypeError:
        scopes = list_scopes()
        scope, name = extract_scope(name, scopes)
        return scope, name
    return None, did

def list_did_content(name:str):
    return _call_did_method('list_content', name, cast=list)

def list_did_content_history(name:str):
    return _call_did_method('list_content_history', name, cast=list)

def get_did_metadata(name:str, detailed:bool=False):
    if detailed:
        return _call_did_method('get_metadata', name)
    return _call_did_method('get_did', name)

def list_did_files(name:str, long:Optional[bool]=None, name_only:bool=False):
    files = _call_did_method('list_files', name, long=long, cast=list)
    if name_only:
        return [f['name'] for f in files]
    return files

def list_dids(expr:str, did_type:Optional[str]='all', long:bool=False):
    if did_type is None:
        did_type = 'all'
    did_type = did_type.lower()
    scope, expr = get_did_scope(expr)
    client = clients['did']
    did_list = list(client.list_dids(scope, {"name": expr},
                                     did_type=did_type, long=long))
    return did_list

def _format_did_expr(scope:Optional[str]=None, run_number:Optional[str]=None,
                     stream_name:Optional[str]=None, prod_step:Optional[str]=None,
                     data_type:Optional[str]=None, version:Optional[str]=None):
    maps = {
        'scope'      : "*" if scope is None else scope,
        'run_number' : "*" if run_number is None else run_number,
        'stream_name': "*" if stream_name is None else stream_name,
        'prod_step'  : "*" if prod_step is None else prod_step,
        'data_type'  : "*" if data_type is None else data_type,
        'version'    : "*" if version is None else version,
    }

    did_expr = "{scope}.{run_number}.{stream_name}.{prod_step}.{data_type}.{version}".format(**maps)

    return did_expr

def list_dids_by_attributes(scope:str, run_number:Optional[str]=None,
                            stream_name:Optional[str]=None, prod_step:Optional[str]=None,
                            data_type:Optional[str]=None, version:Optional[str]=None,
                            did_type:Optional[str]='all', long:bool=False):
    did_expr = _format_did_expr(scope=scope, run_number=run_number,
                                stream_name=stream_name, prod_step=prod_step,
                                data_type=data_type, version=version)
    return list_dids(did_expr, did_type=did_type, long=long)

def get_did_attributes(name:str, detailed:bool=True, sort_tags:bool=True):
    name = name.split(":")[-1]
    match = did_regex.match(name)
    if not match:
        raise ValueError("invalid did name")
    attributes = match.groupdict()
    if not detailed:
        return attributes
    tokens = attributes['version'].split('tid')
    if len(tokens) == 2:
        tid = tokens[-1]
    elif len(tokens) > 2:
        raise RuntimeError("unknown did format")
    else:
        tid = None
    tokens = tokens[0].strip("_")
    tags = {}
    for tag in tokens.split('_'):
        tag_type = tag[0]
        if not tag[1:].isdigit():
            continue
        tag_label = '{}tag'.format(tag_type)
        if tag_label not in tags:
            tags[tag_label] = []
        tags[tag_label].append(tag[1:])
    for tag_label, value in tags.items():
        if len(value) == 1:
            tags[tag_label] = value[0]
    for key, value in tags.items():
        if isinstance(value, list) and sort_tags:
            tags[key] = sorted(value, key = lambda item: -int(item))
    attributes.update(tags)
    if tid is not None:
        attributes['tid'] = tid
    return attributes

def get_did_without_tid(name:str):
    return name.split("_tid")[0]

def get_did_all_versions(name:str):
    attributes = get_did_attributes(name, detailed=False)
    attributes['version'] = "*"
    return list_dids_by_attributes(**attributes)

def get_did_largest_tag_value(name:str, tag_label:str='p'):
    attributes = get_did_attributes(name)
    tag_name = f'{tag_label}tag'
    if tag_name not in attributes:
        return None
    tag_values = attributes[tag_name]
    if isinstance(tag_values, list):
        return max([int(val) for val in tag_values])
    return int(tag_values)

def get_did_tag_variants(name:str, sort:bool=True, tag_label:str='p'):
    attributes = get_did_attributes(name, detailed=True, sort_tags=False)
    tag_name = f'{tag_label}tag'
    if tag_name not in attributes:
        raise RuntimeError(f"no {tag_name} found for the did {name}")
    tid = attributes.get('tid', None)
    tags = attributes[tag_name]
    if not isinstance(tags, list):
        tags = [tags]
    attributes = get_did_attributes(name, detailed=False)
    tag_str = '_'.join([f'{tag_label}{tag}' for tag in tags])
    attributes['version'] = attributes['version'].replace(tag_str, "*")
    if tid is not None:
        attributes['version'] = attributes['version'].replace(tid, "*")
    dids = list_dids_by_attributes(**attributes)
    if tid is None:
        dids = [did for did in dids if '_tid' not in did]
    else:
        dids = [did for did in dids if '_tid' in did]
    if sort:
        dids = sorted(dids, key=lambda did: get_did_largest_tag_value(did, tag_label))[::-1]
    return dids

def get_dids_tag_variants(names:List[str], sort:bool=True,
                          tag_label:str='p', sleep_time:float=0.5):
    dids = {}
    n = len(names)
    for i, name in enumerate(names):
        sleep(sleep_time)
        print(f"Sample ({i + 1}/{n}): {name}")
        dids[name] = get_did_tag_variants(name, sort=sort, tag_label=tag_label)
    return dids

def get_did_container_sum_events(name:str):
    files = list_did_files(name)
    return sum([file['events'] for file in files])

def parse_did_inputs(inputs:Union[List, str]):
    if isinstance(inputs, str):
        if os.path.exists(inputs):
            with open(inputs, 'r') as f:
                lines = f.readlines()
        else:
            lines = inputs.split("\n")
        inputs = [l.strip() for l in lines if l.strip()]
    valid_inputs = []
    for input_i in inputs:
        input_i = input_i.split(':')[-1]
        if not is_valid_did_name(input_i):
            raise ValueError(f'invalid did format: "{input_i}"')
        valid_inputs.append(input_i)
    return valid_inputs

def is_did_available(name:str):
    try:
        metadata = get_did_metadata(name)
        if metadata:
            return True
    except:
        pass
    return False
            
def check_dids_available(inputs:Union[List, str], did_type="all"):
    inputs = parse_did_inputs(inputs)
    samples = {'available': [], 'missing': []}
    for name in inputs:
        if is_did_available(name):
            samples['available'].append(name)
        else:
            samples['missing'].append(name)
    return samples


def get_daods_from_aods(names:Union[List, str],
                        formats:Optional[Union[List[str], str]]=None,
                        did_type:str='container'):
    daod_samples = {}
    if isinstance(formats, str):
        formats = [formats]
    if formats is None:
        formats = ['*']
    formats = [f'DAOD_{fmt}' for fmt in formats]
    if isinstance(names, str):
        names = [names]
    for name in names:
        daod_samples[name] = []
        attributes = get_did_attributes(name, detailed=False)
        if attributes['data_type'] != 'AOD':
            raise ValueError(f'not an AOD sample: "{name}"')
        attributes['prod_step'] = 'deriv'
        attributes['version'] = attributes['version'] + "_*"
        for fmt in formats:
            attributes['data_type'] = fmt
            samples = list_dids_by_attributes(**attributes, did_type=did_type)
            daod_samples[name].extend(samples)
    return daod_samples

def dids_to_dataframe(dids:List[Union[Dict,str]], detailed:bool=False):
    data = []
    for did in dids:
        attributes = {}
        if isinstance(did, dict):
            attributes['did'] = did['name']
            attributes['did_type'] = did['did_type'].replace("DIDType.", "")
            attributes.update(get_did_attributes(did['name'], detailed=detailed))
            attributes['scope'] = did['scope']
        else:
            attributes['did'] = did
            attributes.update(get_did_attributes(did, detailed=detailed))
        data.append(attributes)
    import pandas as pd
    return pd.DataFrame(data)


def filter_dids_by_tags(names:List[str],
                        single_etag:bool=False,
                        single_stag:bool=False,
                        single_rtag:bool=False,
                        single_ptag:bool=False,
                        latest_ptag:bool=False,
                        esrp_tags_only:bool=False):
    did_data = []
    for name in names:
        attributes = {'name': name}
        attributes.update(get_did_attributes(name))
        did_data.append(attributes)
    import pandas as pd
    df = pd.DataFrame(did_data)
    single_tag_check = lambda x: not isinstance(x, list) and (x is not None)
    attributes = {}
    if single_rtag:
        attributes['rtag'] = single_tag_check
    if single_ptag:
        attributes['ptag'] = single_tag_check
    if single_etag:
        attributes['etag'] = single_tag_check
    if single_stag:
        attributes['stag'] = single_tag_check        
    df = filter_dataframe_by_column_values(df, attributes)
    if esrp_tags_only:
        esrp_tags_set = set(['etag', 'stag', 'rtag', 'ptag'])
        lambda_func = lambda x: set(x[x.keys().str.endswith('tag') & ~x.isna()].keys()) == esrp_tags_set
        df = df[df.apply(lambda_func, axis=1)]
    if latest_ptag:
        df_tmp = df.copy()
        for column in ['etag', 'stag', 'rtag', 'ptag']:
            if column not in df_tmp.columns:
                df_tmp[column] = None
        # remove dids without ptag
        df_tmp = df_tmp[~df_tmp['ptag'].isna()]
        # account for cases with multiple e, s or r tags which are unhashable
        def get_merged_tag(x):
            if isinstance(x, list):
                return '_'.join(x)
            return x
        df_tmp['merged_etag'] = df_tmp['etag'].apply(get_merged_tag)
        df_tmp['merged_stag'] = df_tmp['stag'].apply(get_merged_tag)
        df_tmp['merged_rtag'] = df_tmp['rtag'].apply(get_merged_tag)
        # make sure the ptag is treated as integer when finding the max value
        def get_primary_ptag(x):
            if isinstance(x, str):
                return int(x)
            elif isinstance(x, list):
                return np.array(x, dtype=int).max()
            elif x is None:
                return 0
            else:
                return x
        df_tmp['primary_ptag'] = df_tmp['ptag'].apply(get_primary_ptag)
        df_tmp = df_tmp.fillna(-999)
        dids = []
        for name, df_grouped in df_tmp.groupby(['run_number', 'data_type',
                                                'merged_etag', 'merged_stag',
                                                'merged_rtag']):
            idxmax = df_grouped['primary_ptag'].idxmax()
            did = df_grouped.loc[idxmax]['name']
            dids.append(did)
        dids = np.array(dids)
        df = df.set_index('name').loc[dids].reset_index()
    return df['name'].values

def get_AOD_properness(name:str):
    attributes = get_did_attributes(name, detailed=True)
    if attributes['data_type'] != 'AOD':
        raise ValueError(f'{name} is not an AOD sample')
    if ('etag' not in attributes) or ('rtag' not in attributes):
        raise ValueError(f'{name} does not have proper etag and rtag')
    if ('atag' not in attributes) and ('stag' not in attributes):
        raise ValueError(f'{name} does not have proper atag/stag')
    # smaller means more proper
    properness = 0
    if attributes['prod_step'] != 'recon':
        properness += 2
    if (isinstance(attributes['etag'], list)) or (isinstance(attributes['rtag'], list)):
        properness += 1
    return properness

def tag_matching(ref_name:str, names:List[str], tags:List[str], filter_atag:bool=True):
    ref_attributes = get_did_attributes(ref_name, detailed=True)
    tag_values = {}
    def make_tag_list(tags):
        if not isinstance(tags, list):
            return [tags]
        return tags
    for tag in tags:
        if tag not in ref_attributes:
            raise ValueError(f'DID "{ref_name}" does not contain the {tag} information')
        tag_values[tag] = make_tag_list(ref_attributes[tag])
    matched_names = []
    for name in names:
        attributes = get_did_attributes(name, detailed=True)
        if filter_atag:
            if ('atag' in ref_attributes) and ('atag' not in attributes):
                continue
            if ('atag' in attributes) and ('atag' not in ref_attributes):
                continue
        for tag in tags:
            if tag not in attributes:
                break
            tag_value = make_tag_list(attributes[tag])
            if not set(tag_value).intersection(set(tag_values[tag])):
                break
        else:
            matched_names.append(name)
    return matched_names
    
def get_proper_AOD(name:str):
    properness = get_AOD_properness(name)
    if properness == 0:
        return name, properness
    attributes = get_did_attributes(name, detailed=False)
    if attributes['prod_step'] != 'recon':
        attributes['prod_step'] = "*"
    attributes['version'] = "*"
    dids = list_dids_by_attributes(**attributes, did_type='container')
    dids = tag_matching(name, dids, ['rtag', 'etag'], filter_atag=True)
    dids = sorted(dids, key=get_AOD_properness)
    proper_AOD = dids[0]
    properness = get_AOD_properness(proper_AOD)
    return proper_AOD, properness
    
    
def get_proper_AODs(inputs:Union[List, str]):
    dids = parse_did_inputs(inputs)
    results = {}
    results['proper'] = {'unchanged':[], 'changed':{}}
    results['improper'] = {'unchanged':[], 'changed':{}}
    results['final'] = []
    for did in dids:
        proper_AOD, properness = get_proper_AOD(did)
        if properness == 0:
            result = results['proper']
        else:
            result = results['improper']
        results['final'].append(proper_AOD)
        if did == proper_AOD:
            result['unchanged'].append(did)
        else:
            result['changed'][did] = proper_AOD
    return results

def print_proper_AODs(inputs:Union[List, str]):
    results = get_proper_AODs(inputs)
    setups = [('proper', 'unchanged', 'Proper AODs - Unchanged', 'green', 'green'),
              ('proper', 'changed', 'Proper AODs - Changed', 'bright yellow', 'green'),
              ('improper', 'unchanged', 'Improper AODs - Unchanged', 'red', 'red'),
              ('improper', 'changed', 'Improper AODs - Changed', 'red', 'red')]
    text = ''
    for setup in setups:
        result = results[setup[0]][setup[1]]
        size = len(result)
        if not size:
            continue
        title_text = get_colored_text(f'[{setup[2]} ({size})]\n', setup[3])
        content_text = ''
        if isinstance(result, dict):
            for orig_name, new_name in result.items():
                content_text += f'  {orig_name} -> {new_name}\n'
        else:
            content_text = "".join([f'  {name}\n' for name in result])
        content_text = get_colored_text(content_text, setup[4])
        text += (title_text + content_text)
    print(text)