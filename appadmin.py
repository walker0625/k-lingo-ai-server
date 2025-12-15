import os
from dotenv import load_dotenv
import uvicorn
from datetime import datetime
from enum import Enum
from typing import Optional, List

from fastapi import FastAPI
from sqlmodel import Field, Relationship, SQLModel, create_engine
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import selectinload
from sqladmin import Admin, ModelView
from db.model.character import Character, CharacterType
from db.model.user import User
from db.model.user_store import UserCharacter

load_dotenv()
db_url = os.environ['DATABASE_URL']

engine = create_engine(db_url, echo=True)
app = FastAPI()
admin = Admin(app, engine)

# ModelView class
class CharacterAdmin(ModelView, model=Character):
    column_list = [Character.id, Character.type_code,
                   Character.idx, Character.name, Character.created_at]
    # column_searchable_list = [Character.name, Character.desc]
    # column_sortable_list = [Character.id, Character.created_at]
    # column_filters = [Character.type_code]
    # UserCharacter와의 관계 필드는 기본적으로 표시하지 않습니다. (복잡도 때문)
    # column_exclude_list = [Character.users] 
    # Enum 타입 필드의 편집/생성 폼에서 셀렉트 박스를 표시
    # form_args = {
    #     "type_code": {"label": "타입 코드"}
    # }
def user_fomatters(model : UserCharacter, attribute) -> str:
    if attribute == 'user':
        return model.user.username if model.user else "Undefined"
    if attribute == 'character':
        return model.character.name if model.character else "Undefined"
    return "Undefined"

class UserCharacterAdmin(ModelView, model=UserCharacter):
    column_list = [
        UserCharacter.user_id, 
        UserCharacter.user,
        UserCharacter.character_id,
        UserCharacter.character,
        UserCharacter.created_at,
        UserCharacter.updated_at
    ]
    column_details_list = [
        UserCharacter.id, 
        UserCharacter.user, 
        UserCharacter.character, 
        UserCharacter.desc, 
    ]
    column_labels = {
            UserCharacter.user: "username",
            UserCharacter.character: "character name",
    }
    column_extra_options = {
        "user": {"column_loader": selectinload},
        "character": {"column_loader": selectinload},
    }
    column_formatters = {
        "user": lambda m,a : user_fomatters(m,a),
        "character": lambda m, a: user_fomatters(m,a),
    }
    column_formatters_detail = {
        "user": lambda m,a : user_fomatters(m,a),
        "character": lambda m, a: user_fomatters(m,a),
    }

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username]
        
# Admin Instance
admin.add_view(UserAdmin)
admin.add_view(CharacterAdmin)
admin.add_view(UserCharacterAdmin)

# 기본 FastAPI 라우트
@app.get("/")
def home():
    return {"message": "Welcome to the API. Go to /admin for the management page."}

if __name__ == "__main__":
    # Render는 PORT 환경변수를 제공
    port = int(os.environ.get("PORT", 8100))
    uvicorn.run(app, host="0.0.0.0", port=port)#, reload=True if os.environ['APP_MODE'] == "0" else False)
    print("****** end server")