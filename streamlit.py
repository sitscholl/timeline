# -*- coding: utf-8 -*-
"""
Created on Fri Sep 22 09:46:30 2023

@author: sitscholl
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
#import matplotlib.pyplot as plt
#import seaborn as sns
import gspread
from gspread_dataframe import get_as_dataframe
import datetime
import json

#@st.cache_data(persist = True)
#def get_estart():
#    return(datetime.date(2023, 9, 15))
#estart = get_estart()

####
creds = st.secrets['gcp_service_account']
####

####Connect to google account
scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
client = gspread.service_account_from_dict(creds, scope)

####Load gsheets table and reformat
gsheet = client.open("Feldaufnahmen")
tbl = get_as_dataframe(gsheet.worksheet('Wiesen'), na_values = 'NA', evaluate_formulas=True)
tbl = tbl[['Reihenfolge', 'Jahr', 'Wiese', 'Sorte', 'Sortengruppe', '_Ernte [h]', '_Kisten [n]', '_Ertrag [kg]']]
tbl.replace('NA', np.nan, inplace = True)
tbl['_Kisten [n]'] = tbl['_Kisten [n]'].round(1)
tbl['_Ertrag [kg]'] = tbl['_Ertrag [kg]'].round(1)
tbl.dropna(how = 'all', axis = 1, inplace = True)

####Filter
tbl = tbl.loc[(tbl['Sortengruppe'] == 'Hauptsorte') & (tbl['Jahr'] == 2023)]

####Add column Reihenfolge
if 'Reihenfolge' not in tbl.columns:
    tbl['Reihenfolge'] = tbl.index + 1
tbl = tbl[['Reihenfolge'] + [i for i in tbl.columns if i != 'Reihenfolge']]

####Params fields
with st.expander('Edit params'):
    estart = st.date_input('Erntebeginn', value = datetime.date(2023, 9, 18))
    n_people = st.number_input('Arbeiter', value = 9.0, min_value = 0.0, step = .5)
    n_stunden = st.number_input('Arbeitsstunden pro Tag', value = 9.5, min_value = 0.0, max_value = 24.0, step = .5)
    
#st.write(estart_in)
#if estart_in is not None:
#    estart = estart_in
#st.write(estart)
    
stunden_tag = n_people * n_stunden

####Editable Dataframe
with st.expander('Edit data'):
    tbl_plot = st.data_editor(tbl, disabled = [i for i in tbl.columns if i != 'Reihenfolge'])
tbl_plot['ylab'] = tbl_plot['Wiese'] + ' (' + tbl_plot['Sorte'] + ')'
tbl_plot.sort_values('Reihenfolge', inplace = True)

tbl_plot['Dauer'] = tbl_plot['_Ernte [h]'] / stunden_tag
tbl_plot['Dauer'] = .5 * np.round(tbl_plot['Dauer']/.5) ##round to .5
tbl_plot['Dauer'] = tbl_plot['Dauer'].clip(lower = .5)

tbl_plot['Start Date'] = pd.to_datetime(estart) + pd.to_timedelta(tbl_plot['Dauer'].shift(1).fillna(0).cumsum(), unit='D')
tbl_plot['End Date'] = tbl_plot['Start Date'] + pd.to_timedelta(tbl_plot['Dauer'], unit='D')

####Plot
fig = px.timeline(tbl_plot, x_start="Start Date", x_end="End Date", y="ylab",
                  hover_name = 'ylab',
                  hover_data = {'ylab': False,
                                'Dauer': True,
                                '_Kisten [n]': True,
                                '_Ertrag [kg]': True})
##Format x-axis
fig.update_xaxes(showgrid = True,
                 ticks= "outside",
                 ticklabelmode= "period", 
                 tickcolor= "black", 
                 gridcolor = 'black',
                 ticklen=10,
                 dtick = 86400000.0 * 7, #7 days
                 tick0 = estart,
                 #tickformat = '%d-%m-%Y\n(%a)',
                 minor=dict(
                     ticklen=4,  
                     dtick=1*24*60*60*1000, #1 day
                     gridcolor='LightGrey')
                )

#Format y-axis
fig.update_yaxes(title='')

##Add red line for today
fig.add_vline(x = datetime.datetime.today(), line_color = 'Red')

st.plotly_chart(fig)

