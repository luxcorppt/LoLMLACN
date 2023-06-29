import time
import json
import pandas as pd
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score,classification_report
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn import preprocessing
from xgboost import XGBClassifier


values = {}
XTrain = pd.read_csv("trainSplit.csv",index_col=0)
XTest = pd.read_csv("testSplit.csv",index_col=0)

yTrain = XTrain.pop("Tier")
yTest = XTest.pop("Tier")

standard_scaler = StandardScaler()
XTrain = standard_scaler.fit_transform(XTrain)
XTest = standard_scaler.transform(XTest)


label_encoder = preprocessing.LabelEncoder()

label_encoder.fit(yTrain)
yTrain = label_encoder.transform(yTrain)
yTest = label_encoder.transform(yTest)


MODELS = [("XGBoost6",XGBClassifier(seed=42)),("XGBoost10",XGBClassifier(seed=42, max_depth=10)), ("SVM",SVC(class_weight="balanced",random_state=42)),("RandForest",RandomForestClassifier(class_weight="balanced", n_jobs=-1,random_state=42)),
          ("KNN",KNeighborsClassifier(n_jobs=-1)),("LR",LogisticRegression(class_weight="balanced",penalty=None,n_jobs=-1,max_iter=1000))]



#MODELS = [("LR",LogisticRegression(class_weight="balanced",penalty=None,n_jobs=-1,max_iter=1000))]

for name,modelObj in MODELS:
    print(name)
    model = modelObj

    start = time.time()
    model.fit(XTrain, yTrain)
    stop = time.time()


    values["train_time"] = {"start":start,"stop":stop}
    
    start = time.time()
    yPred = model.predict(XTest)
    stop = time.time()    
    
    values["predict_time"] = {"start":start,"stop":stop}
    values["metrics"] = classification_report(yTest, yPred, output_dict=True,target_names=label_encoder.classes_, labels=list(range(9)))
    values["accuracy"] = accuracy_score(yTest, yPred)

    file_path = f"{name}_cpu.json"
    with open(file_path, "w") as json_file:
        json.dump(values, json_file)