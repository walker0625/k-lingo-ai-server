from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from db.vectordb import milvus_service
## logger
from loguru import logger
## user router
router = APIRouter()

class VectorText(BaseModel):
    text: str

@router.post("/embedding")
def add_text_to_vectordb(data: VectorText):
    try:
        ids = milvus_service.insert(data.text)
        return {"status": "success", "id": ids[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/retriever")
def retriever_text(data: VectorText, top_k: int = 5):
    """
        유사도 겁색
        검색 유형 참고 : IP - inner product, L2 - euclid(유클리드)
        nprobe : 검색 할 클러스터 개수(IVF 계열 인덱스) - 높을수록 정확도 향상, 성능 하락
    """
    try:
        results = milvus_service.search(data.text, top_k=top_k)
        response = []
        for hits in results:
            for hit in hits:
                response.append({
                    "id": hit.id,
                    "distance": hit.distance,
                    "text": hit.entity.get("text")
                })
        return {"results": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))