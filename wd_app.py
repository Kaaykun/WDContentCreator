import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
from display_info import *
import pandas as pd
import re
import os
import shutil
from functools import reduce
from collections import defaultdict


csv_patterns = {
    'dragon': (r"^(Dragon|ParticleEffect|Projectile|Swappable|DragonAttack|"
               r"DragonParentChildRelations|Currency|DragonPerchAttackFrame)\.csv"),
    'rider': r"fkjhsladkfjhasldfhjaslf\.csv",
    'spell': r"asdjfhlasjkhflajskfhlsa\.csv"
}

# initialize the state for dragons, riders, spells
asset_types = ['dragon', 'rider', 'spell']
for asset_type in asset_types:
    if asset_type not in st.session_state:
        st.session_state[ asset_type ] = {}
if 'create_asset_msg' not in st.session_state:
    st.session_state.create_asset_msg = ''

def all_assets():
    assets = {}
    assets.update(st.session_state.dragon)
    assets.update(st.session_state.rider)
    assets.update(st.session_state.spell)
    return assets

def find_similar_ids(asset_type, id, keys):
    keys = [item for item in keys if re.search(f'^{id}', item)]
    # Add the key for all missing values linked ids
    linked_ids = ('projectileIdentifier', 'onTargetParticleEffectIdentifier', 'onGroundParticleEffectIdentifier') 
    for linked_id in linked_ids:    
        for key in keys:
            if str(st.session_state[f'{asset_type}_field_defaults'][key][linked_id]) != 'nan':
                lidvalue = st.session_state[f'{asset_type}_field_defaults'][key][linked_id]
        if str(lidvalue) != 'nan':
            keys.append(lidvalue)
        
    print(st.session_state[f'{asset_type}_field_defaults'][id].keys())
    print("Similar ids of "+id+" are:")
    print(keys)
    return keys
    

def create_asset(asset_type,from_template):
    # check if an asset with the same name already exists
    if new_name in all_assets():
        st.session_state.create_asset_msg = f"{new_name} {asset_type} already exists"
    else:
        print(f"Cloning template:¥n{st.session_state[f'{asset_type}_field_defaults'][from_template]}")
        st.session_state[asset_type][new_name] = st.session_state[f'{asset_type}_field_defaults'][from_template].copy()
        st.session_state[asset_type][new_name]['identifier'] = new_name
        # voodoo magic below
        print('here we go')
        similar_ids = find_similar_ids(
                    asset_type, from_template, st.session_state[f'{asset_type_to_create}_field_defaults'].keys())
        
        for key in st.session_state[asset_type][new_name].keys():
            if str(st.session_state[asset_type][new_name][key]) == "nan":
                #look for the nan value in similar_ids
                new_key = None
                for similar_id in similar_ids:
                    nk = st.session_state[f'{asset_type}_field_defaults'][similar_id][key]
                    #print("New key from " + similar_id + " is " + nk)
                    if str(nk) != 'nan':
                        new_key = nk
                if new_key != None:
                    st.session_state[asset_type][new_name][key] = new_key
            #print('New value of '+str(key)+' is '+str(st.session_state[asset_type][new_name][key])) 

def asset_type_from_name(asset_name):
    for asset_type in asset_types:
        if asset_name in st.session_state[asset_type]:
            return asset_type
    return ''

def delete_asset(asset_name):
    # check if an asset with the same name already exists
    if asset_name in assets:
        asset_type = asset_type_from_name(asset_name)
        del st.session_state[asset_type][asset_name] 
        save_assets_to_csv()


def load_defaults():
    template_dir = st.session_state.templates
    for asset_type in asset_types:
        pattern = csv_patterns[asset_type]
        csvs = [os.path.join(p,s) for p,_,ls in os.walk(template_dir) for s in ls if re.search(pattern, s) and not '-checkpoint' in s]
        if len(csvs):
            dfs = [pd.read_csv(csv, skiprows=[1], nrows=1) for csv in csvs]
            # populate types
            dicts = [pd.read_csv(csv, nrows=1).to_dict() for csv in csvs]
            st.session_state[f'{asset_type}_field_types'] = {k:v[0] for d in dicts for k,v in d.items()}
            # populate defaults
            types = defaultdict(str)
            dfs = [pd.read_csv(csv, skiprows=[1], dtype=str, keep_default_na=False) for csv in csvs]
            dfs = [df.set_index(['identifier']) for df in dfs]
            df = merge_no_dups(dfs)
            st.session_state[f'{asset_type}_field_defaults'] = {x[r'identifier']:x for x in df.to_dict('records')}
        else:
            st.session_state[f'{asset_type}_field_types'] = {}
            st.session_state[f'{asset_type}_field_defaults'] = {}
            

def save_assets_to_csv():
    for asset_type in asset_types:
        if len(st.session_state[asset_type])==0:
            pattern = csv_patterns[asset_type]
            test_dir = f'{st.session_state.workspace}/test'
            csvs = [os.path.join(p,s) for p,_,ls in os.walk(test_dir) for s in ls if re.search(pattern, s) and not '-checkpoint' in s]
            for csv in csvs:
                os.remove(csv)       
        else:
            template_dir = st.session_state.templates
            destination_dir = f'{st.session_state.workspace}/test'
            if not os.path.exists(template_dir):
                # add some message that there are no templates 
                # so I don't know what to save
                return
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)
            assets_to_save = list(st.session_state[asset_type].values())
            if len(assets_to_save):
                df_data = pd.DataFrame.from_records(assets_to_save)
                pattern = csv_patterns[asset_type]
                templates = [(s,p) for p,_,ls in os.walk(template_dir) for s in ls if re.search(pattern, s) and not '-checkpoint' in s]
                for template, path in templates:
                    df_header = pd.read_csv(os.path.join(template_dir,template), nrows=1)
                    df = pd.concat([df_header, df_data[df_header.columns]])
                    new_path = path.replace(template_dir, destination_dir)
                    if not os.path.exists(new_path):
                        os.makedirs(new_path)
                    df.to_csv(os.path.join(new_path,template), index=False)

def merge_no_dups(dfs):
    df = dfs[0]
    for i in range(1,len(dfs)):
        df = pd.merge(df, dfs[i], left_on='identifier', right_on='identifier', how='outer',suffixes=('', '_y'))
        df = df[[col for col in df.columns if not col.endswith('_y')]]
    df = df.reset_index()
    return df

def load_assets_from_csv():
    for asset_type in asset_types:
        source_dir = f'{st.session_state.workspace}/test'
        if not os.path.exists(source_dir):
            os.makedirs(source_dir)
        pattern = csv_patterns[asset_type]
        csvs = [os.path.join(p,s) for p,_,ls in os.walk(source_dir) for s in ls if re.search(pattern, s) and not '-checkpoint' in s]
        dfs = [pd.read_csv(csv, skiprows=[1]) for csv in csvs]
        if len(dfs):
            df = merge_no_dups(dfs)
            dicts = df.to_dict('records')
            st.session_state[asset_type] = {}
            for dict in dicts:
                st.session_state[asset_type][dict['identifier']]=dict
            print(df.columns)
            

# sidebar stuff
st.sidebar.header('State Management')
st.sidebar.header('Settings')
settings = st.sidebar.expander('Folders', expanded=False)
st.session_state.workspace = settings.text_input('War Dragons root folder: ', '/Users/xanthos/workspace/dev/streamlit', max_chars=100)
st.session_state.templates = settings.text_input('War Dragons template folder: ', '/Users/xanthos/workspace/WarDragons/dragons3d/Resources/Parameters/', max_chars=100)

# load default types and values
load_defaults()

c = st.sidebar.columns(2)
c[0].button('Load from Disk', on_click=load_assets_from_csv)
c[1].button('Save to Disk', on_click=save_assets_to_csv)
st.sidebar.divider()
st.sidebar.header('Create new asset')
asset_type_to_create = st.sidebar.radio("Asset type", ["dragon", "rider", "spell"], horizontal=True)
new_name = st.sidebar.text_input('Name', 'new_asset')
list_of_ids = list(st.session_state[f'{asset_type_to_create}_field_defaults'].keys())
list_of_ids = [item for item in list_of_ids if re.search(r"^E\d{2}Q.", item)]
list_of_ids = [item for item in list_of_ids if not item.endswith((
    'Stone', 'Shard', 'egg', 'EvolutionFragment', "fireball", "lockon", "flamethrower", "unisonCharge"))]
list_of_ids.reverse()
template_name = st.sidebar.selectbox('Based on', list_of_ids)
st.sidebar.button('Create', on_click=create_asset,args=(asset_type_to_create,template_name))
creation_result = st.sidebar.text(st.session_state.create_asset_msg)
st.sidebar.divider()


assets = all_assets()
if len(assets)==0:
    load_assets_from_csv()
    assets = all_assets()

# main page
st.title('War Dragons Content Creator')
if len(assets):
    asset_names = list(assets.keys())
    tabs = st.tabs(asset_names)
    for i, tab in enumerate(tabs):
        # fix this as we are just trying to make widget id unique
        # and the below just reduces the probabilityß
        widget_id = 0
        asset_name = asset_names[i]
        asset_type = asset_type_from_name(asset_name)
        with tab:
            m = 2
            common = st.expander('Common fields', expanded=True)
            cols=common.columns(m)
            #this_dragon_fields = assets[asset_name]
            #st.session_state[asset_type][asset_name]
            for j, field in enumerate(common_fields[asset_type]):
                with cols[j%m]:
                    st.session_state[asset_type][asset_name][field] = \
                        st.text_input(f'{field} ({st.session_state[f"{asset_type}_field_types"][field]})', 
                                      st.session_state[asset_type][asset_name][field], key=f'{asset_name}{widget_id}')
                    widget_id += 1
            uncommon = st.expander('Uncommon fields', expanded=False)
            cols=uncommon.columns(m)
            for j, field in enumerate(uncommon_fields[asset_type]):
                with cols[j%m]:
                    st.session_state[asset_type][asset_name][field] = \
                        st.text_input(f'{field} ({st.session_state[f"{asset_type}_field_types"][field]})',
                                      st.session_state[asset_type][asset_name][field], key=f'{asset_name}{widget_id}')
                    widget_id += 1
            hidden_button = st.expander('Delete button inside', expanded=False)
            hidden_button.button('Delete', on_click=delete_asset, args=(asset_name,), 
                               key=f'{asset_name}{widget_id}')

# TODO
# Replace all template IDs with new IDs in all fields
# Add entries for projectile hit effect, and all other currency stones when writing to diff csvs
# Make sure the correct IDs are used when writing in the corresponding pdf
#   Currency needs all the currenciy IDs
#   Dragon attack and Projectile needs the fireball etc ID
#   ParticleEffect needs imp_drg_DRAGONID_hit and _miss
#   Swappable needs Egg? Is it ok to leave it empty for PMs?  
# Create upgrades file in dragon folder
# Find a way to copy over visual effects files in their respective folders. Simple file copy and rename from template?
# Change the way this writes to csvs, it should append data to template files instead of overwriting 