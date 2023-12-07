import pandas as pd
import numpy as np
from scipy.integrate import trapezoid
import configparser

print("B")

config = configparser.ConfigParser()
config.read('config.ini')
GLUCOSE = config['variables']['glucose']
TIME = config['variables']['time']
INTERVAL = config['variables'].getint('interval')

print("C")

def mean(df: pd.DataFrame) -> float:
    return df[GLUCOSE].mean()


def summary_stats(df: pd.DataFrame) -> list:
    min = df[GLUCOSE].min()
    first = df[GLUCOSE].quantile(0.25)
    median = df[GLUCOSE].median()
    third = df[GLUCOSE].quantile(0.75)
    max = df[GLUCOSE].max()

    return [min, first, median, third, max]


def std(df: pd.DataFrame) -> float:
    return df[GLUCOSE].std()


def a1c(df: pd.DataFrame) -> float:
    return (46.7 + mean(df)) / 28.7


def gmi(df: pd.DataFrame) -> float:
    return (0.02392 * mean(df)) + 3.31


"""
Returns the percent of total time the glucose levels were between the given lower and upper bounds (inclusive)
@param df: the data in the form of a Pandas DataFrame
@param low: the lower bound of the acceptable glucose values
@param high: the upper bound of the acceptable glucose values
"""


def percent_time_in_range(df: pd.DataFrame, low: int = 70, high: int = 180) -> float:
    in_range_df = df[(df[GLUCOSE] <= high) & (df[GLUCOSE] >= low)]
    time_in_range = len(in_range_df)
    total_time = len(df)
    return (100 * time_in_range / total_time) if total_time > 0 else np.nan


# ------------------------- EVENT-BASED ----------------------------


def AUC(df: pd.DataFrame) -> float:
    return trapezoid(df[GLUCOSE], dx=INTERVAL)


def iAUC(df: pd.DataFrame, level: int = 70) -> float:
    data = df.copy()
    data[GLUCOSE] = data[GLUCOSE] - level
    data.loc[data[GLUCOSE] < 0, GLUCOSE] = 0
    return AUC(data)


def baseline(df: pd.DataFrame) -> float:
    return df[TIME].iloc[0]


def peak(df: pd.DataFrame) -> float:
    return np.max(df[GLUCOSE])


def delta(df: pd.DataFrame) -> float:
    return peak(df) - baseline(df)


"""
Returns a Pandas Series containing the Timestamps of glucose excursions
"""


def excursions(df: pd.DataFrame) -> pd.Series:
    sd = std(df)
    ave = mean(df)

    outlier_df = df[
        (df[GLUCOSE] >= ave + (2 * sd)) | (df[GLUCOSE] <= ave - (2 * sd))
    ].copy()

    # calculate the differences between each of the timestamps
    outlier_df.reset_index(inplace=True)
    outlier_df["timedeltas"] = outlier_df[TIME].diff()[1:]

    # find the gaps between the times
    gaps = outlier_df[outlier_df["timedeltas"] > pd.Timedelta(minutes=INTERVAL)][
        TIME
    ]

    # adding initial and final timestamps so excursions at the start/end are included
    initial = pd.Series(df[TIME].iloc[0] - pd.Timedelta(seconds=1))
    final = pd.Series(df[TIME].iloc[-1] + pd.Timedelta(seconds=1))
    gaps = pd.concat([initial, gaps, final])

    # getting the timestamp of the peak within each excursion
    excursions = []
    for i in range(len(gaps) - 1):
        copy = outlier_df[
            (outlier_df[TIME] >= gaps.iloc[i])
            & (outlier_df[TIME] < gaps.iloc[i + 1])
        ][[TIME, GLUCOSE]].copy()
        copy.set_index(TIME, inplace=True)
        if np.min(copy) > ave:
            # local max
            excursions.append(copy.idxmax())
        else:
            # local min
            excursions.append(copy.idxmin())

    return pd.Series(excursions)

def ADRR(df: pd.DataFrame) -> float:
   data = df.copy()

   # Convert time to date
   data['date'] = pd.to_datetime(data[TIME]).dt.date

   data = data.dropna(subset=[GLUCOSE])

   data['bgi'] = (np.log(data[GLUCOSE]) ** 1.084) - 5.381
   data['right'] = 22.7 * np.maximum(data['bgi'], 0) ** 2
   data['left'] = 22.7 * np.minimum(data['bgi'], 0) ** 2

   adrr = data.groupby(['date']).apply(lambda df: np.max(df['left']) + np.max(df['right'])).mean()
   return adrr

def COGI(df: pd.DataFrame) -> float:
    tir = percent_time_in_range(df)
    tir_score = 0.5 * tir

    tbr = percent_time_in_range(df, 0, 70)
    tbr_score = 0.35 * ((1 - (np.minimum(tbr, 15) / 15)) * 100)

    sd = std(df)
    sd_score = 100
    if sd >= 108:
        sd_score = 0
    elif sd > 18:
        sd_score = (1 - (sd / 108)) * 100
    sd_score = 0.15 * sd_score
    
    COGI = tir_score + tbr_score + sd_score
    return COGI

def MAGE(df: pd.DataFrame, short_ma: int = 9) -> float:
    data = df.copy()
    data["MA_Short"] = data[GLUCOSE].rolling(window=short_ma, min_periods=1, center=True).mean()

    signs = np.sign(data["MA_Short"].diff())
    signs[signs==0] = -1
    crossings = np.where(np.diff(signs))[0]

    glu = lambda x: data[GLUCOSE].iloc[x]
    peak_start = 0 if glu(0) < glu(1) else 1
    valley_start = abs(peak_start - 1)
    
    peaks = [max([glu(crossings[(index * 2) + peak_start]), glu(crossings[(index * 2) + 1 + peak_start])]) for index in range(peak_start, int((len(crossings) + valley_start) / 2))]
    valleys = [min([glu(crossings[(index * 2) + valley_start]), glu(crossings[(index * 2) + 1 + valley_start])]) for index in range(valley_start, int((len(crossings) + peak_start) / 2))]
    
    #validated_peaks = peaks.copy()
    #validated_valleys = valleys.copy() 


    excursions = []
    for i in range(len(crossings) - 1):
        excursion = (
            data[GLUCOSE][crossings[i] : crossings[i + 1]].max()
            - data[GLUCOSE][crossings[i] : crossings[i + 1]].min()
        )
        if excursion > data[GLUCOSE].std():  # Only consider significant excursions
            excursions.append(excursion)
    mage = np.mean(excursions) if excursions else np.nan
    return mage


"""
def MAGE(df: pd.DataFrame) -> float:
   data = pd.DataFrame()
   data[GLUCOSE] = df[df[GLUCOSE].diff() != 0][GLUCOSE]
   data.reset_index(inplace=True)

   roc = "rate of change"
   data[roc] = data[GLUCOSE].pct_change()
   
   data.dropna(subset=[roc, GLUCOSE], inplace=True)

   mask1 = (data[roc] < 0)
   mask2 = (data[roc] > 0).shift()
   mask3 = (data[roc] > 0)
   mask4 = (data[roc] < 0).shift()

   # getting all peaks and nadirs in smoothed curve
   extrema = data[(data[roc] == 0) | (mask1 & mask2) | (mask3 & mask4)].copy()
   #extrema = extrema[extrema[GLUCOSE].diff() != 0] # getting rid of extrema plateaus

   #extrema.reset_index(inplace=True)
   extrema = extrema[GLUCOSE].copy()

   valid_extrema = [extrema.iloc[0]]
   sd = std(df)
   skip = False # boolean to skip certain iterations of for loop
   for i in range(1, len(extrema) - 1):
      if skip:
         skip = False
         continue

      glu = lambda x: extrema.iloc[x]
      is_valid = lambda x, y: abs(x - y) >= sd 

      current = glu(i)

      # if both amplitude segments are larger than the stdev, the extrema should be kept for MAGE calculations 
      if is_valid(current, valid_extrema[-1]) and is_valid(current, glu(i+1)):
         valid_extrema.append(current)
      else:
         skip = True

   amplitude = lambda x: abs(valid_extrema[x] - valid_extrema[x+1])
   amplitudes = pd.Series([amplitude(i * 2) for i in range(int(len(valid_extrema) / 2))])

   print(sd)
   print(valid_extrema)

   return amplitudes.mean()
"""

"""
Takes in a multiindexed Pandas DataFrame containing CGM data for multiple patients/datasets, and
returns a single indexed Pandas DataFrame containing summary metrics in the form of one row per patient/dataset
"""


def create_features(dataset: pd.DataFrame, events: bool = False) -> pd.DataFrame:
    df = pd.DataFrame()

    for id, data in dataset.groupby("id"):
        features = {}
        print("D")
        summary = summary_stats(data)
        print("E")
        features["id"] = id

        features["mean"] = mean(data)
        features["min"] = summary[0]
        features["first quartile"] = summary[1]
        features["median"] = summary[2]
        features["third quartile"] = summary[3]
        features["max"] = summary[4]

        features["intrasd"] = std(data)
        features["intersd"] = std(dataset)

        features["a1c"] = a1c(data)
        features["gmi"] = gmi(data)
        features["percent time in range"] = percent_time_in_range(data)
        features["ADRR"] = ADRR(data)
        features["COGI"] = COGI(data)
        #features["MAGE"] = MAGE(data)

        if events:
            features["AUC"] = AUC(data)
            features["iAUC"] = iAUC(data)
            features["baseline"] = baseline(data)
            features["peak"] = peak(data)
            features["delta"] = delta(data)

        df = pd.concat([df, pd.DataFrame.from_records([features])])

    df = df.set_index(["id"])

    return df
