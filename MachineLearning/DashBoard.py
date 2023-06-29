import pandas as pd
import numpy as np
from opensearchpy import OpenSearch
from dotenv import load_dotenv
import os
import warnings
from QueryBuilders import MatchQueryBuilder, MatchPlayerSubQueryBuilder, MatchTeamSubQueryBuilder
from datetime import datetime
from constantsQueues import queueConstants
import dash_bootstrap_components as dbc
import time
from PIL import Image
import json

warnings.filterwarnings('ignore')

load_dotenv()
CLUSTER_URL = 'https://localhost:9200'
USNAME = os.getenv('USERNM')
PASSWD = os.getenv('PASSWORD')

def get_os_client(cluster_url, username, password):
    client = OpenSearch(
        hosts=[cluster_url],
        http_auth=(username, password),
        verify_certs = False
    )
    return client

client = get_os_client(CLUSTER_URL,USNAME,PASSWD)

championFirstBlood = {
    "filter": {
        "term":{
            "info.participants.firstBloodKill": "true"
        }
    },
    "aggs":{
        "countResA":{
            "terms":{
                "field":"info.participants.championName.keyword",
                "size":40
            }
        }
    }
}

championPick = {
    "terms":{
        "field":"info.participants.championName.keyword",
        "size":40
    }
}


teamFirstBlood = {
    "filter": {
        "term":{
            "info.participants.firstBloodKill": "true"
        }
    },
    "aggs":{
        "countResB":{
            "terms":{
                "field":"info.participants.teamId",
                "size":20
            }
        }
    }
}


teamWins = {
    "filter": {
        "term":{
            "info.teams.win": "true"
        }
    },
    "aggs":{
        "countResC":{
            "terms":{
                "field":"info.teams.teamId",
            }
        }
    }   
}



avgBarons = {
    "terms":{
        "field":"info.teams.teamId"
    },
    "aggs":{
        "avgCount":{
            "extended_stats":{
                "field": "info.teams.objectives.baron.kills"
            }
        }
    } 
}


avgKills = {
    "terms":{
        "field":"info.teams.teamId"
    },
    "aggs":{
        "avgCount":{
            "extended_stats":{
                "field": "info.teams.objectives.champion.kills"
            }
        }
    } 
}

avgDragon = {
    "terms":{
        "field":"info.teams.teamId"
    },
    "aggs":{
        "avgCount":{
            "extended_stats":{
                "field": "info.teams.objectives.dragon.kills"
            }
        }
    } 
}

avgTower = {
    "terms":{
        "field":"info.teams.teamId"
    },
    "aggs":{
        "avgCount":{
            "extended_stats":{
                "field": "info.teams.objectives.tower.kills"
            }
        }
    } 
}

def avgDuration(dateAggs):
    dateAggs = dateAggs or "1q"

    avgDurationQ = {
        "date_histogram": {
            "field": "info.gameCreation",
            "calendar_interval": dateAggs
        },
        "aggs": {
            "avgCount": {
                "extended_stats": {
                    "field": "info.gameDuration"
                }
            }
        }
    }
    #print(avgDurationQ)
    return avgDurationQ




def total_gold_build(teams=None,win=None,qSize=10000):
    team_q = {"match_all":{}} if teams is None else {"terms":{"info.participants.teamId": teams}}
    win_q = {"match_all":{}} if win is None else {"term":{"info.participants.win": win}}

    total_gold = {
        "terms": {
            "field": "_id",
            "size": qSize
        },
        "aggs":{
            "players":{
                "nested": {
                    "path": "info.participants"
                },
                "aggs":{
                    "winner":{
                        "filter": win_q,
                        "aggs":{
                            "team":{
                                "filter": team_q,
                                "aggs":{
                                    "total_agg":{
                                        "sum": {
                                            "field": "info.participants.goldEarned"
                                        } 
                                    }                
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return total_gold

def total_exp_build(teams=None,win=None,qSize=10000):
    team_q = {"match_all":{}} if teams is None else {"terms":{"info.participants.teamId": teams}}
    win_q = {"match_all":{}} if win is None else {"term":{"info.participants.win": win}}

    total_exp = {
        "terms": {
            "field": "_id",
            "size": qSize
        },
        "aggs":{
            "players":{
                "nested": {
                    "path": "info.participants"
                },
                "aggs":{
                    "winner":{
                        "filter": win_q,
                        "aggs":{
                            "team":{
                                "filter": team_q,
                                "aggs":{
                                    "total_agg":{
                                        "sum": {
                                            "field": "info.participants.champExperience"
                                        } 
                                    }                
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return total_exp


def getQueryResBuckets(dictVal,starterPoint,keyOrder):
    result = {}
    for stackRef in dictVal[starterPoint]:
        keyVal = stackRef["key"] 
        for keyOrd in keyOrder:
            stackRef = stackRef[keyOrd]

        result[keyVal] = stackRef
    return result



def runQuery(client,teamWinner=None,teamId=None,playerWinner=None,playerTeamId=None,gameMode=None,qType=None,dateRange=None,platformId=None,qSize=10000,dateAggs=None):
    
    queryTeamBuilder = MatchTeamSubQueryBuilder()
    queryTeamBuilder.setWinner(teamWinner)
    queryTeamBuilder.setTeam(teamId)
    queryTeamBuilder.addQuery("teamWins",teamWins,["countResC"])
    queryTeamBuilder.addQuery("avgBarons",avgBarons,[])
    queryTeamBuilder.addQuery("avgKills",avgKills,[])
    queryTeamBuilder.addQuery("avgDragon",avgDragon,[])
    queryTeamBuilder.addQuery("avgTower",avgTower,[])

    queryPlayerBuilder = MatchPlayerSubQueryBuilder()
    queryPlayerBuilder.setWinner(playerWinner)
    queryPlayerBuilder.setTeam(playerTeamId)
    queryPlayerBuilder.addQuery("championFirstBlood",championFirstBlood,["countResA"])
    queryPlayerBuilder.addQuery("teamFirstBlood",teamFirstBlood,["countResB"])
    queryPlayerBuilder.addQuery("championPick",championPick,[])

    queryBuilder = MatchQueryBuilder(queryPlayerBuilder,queryTeamBuilder)
    queryBuilder.setGameMode(gameMode)
    queryBuilder.setQType(qType)
    queryBuilder.setDate(dateRange)
    queryBuilder.setPlatformId(platformId)
    queryBuilder.addQuery("avgDuration",avgDuration(dateAggs),[])
    queryBuilder.addQuery("total_gold",total_gold_build(teams=teamId,win=playerWinner,qSize=qSize),[])
    queryBuilder.addQuery("total_exp",total_exp_build(teams=teamId,win=playerWinner,qSize=qSize),[])
    aggregation_query = queryBuilder.buildQuery()

    #print(aggregation_query)
    response = client.search(index="matches", body=aggregation_query)
    result = queryBuilder.parseQueryResult(response)
    
    #print(result["total_gold"])


    finalVals = {x:getQueryResBuckets(result[x],"buckets",["doc_count"]) for x in result if not x.startswith("avg")}
    finalValsAvg = {x:getQueryResBuckets(result[x],"buckets",["avgCount","avg"]) for x in result if x.startswith("avg")}
    finalValsStd = {x + "_std":getQueryResBuckets(result[x],"buckets",["avgCount","std_deviation"]) for x in result if x.startswith("avg")}
    finalTotal = {x:getQueryResBuckets(result[x],"buckets",["players","winner","team","total_agg","value"]) for x in result if x.startswith("total_")}

    finalDict = finalVals | finalValsAvg | finalValsStd | finalTotal

    return finalDict


def getPandas(client,**queryArgs):
    pandasRes = {}
    dictVal = runQuery(client,**queryArgs)
    champs = []
    vals = []
    for x,y in dictVal['championFirstBlood'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['championFirstBlood'] = pd.DataFrame.from_dict({"Champion": champs, "Counts": vals})

    champs = []
    vals = []
    for x,y in dictVal['championPick'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['championPick'] = pd.DataFrame.from_dict({"Champion": champs, "Counts": vals})
    
    champs = []
    vals = []
    for x,y in dictVal['teamWins'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['teamWins'] = pd.DataFrame.from_dict({"Team Id": champs, "Counts": vals})
    
    champs = []
    vals = []
    for x,y in dictVal['teamFirstBlood'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['teamFirstBlood'] = pd.DataFrame.from_dict({"Team Id": champs, "Counts": vals})

    champs = []
    vals = []
    for x,y in dictVal['avgBarons'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['avgBarons'] = pd.DataFrame.from_dict({"Team Id": champs, "Average": vals})

    champs = []
    vals = []
    for x,y in dictVal['avgDragon'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['avgDragon'] = pd.DataFrame.from_dict({"Team Id": champs, "Average": vals})

    champs = []
    vals = []
    for x,y in dictVal['avgTower'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['avgTower'] = pd.DataFrame.from_dict({"Team Id": champs, "Average": vals})

    champs = []
    vals = []
    for x,y in dictVal['avgKills'].items():
        champs.append(x)
        vals.append(y)
    pandasRes['avgKills'] = pd.DataFrame.from_dict({"Team Id": champs, "Average": vals})

    champs = []
    vals = []
    stds = []
    for x,y in dictVal['avgDuration'].items():
        champs.append(datetime.utcfromtimestamp(int(x/1000)).strftime('%Y-%m-%d'))
        itsok = False
        y = y or 0


        if y < 5000:
            itsok = True

        y = y if itsok else y/1000
        y = y/60
        vals.append(y)
        z = dictVal['avgDuration_std'][x]
        z = z or 0
        z = z if itsok else z/1000
        z = z/60
        stds.append(z)
    pandasRes['avgDuration'] = pd.DataFrame.from_dict({"Date": champs, "Minutes": vals, "Std": stds})

    champs = []
    vals = []
    for x,y in dictVal["total_gold"].items():
        champs.append(x)
        vals.append(y)
    pandasRes['total_gold'] = pd.DataFrame.from_dict({"Match Id": champs, "Total": vals})

    champs = []
    vals = []
    for x,y in dictVal["total_exp"].items():
        champs.append(x)
        vals.append(y)
    pandasRes['total_exp'] = pd.DataFrame.from_dict({"Match Id": champs, "Total": vals})
    return pandasRes



def getMetadata(client):
    res = {}
    gameModes_q = {
        "aggs": {
            "match_counts": {
                "terms": {
                    "field": "info.gameMode.keyword",
                    "size": 10
                }
            }
        }
    }

    queues_q = {
        "aggs": {
            "match_counts": {
                "terms": {
                    "field": "info.queueId",
                    "size": 10
                }
            }
        }
    }

    platforms_q = {
        "aggs": {
            "match_counts": {
                "terms": {
                    "field": "info.platformId.keyword",
                    "size": 10
                }
            }
        }
    }
    teams_q = {
        "aggs": {
            "teams": {
                "nested": {
                    "path": "info.teams"
                },
                "aggs": {
                    "match_counts":{
                        "terms": {
                            "field": "info.teams.teamId",
                            "size": 10
                        }
                    }
                }
            }
        }
    }
    response = client.search(index="matches", body=gameModes_q)
    res["gamemodes"] = [x["key"].lower() for x in response["aggregations"]["match_counts"]["buckets"]]

    response = client.search(index="matches", body=queues_q)
    res["queues"] = [x["key"] for x in response["aggregations"]["match_counts"]["buckets"]]

    response = client.search(index="matches", body=platforms_q)
    res["platforms"] = [x["key"].lower() for x in response["aggregations"]["match_counts"]["buckets"]]

    response = client.search(index="matches", body=teams_q)
    res["teams"] = [x["key"] for x in response["aggregations"]["teams"]["match_counts"]["buckets"]]
    return res





##################################################################
##################################################################
##################################################################



# Import packages
from dash import Dash, html, dash_table, dcc, callback, Output, Input
import pandas as pd
import plotly.express as px
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

client = get_os_client(CLUSTER_URL,USNAME,PASSWD)


metaData = getMetadata(client)

# Incorporate data
df = getPandas(client)


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP],suppress_callback_exceptions=True)

# the style arguments for the sidebar. We use position:fixed and a fixed width
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "20%",
    "padding": "1%",
    "background-color": "#f3f3f3",
}

# the styles for the main content position it to the right of the sidebar and
# add some padding.
CONTENT_STYLE = {
    "margin-left": "20%",
}

sidebarMatchs = html.Div(
    [
        html.H2("Dashboard", className="display-4"),
        html.P(
            "Matches Analytics", className="lead"
        ),
        dbc.Nav(
            [
                html.Div(["Game Modes Selection",
                    dcc.Dropdown([x for x in metaData["gamemodes"]],
                        [],
                        id="gamemodes-selector",
                        multi=True,
                    ),
                ], style={"margin": "2%","margin-right": "3%"}),

                html.Div(["Queues Selection",
                    dcc.Dropdown([f"{x} - {[y for y in queueConstants if y['queueId'] == x][0]['description']}" for x in metaData["queues"]],
                        [],
                        id="queues-selector",
                        multi=True,
                    ),
                ], style={"margin": "2%","margin-right": "3%"}),

                
                html.Div(["Platforms Selection",
                    dcc.Dropdown([x for x in metaData["platforms"]],
                        [],
                        id="platforms-selector",
                        multi=True,
                    ),
                ], style={"margin": "2%","margin-right": "3%"}),

                html.Hr(),

                html.Div(["Date Range",
                    dcc.DatePickerRange(
                        display_format='YYYY-MM-DD',
                        clearable=True,
                        id="dateRange-selector",
                    )
                ], style={"margin": "2%","margin-right": "3%"}),

                html.Hr(),

                html.Div(["Date Aggregations",
                    dcc.Dropdown([{'label': html.Div(x, style={'font-size': 15, 'padding-left': 10}), 'value': y} for x,y in [("days","1d"),("weeks","1w"),("month", "1M"),("quarter","1q")]],
                        id="date-aggs-selector",
                    ),
                ], style={"margin": "2%","margin-right": "3%"}),

                

                html.Div(["Teams Display",
                    dcc.Checklist([{'label': html.Div(x, style={'font-size': 15, 'padding-left': 10}), 'value': x} for x in metaData["teams"]],
                                  [],
                                  id="teams-selector",
                                  inline=True,
                                  labelStyle = {'display': 'flex'}
                    ),
                ], style={"margin": "2%","margin-right": "3%"}),

                html.Hr(),

                html.Div(["Game State Display",
                    dcc.Checklist([{'label': html.Div("Win", style={'font-size': 15, 'padding-left': 10}), 'value': "Win"},
                                   {'label': html.Div("Loss", style={'font-size': 15, 'padding-left': 10}), 'value': "Loss"}],
                                  [],
                                  id="win-selector",
                                  inline=True,
                                  labelStyle = {'display': 'flex'}
                    ),
                ], style={"margin": "2%","margin-right": "3%"}),

                html.Hr(),

                html.Div(["Games Ammount (Histograms only)",
                    dcc.Slider(5000, 30000, 5000 , value=15000, id='slider-game-amm')
                ], style={"margin": "2%","margin-right": "3%"}),
            ],
            vertical=True,
            pills=True,
        ),
    ],
)

contentMatchs = html.Div([
    dbc.Row([
        dcc.Graph(figure={}, id='graph-placeholderB'),
    ]),    
    dmc.Grid([
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderC')
            ],style={"width":"50%"}),

            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderD')
            ],style={"width":"50%"}),
        ], style={"width":"100%","margin-left": "2%"}),
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholder')
            ],style={"width":"50%"}),
            
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderA')
            ],style={"width":"50%"}),
        ], style={"width":"100%","margin-left": "2%"}),
        
        dbc.Row([
            dbc.Col([
                    dcc.Graph(figure={}, id='graph-placeholderE')
            ],style={"width":"50%"}), 
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderF')
            ],style={"width":"50%"}),
        ], style={"width":"100%","margin-left": "2%"}),
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderG')
            ],style={"width":"50%"}),
            
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderH')
            ],style={"width":"50%"}),
        ], style={"width":"100%","margin-left": "2%"}),
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderI')
            ],style={"width":"50%"}),
            
            dbc.Col([
                dcc.Graph(figure={}, id='graph-placeholderJ')
            ],style={"width":"50%"}),
        ], style={"width":"100%","margin-left": "2%"}),
    ]),
],id="page-content")


corrEDA = html.Img(src=Image.open("corrEDA.png"),style={"width":"80%",})
pairsEDA = html.Img(src=Image.open("pairsEDA.png"),style={"width":"80%"})
plotsEDA = html.Img(src=Image.open("plotsEDA.png"),style={"width":"80%"})
tierEDA = html.Img(src=Image.open("tierEDA.png"),style={"width":"80%"})

contentEDA = html.Div([corrEDA,
    html.Hr(),
    pairsEDA,
    html.Hr(),
    plotsEDA,
    html.Hr(),
    tierEDA,
])


sidebarEDA = html.Div(
    [
        html.H2("EDA", className="display-4"),
        html.P(
            "Exploratory Data Analysis of the benchmarked DataFrame", className="lead"
        ),
    ]
)


modNames = ["XGBoost6","XGBoost10","SVM","RandForest","LR","KNN"]
modDisplay = ["XGBoost (depth 6)", "XGBoost (depth 10)","SVM","Random Forest","Logistic Regression","KNN"]
#modNames = ["SVM","RandForest","LR","KNN"]
#modDisplay = ["SVM","Random Forest","Logistic Regression","KNN"]

sidebarBenchmark = html.Div(
    [
        html.H2("Benchmarks", className="display-4"),
        html.P(
            "Benchmarks of each Machine learning Method", className="lead"
        ),
        html.Div(["Model Metrics",
            dcc.Dropdown([{'label': html.Div(x, style={'font-size': 15, 'padding-left': 10}), 'value': y} for x,y in zip(modDisplay,modNames)],
                value="SVM",id="models-selector",
            ),
        ], style={"margin": "2%","margin-right": "3%"}),
    ]
)



contentBenchmarks = html.Div([
    dmc.Grid([
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-Time-train')
            ],width=8),
            
            dbc.Col([
                dcc.Graph(figure={}, id='graph-TimeSVM-train')
            ],width=3),
        ],style={"width":"100%","margin-left": "2%","margin-top":"2%"}),
    ]),


    dbc.Row([
        dbc.Col([
            dcc.Graph(figure={}, id='graph-Time')
        ],width=8),
        
        dbc.Col([
            dcc.Graph(figure={}, id='graph-TimeSVM')
        ],width=3),
    ],style={"width":"100%","margin-left": "2%"}),

    dmc.Grid([
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-metricsA')
            ],style={"width":"25%"}),
            
            dbc.Col([
                dcc.Graph(figure={}, id='graph-metricsB')
            ],style={"width":"25%"}),
        
            dbc.Col([
                dcc.Graph(figure={}, id='graph-metricsC')
            ],style={"width":"25%"}),

            dbc.Col([
                dcc.Graph(figure={}, id='graph-metricsD')
            ],style={"width":"25%"}),

        ], style={"width":"90%","margin-left": "2%"}),
    ]),

    html.Hr(),
    dmc.Grid([
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure={}, id='graph-cpu')
            ],style={"width":"30%"}),
            
            dbc.Col([
                dcc.Graph(figure={}, id='graph-local')
            ],style={"width":"30%"}),
        
            dbc.Col([
                dcc.Graph(figure={}, id='graph-gpu')
            ],style={"width":"30%"}),  
        ], style={"width":"90%","margin-left": "2%"}),
    ]),
],id="page-content")


 

app.layout = html.Div([
    html.Div(id='sidebar-content',style=SIDEBAR_STYLE),
    html.Div([
        dcc.Tabs(id="tabs-example-graph", value='dash-tab', children=[
            dcc.Tab(label='Dashboard Matches', value='dash-tab'),
            dcc.Tab(label='EDA', value='eda-tab'),
            dcc.Tab(label='Benchmarks', value='bmk-tab'),
        ]),
        html.Div(id='tabs-content')
    ], style=CONTENT_STYLE)
])



@callback(
            Output('tabs-content', 'children'),
            Output('sidebar-content', 'children'),
            Input('tabs-example-graph', 'value'),
        )
def render_content(tab):
    if tab == 'eda-tab':
        return (html.Div([contentEDA]),sidebarEDA)
    elif tab == 'bmk-tab':
        return (html.Div([contentBenchmarks]),sidebarBenchmark)
    else:
        return (html.Div([contentMatchs]),sidebarMatchs)



# Add controls to build the interaction
@callback(
    Output(component_id='graph-Time-train', component_property='figure'),
    Output(component_id='graph-TimeSVM-train', component_property='figure'),
    Output(component_id='graph-Time', component_property='figure'),
    Output(component_id='graph-TimeSVM', component_property='figure'),
    Output(component_id='graph-metricsA', component_property='figure'),
    Output(component_id='graph-metricsB', component_property='figure'),
    Output(component_id='graph-metricsC', component_property='figure'),
    Output(component_id='graph-metricsD', component_property='figure'),
    Output(component_id='graph-cpu', component_property='figure'),
    Output(component_id='graph-local', component_property='figure'),
    Output(component_id='graph-gpu', component_property='figure'),
    Input("models-selector","value"),
)
def update_model_bench(modNameInpt):
    
    platforms = ["cpu","local_cpu","gpu"]
    metrics = ["precision","recall","f1-score"]
    ranks = ["IRON","BRONZE","SILVER","GOLD","PLATINUM","DIAMOND","MASTER","GRANDMASTER","CHALLENGER"]
    df = pd.DataFrame(columns=["model","platform","train_time","predict_time","accuracy"] + metrics)
   
    rankMetrics = pd.DataFrame(columns=["model","platform", "value", "metric","rank"])
    modNamesDict = {x:y for x,y in zip(modNames,modDisplay)}
    for modName in modNames:
        for platform in platforms:
            f = open(os.path.join("JSONS",f'{modName}_{platform}.json'))
            data = json.load(f)
            values = [modNamesDict[modName], platform, data["train_time"]["stop"] - data["train_time"]["start"], data["predict_time"]["stop"] - data["predict_time"]["start"], data["accuracy"]]
            values += [data["metrics"]["weighted avg"][x] for x in metrics]
            
            for rank in ranks:
                for x in metrics:
                    rankVals = [modNamesDict[modName], platform, data["metrics"][rank][x], x, rank]
                    rankMetrics.loc[len(rankMetrics.index)] = rankVals
            
            df.loc[len(df.index)] = values

    df_no_SVM = df[df["model"] != "SVM"]
    df_only_SVM = df[df["model"] == "SVM"]
    
    figs = {}
    figTimes = {}
    figs["times"] = figTimes
    for timeType in ["train_time","predict_time"]:
        figTimes[timeType] = []
        typeTimeVal = "Training" if timeType == "train_time" else "Predicting"
        figTimes[timeType].append(px.histogram(df_no_SVM, x="model", y=timeType,
                     color='platform', barmode='group',
                     histfunc='avg',
                      labels={
                        timeType: f"{typeTimeVal} Time (seconds)",
                        "model": "Model",
                        "platform": "Platform"
                        },
                     title=f"{typeTimeVal} Time Chart",
                     height=400).update_layout(yaxis_title=f"{typeTimeVal} Time (seconds)"))
        figTimes[timeType].append(px.histogram(df_only_SVM, x="model", y=timeType,
                     color='platform', barmode='group',
                      labels={
                        timeType: f"{typeTimeVal} Time (seconds)",
                        "model": "Model",
                        "platform": "Platform"
                        },
                     histfunc='avg',
                     title=f"{typeTimeVal} Time Chart for SVM",
                     height=400).update_layout(yaxis_title=f"{typeTimeVal} Time (seconds)"))
    figMetrics = []
    figs["metrics"] = figMetrics
    for metric in metrics + ["accuracy"]:
        figMetrics.append(px.histogram(df, x="model", y=metric,
                                color='platform', barmode='group',
                                histfunc='avg',
                                labels={
                                     metric: metric,
                                     "model": "Model",
                                     "platform": "Platform"
                                },
                                title=f"{metric[0].upper()}{metric[1:]}",
                                height=400).update_layout(yaxis_title="value"))
    figRanks = {}
    figs["ranks"] = figRanks
    for modName in modNames:
        figRanks[modName] = []
        for platform in platforms:
            df_aux = rankMetrics[rankMetrics["platform"] == platform]
            df_val = df_aux[df_aux["model"] == modNamesDict[modName]]
            figRanks[modName].append(px.histogram(df_val, x="metric", y="value",
                                            color='rank', barmode='group',
                                            histfunc='avg',
                                            title=f"{modNamesDict[modName]} @ {platform}",
                                            labels={
                                                "metric": "Metric",
                                                "value": "",
                                                "rank": "Ranks"
                                            },
                                            height=400).update_layout(yaxis_title=""))

    return *figTimes["train_time"],*figTimes["predict_time"],*figMetrics,*figRanks[modNameInpt]







# Add controls to build the interaction
@callback(
    Output(component_id='graph-placeholder', component_property='figure'),
    Output(component_id='graph-placeholderA', component_property='figure'),
    Output(component_id='graph-placeholderB', component_property='figure'),
    Output(component_id='graph-placeholderC', component_property='figure'),
    Output(component_id='graph-placeholderD', component_property='figure'),
    Output(component_id='graph-placeholderE', component_property='figure'),
    Output(component_id='graph-placeholderF', component_property='figure'),
    Output(component_id='graph-placeholderG', component_property='figure'),
    Output(component_id='graph-placeholderH', component_property='figure'),
    Output(component_id='graph-placeholderI', component_property='figure'),
    Output(component_id='graph-placeholderJ', component_property='figure'),
    Input("gamemodes-selector","value"),
    Input("queues-selector","value"),
    Input("platforms-selector","value"),
    Input("teams-selector","value"),
    Input("win-selector","value"),
    Input('slider-game-amm',"value"),
    Input("date-aggs-selector","value"),
    Input("dateRange-selector","start_date"),
    Input("dateRange-selector","end_date"),
)
def update_graph(gamemodes,queues,platforms,teams,win,gameAmm,dateAggs,*dateRange):
    gamemodes = gamemodes if len(gamemodes) > 0 else None
    queues = queues if len(queues) > 0 else None
    platforms = platforms if len(platforms) > 0 else None
    teams = teams if len(teams) > 0 else None
    win = win if len(win) > 0 and len(win) < 2 else None
    dateAggs = dateAggs or "1q"

    dateRange = dateRange if dateRange[0] is not None and dateRange[1] is not None else None

    if queues is not None:
        queues = [x.split(" - ")[0] for x in queues]

    if win is not None and "Win" in win:
        win = True
    elif win is not None:
        win = False

    if dateRange is not None:
        timestampMin = time.mktime(datetime.strptime(dateRange[0],"%Y-%m-%d").timetuple())*1000
        timestampMax = time.mktime(datetime.strptime(dateRange[1],"%Y-%m-%d").timetuple())*1000
        dateRange = (timestampMin,timestampMax)
    #print("bbbbbb",dateRange)
    #print("gamemodes",gamemodes)        
    #print("queues",queues)        
    #print("platforms",platforms)        
    #print("teams",teams)        
    #print("win",win)        
    #print("dateRange",dateRange)
    #print("#####################################################################")

    df = getPandas(client,teamWinner=win,teamId=teams,playerWinner=win,playerTeamId=teams,gameMode=gamemodes,qType=queues,dateRange=dateRange,platformId=platforms,qSize=gameAmm,dateAggs=dateAggs)
    fig = px.histogram(df["championFirstBlood"], x=df["championFirstBlood"].columns[0], y = df["championFirstBlood"].columns[1],  title="championFirstBlood")
    figA = px.histogram(df["championPick"],x= df["championPick"].columns[0], y = df["championPick"].columns[1], title="championPick")
    figB = px.pie(df["teamWins"], values= df["teamWins"].columns[1], names=df["teamWins"].columns[0], hole=.6, title="Wins")
    figC = px.pie(df["teamFirstBlood"], values= df["teamFirstBlood"].columns[1], names=df["teamFirstBlood"].columns[0], hole=.6, title="First Blood")
    figD = [px.pie(df[x], values= df[x].columns[1], names=df[x].columns[0], title="Average " + x[3:]) for x in ["avgBarons","avgDragon","avgTower","avgKills"]]
    figE = go.Figure([
            go.Scatter(
                name='Average',
                x=df['avgDuration']['Date'],
                y=df['avgDuration']['Minutes'],
                mode='lines+markers',
                line=dict(color='rgb(31, 119, 180)'),
            ),
            go.Scatter(
                name='Upper Bound',
                x=df['avgDuration']['Date'],
                y=df['avgDuration']["Minutes"] + df['avgDuration']['Std'],
                mode='lines',
                marker=dict(color="#444"),
                line=dict(width=0),
                showlegend=False
            ),
            go.Scatter(
                name='Lower Bound',
                x=df['avgDuration']['Date'],
                y=df['avgDuration']["Minutes"] - df['avgDuration']['Std'],
                marker=dict(color="#444"),
                line=dict(width=0),
                mode='lines',
                fillcolor='rgba(68, 68, 68, 0.3)',
                fill='tonexty',
                showlegend=False
            )
        ])
    figE.update_layout(
        yaxis_title='Average Duration (Minutes)',
        title='Average Match Duration',
        hovermode="x"
    )

    figF = px.histogram(df["total_gold"], x=df["total_gold"].columns[1], title="Total Gold")
    figG = px.histogram(df["total_exp"], x=df["total_exp"].columns[1],  title="Total Experience")
    res = (fig,figA, figE, figF, figG, figB, figC, *figD)
    return res

# Run the App
if __name__ == '__main__':
    app.run_server(debug=True)


