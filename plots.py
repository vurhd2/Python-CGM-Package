import pandas as pd
import numpy as np
import preprocessing as pp
import configparser
import json

import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

config = configparser.ConfigParser()
config.read('config.ini')
ID = config['variables']['id']
GLUCOSE = config['variables']['glucose']
TIME = config['variables']['time']
BEFORE = config['variables']['before']
AFTER = config['variables']['after']
TYPE = config['variables']['type']
DESCRIPTION = config['variables']['description']

def daily_plot_all(
    df: pd.DataFrame,
    events: pd.DataFrame = None,
    height: int = 2000
):
    """
    Graphs (and possibly saves) daily plots for all of the patients in the given DataFrame
    @param df         a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
    @param events     a DataFrame containing event timeframes for some (or all) of the given patients
    @param height
    """
    for id, data in df.groupby(ID):
        daily_plot(data, id, height, events)

def daily_plot(
   df: pd.DataFrame,
   id: str,
   height: int = 2000,
   events: pd.DataFrame = None,
   app = False
):
   """
   Only graphs (and possibly saves) a daily plot for the given patient
   @param df   a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
   @param id   the id of the patient whose data is graphed
   @param events  a DataFrame containing event timeframes for some (or all) of the given patients
   """
   show_events = events is not None
   data = df.loc[id].copy()

   data["Day"] = data[TIME].dt.date
   days = data["Day"].astype(str).unique().tolist()

   fig = make_subplots(rows=len(days), cols=2 if show_events else 1, column_widths=[0.66,0.34] if show_events else None,
                        specs=[[{"type":"scatter"}, {"type":"table"}] for i in range(len(days))] if show_events else None,
                        horizontal_spacing=0.01 if show_events else None)
   row = 1
   row_height = 0
   for day, dataset in data.groupby("Day"):
      fig.add_trace(go.Scatter(x=dataset[TIME],y=dataset[GLUCOSE],mode='lines+markers',name=str(day)), row=row, col=1)

      if show_events:
         events[TIME] = pd.to_datetime(events[TIME])
         day_events = events[(events[TIME].dt.date == day) & (events[ID] == id)].sort_values(TIME)
         table_body = [day_events[TIME].dt.time.astype(str).tolist(), day_events["Description"].tolist()]
         row_height = max(row_height, day_events.shape[0])
         if day_events.shape[0] != 0:
            fig.add_trace(
               go.Table(
                  columnwidth=[10,40],
                  header=dict(values = [["<b>Time</b>"], ["<b>Description</b>"]],font=dict(size=11)),
                  cells=dict(values=table_body,align=['left', 'left'],font=dict(size=10),)
               ), row=row, col=2
            )
      row += 1

   if show_events:
      if isinstance(events, pd.DataFrame):
         event_data = events[events[ID] == id] if events is not None else None
         if event_data is not None:
            event_types = event_data['Type'].unique()
            with open('event_colors.json') as colors_file:
               color_dict = json.load(colors_file)
               colors = list(color_dict.values())
               color_map = {event_type: colors[i] for i, event_type in enumerate(event_types)}
               for index, row in event_data.iterrows():
                  r = days.index(str(row[TIME].date())) + 1
                  fig.add_shape(go.layout.Shape(
                     type="line", 
                     yref="y domain",
                     x0=pd.to_datetime(row[TIME]), 
                     y0=0,
                     x1=pd.to_datetime(row[TIME]),
                     y1=1,
                     line=dict(color=color_map[row['Type']], width=3)), row=r, col=1)
                  fig.add_annotation(yref="y domain", x=pd.to_datetime(row[TIME]), y=1, text=row['Type'], row=r, col=1, showarrow=False)
      elif events[ID] == id:
         day = str(events[TIME].dt.date)
         fig.add_vline(x=pd.to_datetime(events[TIME]), line_dash="dash", line_color=color_map[events['Type']])
         fig.add_annotation(yref="y domain", x=pd.to_datetime(events[TIME]), y=1, text=events['Type'], showarrow=False)
   
   # standardizing axes
   if len(days) > 1:
      offset_before = pd.Timedelta(hours=1, minutes=26)
      offset_after = pd.Timedelta(hours=1, minutes=23)
      fig.update_xaxes(range=[pd.Timestamp(days[0]) - offset_before, pd.Timestamp(days[1]) + offset_after], row=1, col=1)
      fig.update_xaxes(range=[pd.Timestamp(days[-1]) - offset_before, (pd.Timestamp(days[-1]) + pd.Timedelta(days=1)) + offset_after], row=len(days), col=1)
   fig.update_yaxes(range=[min(np.min(data[GLUCOSE]), 60) - 10, max(np.max(data[GLUCOSE]), 180) + 10])

   fig.update_layout(title=f"Daily Plot for {id}", height=height, showlegend=(not show_events))
   if app: return fig
   fig.show()

def event_plot_all(df: pd.DataFrame, id: str, events: pd.DataFrame, type: str):
    """
    Displays plots for all events of the given type for the given patient
    @param df        a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
    @param id        the 'id' of the patient for whom the event plots should be graphed
    @param events    a DataFrame containing event timeframes as per the usual structure
    @param type      the type of events for which plots should be generated     
    """
    relevant_events = events[(events[ID] == id) & (events[TYPE] == type)]
    for index, event in relevant_events.iterrows():
        event_plot(df, id, event, relevant_events)

def event_plot(df: pd.DataFrame, id: str, event: pd.Series, events: pd.DataFrame = None, app: bool = False):
   """
   Generates a single event plot for the given patient and event
   @param df        a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
   @param id        the 'id' of the patient for whom the event plot should be graphed
   @param event     a Pandas Series containing the event that should be plotted
   @param events    a DataFrame containing event timeframes as per the usual structure
                    (optional, if passed will just display vertical lines for all relevant events too)
   @param app       if this function is being run through the web app (should not be touched by users)     
   """
   if event[ID] != id: raise Exception("Given event does not match the 'id' given.")
   data = df.loc[id].copy()
   event[TIME] = pd.to_datetime(event[TIME])
   before = event[TIME] - pd.Timedelta(minutes=event[BEFORE])
   after = event[TIME] + pd.Timedelta(minutes=event[AFTER])

   subplot_figs = []
   data["Day"] = data[TIME].dt.date
   for day, dataset in data.groupby("Day"):
      subplot_figs.append(
         go.Scatter(
               x=dataset[TIME],
               y=dataset[GLUCOSE],
               mode='lines+markers',
               name=str(day)
         )
      )
   fig = go.Figure(data=subplot_figs, layout=go.Layout(title=f"Event Plot for {id}"))

   if events is not None:
      event_data = events[events[ID] == id] if events is not None else None
      if event_data is not None:
         event_types = event_data[TYPE].unique()
         with open('event_colors.json') as colors_file:
            color_dict = json.load(colors_file)
            colors = list(color_dict.values())
            color_map = {event_type: colors[i] for i, event_type in enumerate(event_types)}
            for index, row in event_data.iterrows():
               fig.add_vline(x=pd.to_datetime(row[TIME]), line_dash="dash", line_color=color_map[row[TYPE]])
               fig.add_annotation(yref="y domain", x=pd.to_datetime(row[TIME]), y=1, text=row[TYPE], showarrow=False)
   else:
      fig.add_vline(x=pd.to_datetime(event[TIME]), line_dash="dash", line_color=color_map[event[TYPE]])
      fig.add_annotation(yref="y domain", x=pd.to_datetime(event[TIME]), y=1, text=event[TYPE], showarrow=False)

   fig.update_xaxes(type="date", range=[before, after])
   if app: return fig
   fig.show()

def weekly_plot_all(df: pd.DataFrame, height: int = 1000):
   """
   Displays Weekly (Time-Series) Plots for each patient in the given DataFrame
   @param df        a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
   @param height    the height of the resulting plot (in pixels)
   """
   for id, data in df.groupby(ID):
      weekly_plot(data, id, height)

def weekly_plot(df: pd.DataFrame, id: str, height: int = 1000, app = False):
   """
   Displays a Weekly (Time-Series) Plot for only the given patient in the DataFrame
   @param df        a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
   @param id        the id of the single patient whose data is being graphed
   @param height    the height of the resulting plot (in pixels)
   @param app       a boolean indicating whether this function is being run within the web app or not
   """
   data = df.loc[id].reset_index().copy()
   data.set_index(TIME, inplace=True)

   weekly_data = data.groupby(pd.Grouper(freq='W'))
   weekly_dfs = [group for _, group in weekly_data]
   
   fig = make_subplots(rows=len(weekly_dfs), cols=1)
   for week_index in range(len(weekly_dfs)):
      week = weekly_dfs[week_index].reset_index()
      fig.add_trace(
         go.Scatter(
               x=week[TIME],
               y=week[GLUCOSE],
               mode='lines+markers',
         ), row=(week_index+1), col=1
      )
   
   if len(weekly_dfs) > 1:
      offset_before = pd.Timedelta(hours=10)
      offset_after = pd.Timedelta(hours=10)
      first_end = pd.Timestamp(weekly_dfs[1].reset_index()[TIME].dt.date.iloc[0])
      first_start = first_end - pd.Timedelta(weeks=1)
      last_start = pd.Timestamp(weekly_dfs[-1].reset_index()[TIME].dt.date.iloc[0])
      last_end = last_start + pd.Timedelta(weeks=1)
      fig.update_xaxes(range=[first_start - offset_before, first_end + offset_after], row=1, col=1)
      fig.update_xaxes(range=[last_start - offset_before, last_end + offset_after], row=len(weekly_dfs), col=1)
   fig.update_yaxes(range=[min(np.min(data[GLUCOSE]), 60) - 10, max(np.max(data[GLUCOSE]), 180) + 10])
   fig.update_xaxes(tickformat="%B %d, %Y <br> (%a)")

   fig.update_layout(title=f"Weekly Plot for {id}", height=height, showlegend=False)

   if app: return fig
   fig.show()

def spaghetti_plot_all(df: pd.DataFrame, chunk_day: bool = False, height: int = 600):
    """
    Sequentially produces spaghetti plots for all the given patients
    @param df         a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
    @param chunk_day  a boolean indicating whether to split weekdays and weekends
    @param height     the height of the resulting plot (in pixels)
    """
    for id, data in df.groupby(ID):
        spaghetti_plot(data, id, chunk_day, height)

def spaghetti_plot(
    df: pd.DataFrame, id: str, chunk_day: bool = False, height: int = 600, app=False
):
    """
    Graphs a spaghetti plot for the given patient
    @param df           a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
    @param id           the id of the patient whose data should be plotted
    @param chunk_day    a boolean indicating whether to split weekdays and weekends
    @param height       the height of the resulting plot (in pixels)
    @param app          a boolean indicating whether this function is being run within the web app or not
    """
    data = df.loc[id].copy()
    data["Day"] = data[TIME].dt.date
    times = data[TIME] - data[TIME].dt.normalize()
    data["Time"] = (pd.to_datetime(["1/1/1970" for i in range(data[TIME].size)]) + times)
    data.sort_values(by=[TIME], inplace=True)

    fig = px.line(data, x="Time", y=GLUCOSE, color="Day", title=f"Spaghetti Plot for {id}", height=height, facet_col="Day Chunking" if chunk_day else None)
    fig.update_xaxes(tickformat="%H:%M:%S", title_text="Time") # shows only the times for the x-axis
    
    if app: return fig
    fig.show()

def AGP_plot_all(df: pd.DataFrame, height: int = 600):
    """
    Displays AGP Plots for each patient in the given DataFrame
    @param df        a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
    @param height    the height of the resulting plot (in pixels)
    """
    for id, data in df.groupby(ID):
        AGP_plot(data, id, height)


def AGP_plot(df: pd.DataFrame, id: str, height: int = 600, app=False):
    """
    Displays an AGP Plot for only the given patient in the DataFrame
    @param df        a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
    @param id        the id of the single patient whose data is being graphed
    @param height    the height of the resulting plot (in pixels)
    @param app       a boolean indicating whether this function is being run within the web app or not
    """
    if pp.get_interval() > 5:
         raise Exception("Data needs to have measurement intervals at most 5 minutes long")

    data = df.loc[id]  
    data.reset_index(inplace=True)

    data[[TIME, GLUCOSE]] = pp.resample_data(data[[TIME, GLUCOSE]])
    times = data[TIME] - data[TIME].dt.normalize()
    # need to be in a DateTime format so seaborn can tell how to scale the x axis labels below
    data["Time"] = (pd.to_datetime(["1/1/1970" for i in range(data[TIME].size)]) + times)

    data.set_index("Time", inplace=True)

    agp_data = pd.DataFrame()
    for time, measurements in data.groupby("Time"):
      metrics = {
         "Time": time,
         "5th": measurements[GLUCOSE].quantile(0.05),
         "25th": measurements[GLUCOSE].quantile(0.25),
         "Median": measurements[GLUCOSE].median(),
         "75th": measurements[GLUCOSE].quantile(0.75),
         "95th": measurements[GLUCOSE].quantile(0.95),
      }
      agp_data = pd.concat([agp_data, pd.DataFrame.from_records([metrics])])

    agp_data.sort_values(by=["Time"], inplace=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(name="5th", x=agp_data["Time"], y=agp_data["5th"], line=dict(color="#869FCE")))
    fig.add_trace(go.Scatter(name="25th", x=agp_data["Time"], y=agp_data["25th"], fill="tonexty", fillcolor="#C9D4E9", line=dict(color="#97A8CB")))
    fig.add_trace(go.Scatter(name="Median",x=agp_data["Time"], y=agp_data["Median"], fill="tonexty", fillcolor="#97A8CB", line=dict(color="#183260")))
    fig.add_trace(go.Scatter(name="75th", x=agp_data["Time"], y=agp_data["75th"], fill="tonexty", fillcolor="#97A8CB", line=dict(color="#97A8CB")))
    fig.add_trace(go.Scatter(name="95th", x=agp_data["Time"], y=agp_data["95th"], fill="tonexty", fillcolor="#C9D4E9", line=dict(color="#869FCE")))

    fig.add_hline(y=70, line_color="green")
    fig.add_hline(y=180, line_color="green")
    fig.update_layout(title={"text": f"AGP Plot for {id}"}, height=height, yaxis_range = [35,405])
    fig.update_xaxes(tickformat="%H:%M:%S", title_text="Time") # shows only the times for the x-axis

    if app: return fig
    fig.show()