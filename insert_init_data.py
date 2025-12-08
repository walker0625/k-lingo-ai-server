import requests
# import json
import pandas as pd
from db.model.interview import InterviewCreate
# from pydantic import BaseModel
BASE_URL = "http://localhost:8104/"
# BASE_URL = "http://100.100.53.32:8104/"

## user 데이터 생성
def user_data():
    api = f"{BASE_URL}/users/register"
    bodies = [{
        "username": "klingo01",
        "fullname": "klingo",
        "password": "klingo"
    },{
        "username": "klingo02",
        "fullname": "klingo",
        "password": "klingo"
    },{
        "username": "klingo03",
        "fullname": "klingo",
        "password": "klingo"
    }]
    for body in bodies:
        print(body)
        response = requests.post(api, json=body)
        print(response.json())
    return "ok"
## 토큰 생성
def login():
    api = f"{BASE_URL}/users/token"
    body = {
        "username":"klingo01",
        "password":"klingo"
    }
    response = requests.post(api, data=body)
    return response.json()["access_token"]
def insert_interview(id, item):
    ## 인터뷰 데이터 입력
    api = f"{BASE_URL}/interview/post"
    response = requests.post(api, data=item.model_dump_json())
    print(response.status_code)
    if response.status_code != 201:
        print(id,response.json())


print("********** start **********")
## User
user_data()
## Interview Data
for interview_file in ["./masterdata/InterviewQuestion01.csv","./masterdata/InterviewQuestion02.csv"]:
    df = pd.read_csv(interview_file)
    df.columns = ["type_code","id","eng","kor","eng_key","kor_key"]
    ## interview list
    interview_list = []
    for i in range(len(df)):
        interview_list.append(InterviewCreate(**df.iloc[i].to_dict()))
    interview_list[:3]
    ## 데이터 입력 처리
    for i,item in enumerate(interview_list):
        insert_interview(df.loc[i,'id'],item)
print("********** end **********")