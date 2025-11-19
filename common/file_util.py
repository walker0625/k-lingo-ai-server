## 받은 파일 저장
import os, shutil
from datetime import datetime
from typing import Literal
from fastapi import UploadFile


def make_temp_file_info(dir:Literal["input","output"], source_file:str):
    static_dir = os.environ["STATIC_PATH"]
    _temp_file = f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{source_file}'
    file_name = os.path.join(f'{static_dir}/{dir}',_temp_file)
    return {"path":file_name,"link":f"/static/input/{_temp_file}"}

def save_input_file_to_temp(file: UploadFile):
    """
        api를 통해 들어올 UploadFile을 /static/input 폴더에 저장하고 해당 정보 리턴
        return : {"path":저장한 파일명, "link":저장한 파일 링크}
    """
    if not file or not file.filename:
        return None
    file_info = make_temp_file_info("input",file.filename)
    # 파일 저장
    with open(file_info["path"], "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_info