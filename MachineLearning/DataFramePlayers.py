import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import opensearch_py_ml as oml
from opensearchpy import OpenSearch
from dotenv import load_dotenv
import os
import warnings
from tqdm import tqdm

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

index_name = 'ranks'
field_name = 'summonerId'
query = {
    "query": {
        "bool":{
            "must":{
                "match": {
                    "queueType": "ranked_solo_5x5"
                }             
            }
        }
    },
    "size": 1000  # Set the desired batch size, e.g., 1000
}

response = client.search(index=index_name, body=query, scroll='1m')

sumId = []
rankVals = []
tierVals = []
winsVals = []
lossVals = []

sumId += [hit['_source']['summonerId'] for hit in response['hits']['hits']]
tierVals += [hit['_source']["tier"] for hit in response['hits']['hits']]
rankVals += [hit['_source']["rank"] for hit in response['hits']['hits']]
winsVals += [hit['_source']["wins"] for hit in response['hits']['hits']]
lossVals += [hit['_source']["losses"] for hit in response['hits']['hits']]


scroll_id = response['_scroll_id']
while True:
    response = client.scroll(scroll_id=scroll_id, scroll='1m')
    hits = response['hits']['hits']
    
    if not hits:
        break

    sumId += [hit['_source']['summonerId'] for hit in response['hits']['hits']]
    tierVals += [hit['_source']["tier"] for hit in response['hits']['hits']]
    rankVals += [hit['_source']["rank"] for hit in response['hits']['hits']]
    winsVals += [hit['_source']["wins"] for hit in response['hits']['hits']]
    lossVals += [hit['_source']["losses"] for hit in response['hits']['hits']]
    
    scroll_id = response['_scroll_id']



newCV = pd.DataFrame.from_dict({"Summoner Id": sumId, "Tier": tierVals, "Rank":rankVals, "Wins":winsVals, "Loss": lossVals})


def agg_player_performance_query(summonerID, tier, wins, loss, totalGamesNormalizer):
    query = {
        "query":{
            "bool":{
                "must":[
                    {"match": { "info.queueId": 420}},
                    {
                        "nested":{
                          "path": "info.participants",
                            "query": {
                                "bool": {
                                  "must": [
                                    {"match": { "info.participants.summonerId": summonerID}},
                                  ]
                                }
                            },
                        },
                    }
                ]
            }
        },
        "aggs":{
            "players": {
                "nested": {
                    "path": "info.participants"
                },
                "aggs":{
                    "single_player": {
                       "filter": {
                            "term":{
                                "info.participants.summonerId.keyword": summonerID
                            }
                        },
                        "aggs":{
                            #KDA        
                            "killsAvg":{"avg":{"field":"info.participants.kills"}},
                            "deathsAvg":{"avg":{"field":"info.participants.deaths"}},
                            "assistsAvg":{"avg":{"field":"info.participants.assists"}},
                            
                            #ChampionStats
                            "champExperienceAvg":{"avg":{"field":"info.participants.champExperience"}},
                            "damageSelfMitigatedAvg":{"avg":{"field":"info.participants.damageSelfMitigated"}},
                            "goldEarnedAvg":{"avg":{"field":"info.participants.goldEarned"}},
                            "totalDamageDealtAvg": {"avg":{"field":"info.participants.totalDamageDealt"}},
                            "totalDamageDealtToChampionsAvg": {"avg":{"field":"info.participants.totalDamageDealtToChampions"}},
                            "totalDamageShieldedOnTeammatesAvg": {"avg":{"field":"info.participants.totalDamageShieldedOnTeammates"}},
                            "totalDamageTakenAvg": {"avg":{"field":"info.participants.totalDamageTaken"}},
                            "totalHealAvg": {"avg":{"field":"info.participants.totalHeal"}},
                            "totalMinionsKilledAvg": {"avg":{"field":"info.participants.totalMinionsKilled"}},
                            "totalTimeSpentDeadAvg": {"avg":{"field":"info.participants.totalTimeSpentDead"}},
                            "totalUnitsHealedAvg": {"avg":{"field":"info.participants.totalUnitsHealed"}},
                            "visionScoreAvg": {"avg":{"field":"info.participants.visionScore"}},

                            #Objectives
                            "baronKillsAvg": {"avg":{"field":"info.participants.baronKills"}},
                            "dragonKillsAvg":{"avg":{"field":"info.participants.dragonKills"}},
                            "damageDealtToObjectivesAvg":{"avg":{"field":"info.participants.damageDealtToObjectives"}},
                            "damageDealtToBuildingsAvg":{"avg":{"field":"info.participants.damageDealtToBuildings"}},
                            "firstBloodAvg":{"terms":{"field":"info.participants.firstBloodKill"}},
                            "firstBloodAssistAvg":{"terms":{"field":"info.participants.firstBloodAssist"}},
                            "firstTowerAssistAvg": {"terms":{"field":"info.participants.firstTowerAssist"}},
                            "firstTowerKillAvg": {"terms":{"field":"info.participants.firstTowerKill"}},
                            "nexusKillsAvg": {"avg":{"field":"info.participants.nexusKills"}},
                            "nexusTakedownsAvg": {"avg":{"field":"info.participants.nexusTakedowns"}},
                            "inhibitorKillsAvg": {"avg":{"field":"info.participants.inhibitorKills"}},
                            "inhibitorTakedownsAvg": {"avg":{"field":"info.participants.inhibitorTakedowns"}},
                            "killingSpreesAvg": {"avg":{"field":"info.participants.killingSprees"}},
                            "largestKillingSpreeAvg": {"avg":{"field":"info.participants.largestKillingSpree"}},
                            "totalAllyJungleMinionsKilledAvg": {"avg":{"field":"info.participants.totalAllyJungleMinionsKilled"}},
                            "totalEnemyJungleMinionsKilledAvg": {"avg":{"field":"info.participants.totalEnemyJungleMinionsKilled"}},

                            #Metagame
                            "earlySurrendersAvg":{"terms":{"field":"info.participants.gameEndedInEarlySurrender"}},
                            "surrendersAvg":{"terms":{"field":"info.participants.gameEndedInSurrender"}},
                            "roleCounts":{"terms":{"field":"info.participants.individualPosition.keyword"}},
                            "timePlayingAvg":{"avg":{"field":"info.participants.timePlayed"}},
                            "baitPingsAvg": {"avg":{"field":"info.participants.baitPings"}},
                            "enemyMissingPingsAvg": {"avg":{"field":"info.participants.enemyMissingPings"}},
                            "basicPingsAvg": {"avg":{"field":"info.participants.basicPings"}},
                        }
                    },
                }
            },
            "Ranked Count":{
                "terms":{
                    "field":"info.gameMode.keyword",
                    "size":20
                }    
            },
        }
    }


    response = client.search(index="matches", body=query)

    values = [summonerID, tier, wins/(wins+loss),(wins+loss)/totalGamesNormalizer]

    avgs = ["killsAvg","deathsAvg","assistsAvg","champExperienceAvg","damageSelfMitigatedAvg","goldEarnedAvg","totalDamageDealtAvg","totalDamageDealtToChampionsAvg",
            "totalDamageShieldedOnTeammatesAvg","totalDamageTakenAvg","totalHealAvg","totalMinionsKilledAvg","totalTimeSpentDeadAvg","totalUnitsHealedAvg","visionScoreAvg",
            "baronKillsAvg","dragonKillsAvg","damageDealtToObjectivesAvg","damageDealtToBuildingsAvg","nexusKillsAvg","nexusTakedownsAvg","inhibitorKillsAvg","inhibitorTakedownsAvg",
            "killingSpreesAvg","largestKillingSpreeAvg","totalAllyJungleMinionsKilledAvg","totalEnemyJungleMinionsKilledAvg","timePlayingAvg","baitPingsAvg","enemyMissingPingsAvg","basicPingsAvg"]
    
    bools = ["firstBloodAvg","firstBloodAssistAvg","firstTowerAssistAvg","firstTowerKillAvg","earlySurrendersAvg","surrendersAvg"]
    
    counts = ["roleCounts"]

    totalMatchesAux = sum([x["doc_count"] for x in response["aggregations"]["Ranked Count"]["buckets"]])
    totalMatches = totalMatchesAux if totalMatchesAux > 0 else 1 

    for avgKey in avgs:
        value = response["aggregations"]["players"]["single_player"][avgKey]["value"]
        value = value if value is not None and value != "None" else 0
        values.append(value)

    for boolKey in bools:
        value = [x["doc_count"] for x in response["aggregations"]["players"]["single_player"][boolKey]["buckets"] if x["key"] == 1]
        value = value[0] if len(value) else 0
        value /= totalMatches
        values.append(value)

    supCount = [x["doc_count"] for x in response["aggregations"]["players"]["single_player"]["roleCounts"]["buckets"] if x["key"] == "UTILITY"]
    adcCount = [x["doc_count"] for x in response["aggregations"]["players"]["single_player"]["roleCounts"]["buckets"] if x["key"] == "BOTTOM"]
    midCount = [x["doc_count"] for x in response["aggregations"]["players"]["single_player"]["roleCounts"]["buckets"] if x["key"] == "MIDDLE"]
    topCount = [x["doc_count"] for x in response["aggregations"]["players"]["single_player"]["roleCounts"]["buckets"] if x["key"] == "TOP"]
    jngCount = [x["doc_count"] for x in response["aggregations"]["players"]["single_player"]["roleCounts"]["buckets"] if x["key"] == "JUNGLE"]

    supCount = supCount[0] if len(supCount) else 0
    adcCount = adcCount[0] if len(adcCount) else 0
    midCount = midCount[0] if len(midCount) else 0
    topCount = topCount[0] if len(topCount) else 0
    jngCount = jngCount[0] if len(jngCount) else 0

    supCount /= totalMatches
    adcCount /= totalMatches
    midCount /= totalMatches
    topCount /= totalMatches
    jngCount /= totalMatches

    values.extend([supCount,adcCount,midCount,topCount,jngCount])

    return totalMatchesAux,values




df = pd.DataFrame(columns=["Summoner Id", "Tier", "WinRate","TotalGames",
    "killsAvg","deathsAvg","assistsAvg","champExperienceAvg","damageSelfMitigatedAvg","goldEarnedAvg","totalDamageDealtAvg","totalDamageDealtToChampionsAvg",
    "totalDamageShieldedOnTeammatesAvg","totalDamageTakenAvg","totalHealAvg","totalMinionsKilledAvg","totalTimeSpentDeadAvg","totalUnitsHealedAvg","visionScoreAvg",
    "baronKillsAvg","dragonKillsAvg","damageDealtToObjectivesAvg","damageDealtToBuildingsAvg","nexusKillsAvg","nexusTakedownsAvg","inhibitorKillsAvg","inhibitorTakedownsAvg",
    "killingSpreesAvg","largestKillingSpreeAvg","totalAllyJungleMinionsKilledAvg","totalEnemyJungleMinionsKilledAvg","timePlayingAvg","baitPingsAvg","enemyMissingPingsAvg","basicPingsAvg",
    "firstBloodAvg","firstBloodAssistAvg","firstTowerAssistAvg","firstTowerKillAvg","earlySurrendersAvg","surrendersAvg",
    "roleSUP", "roleADC", "roleMID", "roleTOP", "roleJNG"
    ])


for ind in tqdm(newCV.index):
    lin = newCV.loc[ind]

    totalMatches,values = agg_player_performance_query(lin["Summoner Id"],lin["Tier"],lin["Wins"],lin["Loss"],2000)

    if totalMatches > 0: 
        df.loc[len(df.index)] = values

df.to_csv(os.path.join("csv","aggPlayers.csv"))


