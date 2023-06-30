import time
import json
import cudf
from cuml import SVC,LogisticRegression
from cuml.ensemble import RandomForestClassifier
from cuml.neighbors import KNeighborsClassifier
from cuml.preprocessing import StandardScaler
from cuml.preprocessing.LabelEncoder import LabelEncoder
from sklearn.metrics import accuracy_score,classification_report
from xgboost import XGBClassifier

XTrain = cudf.read_csv("trainSplit.csv",index_col=0)
XTest = cudf.read_csv("testSplit.csv",index_col=0)

yTrain = XTrain.pop("Tier")
yTest = XTest.pop("Tier")

standard_scaler = StandardScaler()
XTrain = standard_scaler.fit_transform(XTrain)
XTest = standard_scaler.transform(XTest)

label_encoder = LabelEncoder()
label_encoder.fit(yTrain)
yTrain = label_encoder.transform(yTrain.to_numpy())
yTest = label_encoder.transform(yTest.to_numpy())



values = {}
MODELS = [("XGBoost6",XGBClassifier(seed=42, tree_method='gpu_hist')), ("XGBoost10",XGBClassifier(seed=42, max_depth=10, tree_method='gpu_hist')),("SVM",SVC(class_weight="balanced",random_state=42)),("RandForest",RandomForestClassifier(random_state=42)),
          ("KNN",KNeighborsClassifier()),("LR",LogisticRegression(penalty="none",class_weight="balanced",max_iter=1000,linesearch_max_iter=1000))]


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

    yPred = model.predict(XTest)
    
    yPred = yPred.to_numpy() if not name.startswith("XGBoost") else yPred
    
    values["metrics"] = classification_report(yTest.to_numpy(), yPred, output_dict=True,target_names=label_encoder.classes_, labels=list(range(9)))
    values["accuracy"] = accuracy_score(yTest.to_numpy(), yPred)

    file_path = f"{name}_gpu.json"
    with open(file_path, "w") as json_file:
        json.dump(values, json_file)