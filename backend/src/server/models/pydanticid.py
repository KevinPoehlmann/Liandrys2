from bson.objectid import ObjectId as BsonObjectId



class PydanticObjectId(BsonObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, BsonObjectId):
            raise TypeError("Object ID needed")
        return str(v)
"""     
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string") """