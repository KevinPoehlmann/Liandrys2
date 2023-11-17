from bson.objectid import ObjectId as BsonObjectId
from bson.errors import InvalidId



class PydanticObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            BsonObjectId(str(v))
        except InvalidId:
            raise ValueError("Not a valid ObjectId")
        return str(v)
"""     
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string") """