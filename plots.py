import pandas as pd
import seaborn as sns
import preprocessing as pp
import matplotlib.pyplot as plt
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
GLUCOSE = config['variables']['glucose']
TIME = config['variables']['time']
INTERVAL = config['variables'].getint('interval')

"""
Graphs (and possibly saves) daily plots for all of the patients in the given DataFrame
@param df         a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
@param events     a DataFrame containing event timeframes for some (or all) of the given patients
@param chunk_day  a boolean indicating whether to split weekdays and weekends
@param save       a boolean indicating whether to download the graphs locally
"""


def daily_plot_all(
    df: pd.DataFrame,
    events: pd.DataFrame = None,
    chunk_day: bool = False,
    save: bool = False,
):
    sns.set_theme()
    for id, data in df.groupby("id"):
        daily_plot(data, id, events, chunk_day, save)


"""
Only graphs (and possibly saves) a daily plot for the given patient
@param df   a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
@param id   the id of the patient whose data is graphed
@param events  a DataFrame containing event timeframes for some (or all) of the given patients
@param chunk_day  a boolean indicating whether to split weekdays and weekends
@param save a boolean indicating whether to download the graphs locally
"""


def daily_plot(
    df: pd.DataFrame,
    id: str,
    events: pd.DataFrame = None,
    chunk_day: bool = False,
    save: bool = False,
):
    data = df.loc[id]

    data[TIME] = pd.to_datetime(data[TIME])
    data.reset_index(inplace=True)

    plot = sns.relplot(
        data=data,
        kind="line",
        x=TIME,
        y=GLUCOSE,
        col="Day Chunking" if chunk_day else None,
    )
    plot.fig.subplots_adjust(top=0.9)
    plot.fig.suptitle(f"Glucose (mg/dL) vs. Timestamp for {id}")

    # plotting vertical lines to represent the events
    if events is not None:
        event_data = events.set_index("id").loc[id]
        for ax in plot.axes.flat:
            if isinstance(event_data, pd.DataFrame):
                for index, row in event_data.iterrows():
                    ax.axvline(pd.to_datetime(row[TIME]), color="orange")
            else:
                ax.axvline(pd.to_datetime(event_data[TIME]), color="orange")

    plt.ylim(35, 405)
    plt.show()

    if save:
        plot.savefig("./plots/" + str(id) + "Daily.png")


"""
Sequentially produces spaghetti plots for all the given patients
@param df   a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
@param chunk_day  a boolean indicating whether to split weekdays and weekends
@param save a boolean indicating whether to download the graphs locally
"""


def spaghetti_plot_all(df: pd.DataFrame, chunk_day: bool = False, save: bool = False):
    sns.set_theme()
    for id, data in df.groupby("id"):
        spaghetti_plot(data, id, chunk_day, save)


"""
Graphs a spaghetti plot for the given patient
@param df   a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns
@param id   the id of the patient whose data should be plotted
@param chunk_day  a boolean indicating whether to split weekdays and weekends
@param save a boolean indicating whether to download the graphs locally
"""


def spaghetti_plot(
    df: pd.DataFrame, id: str, chunk_day: bool = False, save: bool = False
):
    data = df.loc[id]

    data.reset_index(inplace=True)

    # Convert timestamp column to datetime format
    data[TIME] = pd.to_datetime(data[TIME])

    data["Day"] = data[TIME].dt.date

    times = data[TIME] - data[TIME].dt.normalize()
    # need to be in a DateTime format so seaborn can tell how to scale the x axis labels
    data["Time"] = (
        pd.to_datetime(["1/1/1970" for i in range(data[TIME].size)]) + times
    )

    data.sort_values(by=[TIME], inplace=True)

    plot = sns.relplot(
        data=data,
        kind="line",
        x="Time",
        y=GLUCOSE,
        hue="Day",
        col="Day Chunking" if chunk_day else None,
    )

    plot.fig.subplots_adjust(top=0.9)
    plot.fig.suptitle(f"Spaghetti Plot for {id}")

    plt.xticks(
        pd.to_datetime([f"1/1/1970T{hour:02d}:00:00" for hour in range(24)]),
        (f"{hour:02d}:00" for hour in range(24)),
    )
    plt.ylim(35, 405)
    for ax in plot.axes.flat:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    plt.show()  # might result in an empty plot based on osx or matplotlib version apparently

    if save:
        plt.savefig("./plots/" + str(id) + "Spaghetti.png", bbox_inches="tight")


"""
Displays (and possibly saves) AGP Plots for each patient in the given DataFrame
@param df   a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
@param save a boolean indicating whether to download the graphs locally
"""


def AGP_plot_all(df: pd.DataFrame, save: bool = False):
    sns.set_theme()
    for id, data in df.groupby("id"):
        AGP_plot(data, id, save)


"""
Displays (and possibly saves) an AGP Plot for only the given patient in the DataFrame
@param df   a Multiindexed DataFrame grouped by 'id' and containing DateTime and Glucose columns containing all patient data
@param id   the id of the single patient whose data is being graphed
@param save a boolean indicating whether to download the graphs locally
"""


def AGP_plot(df: pd.DataFrame, id: str, save: bool = False):
    if INTERVAL > 5:
        raise Exception(
            "Data needs to have measurement intervals at most 5 minutes long"
        )

    data = df.loc[id]
    data.reset_index(inplace=True)

    data[[TIME, GLUCOSE]] = pp.resample_data(data[[TIME, GLUCOSE]])
    times = data[TIME] - data[TIME].dt.normalize()
    # need to be in a DateTime format so seaborn can tell how to scale the x axis labels below
    data["Time"] = (
        pd.to_datetime(["1/1/1970" for i in range(data[TIME].size)]) + times
    )

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

    agp_data = pd.melt(
        agp_data,
        id_vars=["Time"],
        value_vars=["5th", "25th", "Median", "75th", "95th"],
        var_name="Metric",
        value_name=GLUCOSE,
    )

    agp_data.sort_values(by=["Time"], inplace=True)

    plot = sns.relplot(
        data=agp_data,
        kind="line",
        x="Time",
        y=GLUCOSE,
        hue="Metric",
        hue_order=["95th", "75th", "Median", "25th", "5th"],
        palette=["#869FCE", "#97A8CB", "#183260", "#97A8CB", "#869FCE"],
    )

    plot.fig.subplots_adjust(top=0.9)
    plot.fig.suptitle(f"AGP Plot for {id}")

    plt.xticks(
        pd.to_datetime([f"1/1/1970T{hour:02d}:00:00" for hour in range(24)]),
        (f"{hour:02d}:00" for hour in range(24)),
    )
    plt.xticks(rotation=45)
    plt.ylim(35, 405)

    for ax in plot.axes.flat:
        ax.axhline(70, color="green")
        ax.axhline(180, color="green")

        # shading between lines
        plt.fill_between(
            ax.lines[0].get_xdata(),
            ax.lines[0].get_ydata(),
            ax.lines[1].get_ydata(),
            color="#C9D4E9",
        )
        plt.fill_between(
            ax.lines[1].get_xdata(),
            ax.lines[1].get_ydata(),
            ax.lines[3].get_ydata(),
            color="#97A8CB",
        )
        plt.fill_between(
            ax.lines[3].get_xdata(),
            ax.lines[3].get_ydata(),
            ax.lines[4].get_ydata(),
            color="#C9D4E9",
        )

    plt.show()

    if save:
        plt.savefig("./plots/" + str(id) + "AGP.png", bbox_inches="tight")
