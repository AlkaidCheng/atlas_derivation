from typing import Union, List, Optional
import os
import re
import json
import glob
import fnmatch

from dateutil.relativedelta import relativedelta
import datetime

import pandas as pd
import numpy as np

from atlas_derivation.utils.did_utils import *

class AODDeletionManager():
    def __init__(self):
        super().__init__()
        self.reference = {}
        self.samples = []
        self.exclusion_samples = []
        self.exclusion_samples_wildcard = []
        self.inclusion_samples = []
        self.inclusion_samples_wildcard = []
    
    def load_ref(self, filename:str, data_type:Optional[str]=None):
        if data_type not in self.reference:
            self.reference[data_type] = {}
        # remove empty lines
        lines = [i.strip() for i in open(filename).readlines() if i.strip()]
        result = {}
        annotation = None
        flag = 0
        for l in lines:
            if l.startswith("#"):
                if "----" in l:
                    flag = 1
                    continue
                elif flag == 0:
                    annotation = l.replace("#", "").strip()
                    if annotation not in result:
                        result[annotation] = []
            else:
                expr = [i.strip() for i in l.split() if i.strip()][1]
                tokens = [i.strip() for i in re.split('\*|\.', expr) if i.strip()]
                tokens = [i for i in tokens if i.isdigit()]
                if len(tokens) > 1:
                    raise RuntimeError(f"can not determine run number from {expr}")
                result[annotation].append(tokens[0])
                flag = 0
        keys = list(result)
        for key in keys:
            if not result[key]:
                result.pop(key)
            else:
                result[key] = sorted(list(set(result[key])))
        self.check_ref_duplicates(result)
        self.update_ref(result, data_type)        
        if (data_type is not None) and ('DAOD' in data_type):
            self.update_ref(result, 'AOD')
    
    def update_ref(self, result, data_type:Optional[str]=None):
        if data_type not in self.reference:
            self.reference[data_type] = {}
        for key, values in result.items():
            if key not in self.reference[data_type]:
                self.reference[data_type][key] = []
            self.reference[data_type][key] += values
            self.reference[data_type][key] = sorted(list(set(self.reference[data_type][key])))
            
    @staticmethod
    def get_dids_from_file(filename:str):
        lines = open(filename).readlines()
        dids = []
        dids_wildcard = []
        for line in lines:
            line = line.strip()
            if (not line) or ("//" in line) or ("#" in line):
                continue
            if ":" in line:
                line = line.split(":")[-1]
            if "*" in line:
                dids_wildcard.append(line)
                continue
            if not is_valid_did_name(line):
                print(f"ERROR: Invalid DID format: {line}")
            dids.append(line)
        return dids, dids_wildcard
    
    def load_sample_from_dir(self, dirname:str):
        files = glob.glob(os.path.join(dirname, "*.txt"))
        all_dids = []
        for file in files:
            dids = [i.strip() for i in open(file).readlines() if i]
            dids = [i.split()[0] for i in dids if "//" not in i and "#" not in i]
            all_dids += dids
        all_dids = sorted(list(set(all_dids)))
        self.samples = all_dids
        
    def load_exclusion_sample_from_dir(self, dirname:str):
        files = glob.glob(os.path.join(dirname, "*.txt"))
        all_dids = []
        all_dids_wildcard = []
        for file in files:
            dids, dids_wildcard = self.get_dids_from_file(file)
            all_dids += dids
            all_dids_wildcard += dids_wildcard
        all_dids = sorted(list(set(all_dids)))
        all_dids_wildcard = sorted(list(set(all_dids_wildcard)))
        self.exclusion_samples = all_dids
        self.exclusion_samples_wildcard = all_dids_wildcard
        
    def add_samples_to_keep_from_file(self, filename:str):
        dids, dids_wildcard = self.get_dids_from_file(filename)
        dids = sorted(list(set(dids)))
        dids_wildcard = sorted(list(set(dids_wildcard)))
        self.exclusion_samples.extend(dids)
        self.exclusion_samples_wildcard.extend(dids_wildcard)
        
    def add_samples_to_delete_from_file(self, filename:str):
        dids, dids_wildcard = self.get_dids_from_file(filename)
        dids = sorted(list(set(dids)))
        dids_wildcard = sorted(list(set(dids_wildcard)))
        self.inclusion_samples.extend(dids)
        self.inclusion_samples_wildcard.extend(dids_wildcard)
        
    def get_ref_run_number_map(self, result):
        reverse_map = {}
        for annotation, run_numbers in result.items():
            for run_number in run_numbers:
                if run_number not in reverse_map:
                    reverse_map[run_number] = []
                reverse_map[run_number].append(annotation)
        return reverse_map
    
    def check_ref_duplicates(self, result):
        reverse_map = self.get_ref_run_number_map(result)
        for run_number, annotations in reverse_map.items():
            if len(annotations) > 1:
                print(f"Duplicates: {run_number} - {annotations}")
    
    def get_overlap_samples(self):
        run_number_map = {}
        for data_type, result in self.reference.items():
            run_number_map[data_type] = self.get_ref_run_number_map(result)
        if None not in run_number_map:
            run_number_map[None] = {}
        overlap_samples = {}
        for did in self.samples:
            attributes = get_did_attributes(did)
            data_type = attributes['data_type']
            run_number = attributes['run_number']
            if ((data_type in run_number_map) and (run_number in run_number_map[data_type])) or \
            (run_number in run_number_map[None]):
                if data_type not in overlap_samples:
                    overlap_samples[data_type] = []
                overlap_samples[data_type].append(did)
                continue
            did_no_tid = get_did_without_tid(did)
            if (did_no_tid in self.exclusion_samples) or (did in self.exclusion_samples):
                if data_type not in overlap_samples:
                    overlap_samples[data_type] = []                
                overlap_samples[data_type].append(did)
                continue
            for exclusion_pattern in self.exclusion_samples_wildcard:
                if fnmatch.fnmatch(did_no_tid, exclusion_pattern):
                    if data_type not in overlap_samples:
                        overlap_samples[data_type] = []
                    overlap_samples[data_type].append(did)
                    break
        for data_type in overlap_samples:
            overlap_samples[data_type] = np.setdiff1d(overlap_samples[data_type], self.inclusion_samples)
            matched_samples = []
            for inclusion_pattern in self.inclusion_samples_wildcard:
                matched_samples.extend(fnmatch.filter(overlap_samples[data_type], inclusion_pattern))
            overlap_samples[data_type] = list(np.setdiff1d(overlap_samples[data_type], matched_samples))
        return overlap_samples
    
    @staticmethod
    def get_latest_ptag(ptags):
        if any(isinstance(ptag, list) for ptag in ptags):
            return None
        return sorted(ptags, key= lambda item: -int(item))[0]
    
    def check_DAOD_ptags(self, dids, cache: bool = False, cachedir: str = ''):
        data = {}
        n = len(dids)
        for i, did in enumerate(dids):
            attributes = get_did_attributes(did)
            tid = attributes.get("tid", None)
            if tid is None:
                key = did
            else:
                key = did.replace(f"_tid{tid}", "")
            if key not in data:
                data[key] = {'samples': []}
                data[key]['ptag'] = attributes['ptag']
            data[key]['samples'].append(did)
        if (cache and cachedir) and not os.path.exists(cachedir):
            os.makedirs(cachedir)
        n = len(data)
        for i, key in enumerate(data):
            print(f"Sample ({i+1}/{n}): {key}")
            key_data = data[key]
            cachepath = os.path.join(cachedir, f'{key}.json')
            if cache and os.path.exists(cachepath):
                with open(cachepath, 'r') as cachefile:
                    did_ptag_variants = json.load(cachefile)
            else:
                did_ptag_variants = get_did_tag_variants(key, tag_label='p')
            if cache:
                with open(cachepath, 'w') as cachefile:
                    json.dump(did_ptag_variants, cachefile)
            key_data['samples_with_other_ptags'] = did_ptag_variants
            ptags_available = []
            for _did in did_ptag_variants:
                _attributes = get_did_attributes(_did)
                if _attributes['ptag'] not in ptags_available:
                    ptags_available.append(_attributes['ptag'])
            key_data['ptags_available'] = ptags_available
            latest_ptag = self.get_latest_ptag(ptags_available)
            ptag = key_data['ptag']
            if (latest_ptag is None) or (latest_ptag == ptag):
                key_data['is_latest'] = True
            else:
                key_data['is_latest'] = False
        return data
    
    def process_deletion(self, outdir:str="output", ptag_threshold:Optional[int]=0, cache:bool=True):
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        key_expr = "{scope}.{run_number}.{stream_name}.{prod_step}.{data_type}"
        samples_by_dtype = {}
        for did in self.samples:
            attributes = get_did_attributes(did)
            data_type = attributes['data_type']
            if data_type not in samples_by_dtype:
                samples_by_dtype[data_type] = []
            samples_by_dtype[data_type].append(did)
        for dtype in samples_by_dtype:
            result = samples_by_dtype[dtype]
            outpath = os.path.join(outdir, f"{dtype}.json")
            with open(outpath, "w") as out:
                json.dump(result, out, indent=2)
        overlap_samples = self.get_overlap_samples()
        for dtype in overlap_samples:
            result = overlap_samples[dtype]
            outpath = os.path.join(outdir, f"{dtype}_overlap.json")
            with open(outpath, "w") as out:
                json.dump(result, out, indent=2)
        DAOD_ptag_checks = {}
        cachedir = os.path.join(outdir, 'cache')
        for dtype in samples_by_dtype:
            if 'DAOD' in dtype:
                dids = samples_by_dtype[dtype]
                outpath = os.path.join(outdir, f"{dtype}_ptag_checks.json")
                if os.path.exists(outpath) and cache:
                    print("INFO: Cached DAOD check result.")
                    DAOD_ptag_checks[dtype] = json.load(open(outpath))
                    continue
                else:
                    DAOD_ptag_checks[dtype] = self.check_DAOD_ptags(dids, cache=cache, cachedir=cachedir)
                    json.dump(DAOD_ptag_checks[dtype], open(outpath, 'w'), indent=2)
        summary = {'keep': {}, 'delete': {}}
        for dtype in samples_by_dtype:
            summary['keep'][dtype] = []
            summary['delete'][dtype] = []
            samples = samples_by_dtype[dtype]
            if 'DAOD' in dtype:
                DAOD_checker = DAOD_ptag_checks[dtype]
            else:
                DAOD_checker = None
            overlaps = overlap_samples.get(dtype, [])
            reference = self.reference[dtype]
            run_number_map = self.get_ref_run_number_map(reference)
            n = len(samples)
            for i, sample in enumerate(samples):
                print(f"{dtype} ({i+1}/{n}): {sample}")
                data = {
                    'DSID': sample,
                    'description': ""
                }
                attributes = get_did_attributes(sample)
                if DAOD_checker is not None:
                    tid = attributes.get("tid", None)
                    if tid is None:
                        key = sample
                    else:
                        key = sample.replace(f"_tid{tid}", "")
                    daod_info = DAOD_checker[key]
                    data['ptag'] = daod_info['ptag']
                    ptags_available = [str(i) for i in daod_info['ptags_available']]
                    data['ptags_available'] = " ".join(ptags_available)
                decision = None
                if sample not in overlaps:
                    decision = 'delete'
                else:
                    run_number = attributes['run_number']
                    if run_number in run_number_map:
                        data['description'] = run_number_map[run_number][0]
                    else:
                        data['description'] = ''
                    if DAOD_checker is not None:
                        if (daod_info['is_latest']):
                            if isinstance(data['ptag'], list):
                                ptag = max([int(i) for i in data['ptag']])
                            else:
                                ptag = int(data['ptag'])
                            if ptag >= ptag_threshold:
                                decision = 'keep'
                            else:
                                decision = 'delete'
                        else:
                            decision = 'delete'
                    else:
                        decision = 'keep'
                summary[decision][dtype].append(data)
        summary_outpath = os.path.join(outdir, 'summary.json')
        json.dump(summary, open(summary_outpath, 'w'), indent=2)
        
        extension_list_filepath = os.path.join(outdir, 'extension_list.txt')
        with open(extension_list_filepath, "w") as f:
            for dtype in summary["keep"]:
                samples = summary["keep"][dtype]
                for sample in samples:
                    f.write(f"{sample['DSID']}\n")
        
        excel_outpath = os.path.join(outdir, 'summary.xlsx')
        with pd.ExcelWriter(excel_outpath, engine='xlsxwriter') as writer:
            for action in summary:
                for dtype in summary[action]:
                    sheet_name = f"{dtype}_to_{action}"
                    df = pd.DataFrame(summary[action][dtype])
                    if not len(df):
                        continue
                    df = df.sort_values(['description', 'DSID'], ignore_index=True)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        expiration_date = datetime.date.today() + relativedelta(years=1)
        extension_command = f"rucio add-lifetime-exception --inputfile {extension_list_filepath} " +\
                            f"--reason REASON --expiration {expiration_date}"
        print(extension_command)
        return summary