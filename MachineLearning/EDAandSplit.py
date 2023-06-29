import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os
import seaborn as sb
from opensearchpy import OpenSearch
import warnings
from sklearn.model_selection import train_test_split

df = pd.read_csv(os.path.join("csv","aggPlayers.csv"),index_col=0)

n_rows=10
n_cols=4

df_numericals = df.drop(["Summoner Id","Tier","roleADC","roleSUP","roleJNG","roleTOP","roleMID"],axis=1)


PLOTS = False

if PLOTS:
    fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(40,30),constrained_layout=True)
    for i, column in enumerate(df_numericals.columns):
        sb.histplot(df_numericals[column],ax=axes[i//n_cols,i%n_cols],kde=True)
    plt.savefig("plotsEDA", bbox_inches='tight')

    print("ok")

    plt.figure(figsize=(30, 20))
    sb.heatmap(df_numericals.corr(),annot=True, linewidth=.5, cmap="crest");
    plt.savefig("corrEDA", bbox_inches='tight')

    print("ok")

    df_numericals = df.drop(["Summoner Id","roleADC","roleSUP","roleJNG","roleTOP","roleMID"],axis=1)
    df_numericals = df.sample(50000)[["Tier","totalMinionsKilledAvg","timePlayingAvg","killingSpreesAvg","visionScoreAvg","totalDamageDealtToChampionsAvg","damageDealtToBuildingsAvg","damageDealtToObjectivesAvg","totalDamageTakenAvg",]]
    plt.figure(figsize=(20, 10))
    sb.pairplot(df_numericals, hue="Tier",palette="coolwarm",corner=True)
    plt.savefig("pairsEDA")
    print("ok")

    plt.figure(figsize=(30, 20))
    ax = df['Tier'].value_counts().plot(kind='bar',
                                        figsize=(14,8),
                                        title="Ranks Counts")
    plt.savefig("tierEDA", bbox_inches='tight')


#split and save csvs

dfBase = df.drop(["Summoner Id"],axis=1)
y = df.pop("Tier")

X_train, X_test, y_train, y_test = train_test_split(dfBase,y, test_size=0.3, random_state=42)
X_train["Tier"] = y_train
X_test["Tier"] = y_test


X_train.to_csv(os.path.join("csv","trainSplit.csv"))
X_test.to_csv(os.path.join("csv","testSplit.csv"))