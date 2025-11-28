import os
from pymilvus import(
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    db
)
from sentence_transformers import SentenceTransformer
## logger
from loguru import logger
logger.info("MILVUS SETTING")

# Milvus connection
MILVUS_HOST=os.environ["MILVUS_HOST"]
MILVUS_PORT=os.environ["MILVUS_PORT"]
MILVUS_DATABASE=os.environ["MILVUS_DATABASE"]
EMBEDDING_DIM = int(os.environ["EMBEDDING_DIM"])
COLLECTION_NAME = "text_collection"
logger.info(f"{MILVUS_HOST}, {MILVUS_PORT}, {MILVUS_DATABASE}, {EMBEDDING_DIM}")

# embedding model : 384 dim
embedding_model : SentenceTransformer | None = None
# logger.info("EMBEDDING MODEL : all-MiniLM-L6-v2")
# embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
vector_collection: Collection | None = None

def set_connection():
    global embedding_model, vector_collection
    logger.info("EMBEDDING MODEL : all-MiniLM-L6-v2")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("MILVUS CONNECTION")
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if MILVUS_DATABASE not in db.list_database():
        db.create_database(MILVUS_DATABASE)
        logger.info(f"Database '{MILVUS_DATABASE}' created.")
    logger.info(f"USING DATABASE : {MILVUS_DATABASE}")
    db.using_database(MILVUS_DATABASE)
    # collection definition
    logger.info("COLLECTION SETTING")
    if not utility.has_collection(COLLECTION_NAME):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),  # 모델 차원에 맞게 설정
        ]
        vector_schema = CollectionSchema(fields, description="Text embeddings")
        logger.info(f"Collection '{COLLECTION_NAME}' created.")
        vector_collection = Collection(name=COLLECTION_NAME, schema=vector_schema)
    else:
        logger.info("COLLECTION SETTING")
        vector_collection = Collection(COLLECTION_NAME)
    # check index
    if not vector_collection.has_index():
        logger.info("INDEX CREATING")
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        vector_collection.create_index(
            field_name="embedding", 
            index_params=index_params,
            index_name="idx"
        )
        logger.info("INDEX CREATED")
    vector_collection.load()
