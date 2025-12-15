import os
from pymilvus import connections, utility, db, Collection, CollectionSchema, FieldSchema, DataType
from sentence_transformers import SentenceTransformer
## logger
from loguru import logger
MILVUS_HOST=os.environ["MILVUS_HOST"]
MILVUS_PORT=os.environ["MILVUS_PORT"]
MILVUS_DATABASE=os.environ["MILVUS_DATABASE"]
EMBEDDING_DIM = int(os.environ["EMBEDDING_DIM"])
COLLECTION_NAME = "text_collection"
MODEL_NAME = "all-MiniLM-L6-v2"

class MilvusHandler:
    def __init__(self):
        self.collection = None
        self.model = None

    def connect(self):
        logger.info("Milvus connection")
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        # DB 생성/선택
        if MILVUS_DATABASE not in db.list_database():
            db.create_database(MILVUS_DATABASE)
        db.using_database(MILVUS_DATABASE)
        # 컬렉션 로드/생성 및 인덱스 보장
        self._init_collection()

    def _init_collection(self):
        # 컬렉션 존재 여부 확인
        if not utility.has_collection(COLLECTION_NAME):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
            ]
            schema = CollectionSchema(fields, description="Text embedding collection")
            self.collection = Collection(name=COLLECTION_NAME, schema=schema)
            logger.debug(f"Collection '{COLLECTION_NAME}' created.")
        else:
            self.collection = Collection(COLLECTION_NAME)
            logger.debug(f"Collection '{COLLECTION_NAME}' found.")

        # ★ 핵심: 인덱스 확인 및 생성
        if not self.collection.has_index():
            logger.debug("Creating index...")
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params,
                index_name="idx"
            )
        # 컬렉션 메모리 로드
        self.collection.load()
        ## Embedding Model
        logger.debug("Loading Embedding Model...")
        self.model = SentenceTransformer(MODEL_NAME)

    def disconnect(self):
        if self.collection:
            self.collection.release()
        connections.disconnect("default")
        logger.debug("milvus disconnected.")
        
    def encode(self, text: str):
        if not self.model:
            raise RuntimeError("Model is not loaded")
        return self.model.encode(text).tolist()    

    # 검색/삽입 헬퍼 메서드
    def insert(self, text: str):
        if not self.collection:
            raise RuntimeError("Collection is not loaded")
        vector = self.encode(text)
        data = [[text], [vector]]
        res = self.collection.insert(data)
        self.collection.flush() # 즉시 반영이 필요할 경우 사용
        return res.primary_keys

    def search(self, text: str, top_k: int = 5):
        if not self.collection:
            raise RuntimeError("Collection is not loaded")
        vector = self.encode(text)
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        return self.collection.search(
            data=[vector], 
            anns_field="embedding", 
            param=search_params, 
            limit=top_k,
            output_fields=["text"]
        )

# 싱글톤 인스턴스 생성
milvus_service = MilvusHandler()