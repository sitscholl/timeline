# -*- coding: utf-8 -*-
"""
Created on Fri Sep 22 09:46:30 2023

@author: sitscholl
"""

##To dos:
# Add column "Pflückgänge" and explode table if multiple pflückgänge. Use a list in Reihenfolge to determine order
# Add two tabs: Zupfen und Ernte with two timelines
# Save modifications to input fields for next session

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# import matplotlib.pyplot as plt
# import seaborn as sns
import gspread
from gspread_dataframe import get_as_dataframe
import datetime
from datetime import timedelta
from collections import defaultdict
from streamlit_sortables import sort_items

st.set_page_config("Timeline", initial_sidebar_state="collapsed")

####
creds = st.secrets["gcp_service_account"]
####

####Connect to google account
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
client = gspread.service_account_from_dict(creds, scope)

#### Input fields
type = st.selectbox(
    "Arbeit auswählen",
    options=(
        ("Zupfen", "Ernte")
        if datetime.datetime.today().month < 8
        else ("Ernte", "Zupfen")
    ),
)
estart = st.date_input("Erntebeginn", value=datetime.date(2024, 6, 14))
with st.sidebar:
    n_people = st.number_input(
        "Arbeiter", value=9.0 if type == "Ernte" else 4.0, min_value=0.0, step=0.5
    )

    _HOUR_START = st.number_input(
        "Arbeitsbeginn [Stunde]", value=7.5, min_value=0.0, max_value=23.0
    )
    _HOUR_END = st.number_input(
        "Arbeitsende [Stunde]", value=18.0, min_value=0.0, max_value=23.0
    )
    _BREAKS = st.number_input(
        "Dauer Mittagspause [Stunden]", value=1.5, min_value=0.0, max_value=23.0
    )

    snd_work = st.checkbox("Sonntag Arbeiten?")
    st.write(f"Tägliche Arbeitsstunden: {(_HOUR_END - _HOUR_START) - _BREAKS}h")

if _HOUR_END < _HOUR_START:
    raise ValueError("Arbeitsende kann nicht vor Arbeitsbeginn sein!")

#### Compute variables
dur_col = {"Zupfen": "_Zupfen [h]", "Ernte": "_Ernte [h]"}[type]
n_stunden = (_HOUR_END - _HOUR_START) - _BREAKS

_HOUR_START_INT = int(_HOUR_START)
_MINUTES_START_INT = int((_HOUR_START * 60) % 60)
estart = datetime.datetime(
    estart.year, estart.month, estart.day, _HOUR_START_INT, _MINUTES_START_INT, 0
)
st.write(f"Start date: {estart}")

####Load gsheets table and reformat
gsheet = client.open("Feldaufnahmen")
tbl = get_as_dataframe(
    gsheet.worksheet("Wiesen"), na_values="NA", evaluate_formulas=True
)
tbl = tbl[
    [
        "Reihenfolge",
        "Jahr",
        "Wiesenabschnitt",
        "Sorte",
        "Sortengruppe",
        "Zupfen [h]",
        "Ernte [h]",
        "_Zupfen [h]",
        "_Ernte [h]",
        "_Kisten [n]",
        "_Ertrag [kg]",
    ]
]
tbl.replace("NA", np.nan, inplace=True)
tbl["_Kisten [n]"] = tbl["_Kisten [n]"].round(1)
tbl["_Ertrag [kg]"] = tbl["_Ertrag [kg]"].round(1)
tbl.dropna(how="all", axis=1, inplace=True)

#### Fill missing values
tbl_mean = (
    tbl.loc[(tbl["Jahr"] >= 2023)]
    .groupby(["Wiesenabschnitt", "Sorte"])[["Zupfen [h]", "Ernte [h]"]]
    .mean()
)

####Filter
tbl = tbl.loc[(tbl["Jahr"] == 2024)]  # (tbl["Sortengruppe"] == "Hauptsorte") &
tbl.set_index(["Wiesenabschnitt", "Sorte"], inplace=True)

##### Fill missing values
for c in ["_Zupfen [h]", "_Ernte [h]"]:
    tbl.loc[tbl[c].isna(), f"{c}_fill"] = True
    tbl[f"{c}_fill"].fillna(False, inplace=True)
    tbl[c] = tbl[c].fillna(tbl_mean[c.lstrip("_")])
#    n_na = tbl[c].isna().sum()
#    if n_na > 0:
#        tbl[c] = tbl[c].fillna(n_stunden * n_people)
#        st.warning(f"Filled {n_na} missing values for column {c}")

tbl.reset_index(inplace=True)

####Add column Reihenfolge
tbl["Reihenfolge"].fillna(999, inplace=True)
tbl.loc[tbl[dur_col].isna(), "Reihenfolge"] = 999
tbl.sort_values("Reihenfolge", inplace=True)
tbl = tbl[["Reihenfolge"] + [i for i in tbl.columns if i != "Reihenfolge"]]

####Add unique Name for each field
tbl.loc[tbl[f"{dur_col}_fill"], "Wiesenabschnitt"] = tbl["Wiesenabschnitt"].str.upper()
tbl.loc[tbl[f"{dur_col}_fill"], "Sorte"] = tbl["Sorte"].str.upper()
tbl["ylab"] = (
    tbl["Reihenfolge"].astype(int).astype(str)
    + " "
    + tbl["Wiesenabschnitt"]
    + " ("
    + tbl["Sorte"]
    + ")"
)

#### Manual sorting plugin
st.markdown("**Reihenfolge ändern:**")
sorted_items = sort_items(list(tbl["ylab"].unique()))
sorted_man = (
    pd.DataFrame(sorted_items, columns=["ylab"])
    .rename_axis("Reihenfolge")
    .reset_index()
)
tbl = sorted_man.merge(tbl.drop('Reihenfolge', axis = 1), on = 'ylab', how = 'left')

####Editable Dataframe
with st.expander("Edit data"):
    tbl_plot = st.data_editor(
        tbl, disabled=[i for i in tbl.columns if i != "Reihenfolge"]
    )

####Prepare columns for End Date calculation and plotting
tbl_plot[f"{dur_col}_re"] = (tbl_plot[dur_col] / (n_people * n_stunden)).round(
    2
).astype(str) + " days"

####Main loop: Loop over table and calculate end time for each field, based on working hours per day and number of workers
end_dates = []
curr_date = estart
for h in tbl_plot[dur_col]:

    # st.write(f"Required hours for field {nam}: {h/n_people}")
    while h > 0:

        # Available working hours on current date until feierabend
        # If hour <= 12: Mittagspause mit einbeziehen
        if (curr_date.weekday() == 6) & (not snd_work):
            working_hours = 0
        elif curr_date.hour <= 12:
            working_hours = _HOUR_END - curr_date.hour - curr_date.minute / 60 - _BREAKS
        else:
            working_hours = _HOUR_END - curr_date.hour - curr_date.minute / 60

        # Total work equivalent for current day
        working_hours_tot = working_hours * n_people

        # If field requires more hours than available for this day: proceed to next day at _HOUR_START
        if h > working_hours_tot:
            curr_date = (curr_date + timedelta(days=1)).replace(
                hour=_HOUR_START_INT, minute=_MINUTES_START_INT, second=0
            )
        # Otherwise add remaining hours for field to current day
        else:
            curr_date += timedelta(hours=(h / n_people))

        # Subtract hours done on this day
        h -= working_hours_tot

    # Round end date to nearest hour
    hour_round = round(curr_date.hour + curr_date.minute / 60 + curr_date.second / 3600)
    curr_date = curr_date.replace(hour=hour_round, minute=0, second=0, microsecond=0)

    # Append to list
    end_dates.append(curr_date)

#### Add columns to dataframe
tbl_plot["End Date"] = end_dates
tbl_plot["Start Date"] = tbl_plot["End Date"].shift(1).fillna(estart)

#### Timeline plot
fig = px.timeline(
    tbl_plot,
    x_start="Start Date",
    x_end="End Date",
    y="ylab",
    hover_name="ylab",
    hover_data={
        "ylab": False,
        f"{dur_col}_re": True,
        "_Kisten [n]": True,
        "_Ertrag [kg]": True,
    },
)
#### Format x-axis
fig.update_xaxes(
    showgrid=True,
    ticks="outside",
    # ticklabelmode="period",
    tickcolor="black",
    gridcolor="black",
    ticklen=10,
    dtick=86400000.0 * 7,  # 7 days
    tick0=estart,
    # tickformat = '%d-%m-%Y\n(%a)',
    minor=dict(
        ticklen=4, dtick=1 * 24 * 60 * 60 * 1000, gridcolor="LightGrey"  # 1 day
    ),
)

#### Format y-axis
fig.update_yaxes(title="")
# fig.update_layout(hovermode="x unified")

#### Add red line for today
fig.add_vline(
    x=datetime.datetime.today(), line_color="Red"
)  # pd.to_datetime("2023-09-18", format="%Y-%m-%d")

#### Render plot
st.plotly_chart(fig)
