from sqladmin import Admin, ModelView
from db.model.character import Character
from db.model.user_store import UserCharacter
from db.model.user import User
## logger
from loguru import logger

## Admin View Class
class CharacterAdmin(ModelView, model=Character):
    # table list column
    column_list = [Character.id, Character.type_code, Character.idx, Character.name, Character.created_at]
    # search column
    # column_searchable_list = [Character.name, Character.desc]
    # sort column
    # column_sortable_list = [Character.id, Character.name]
    # filter column
    # column_filters = [Character.type_code]
    # relation (need to check whether to include relation because of complex)
    # column_exclude_list = [Character.users] 
    ###### form select box : Enum field
    # form_args = {
    #     "type_code": {"label": "타입 코드"}
    # }
class UserCharacterAdmin(ModelView, model=UserCharacter):
    column_list = [UserCharacter.user_id, UserCharacter.character_id]

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username]
        
def start_admin(app, engine):
    admin = Admin(app, engine, base_url="/klingo_admin")
    logger.info("Admin Page Start")
    admin.add_view(UserAdmin)
    admin.add_view(CharacterAdmin)
    admin.add_view(UserCharacterAdmin)