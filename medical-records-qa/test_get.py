from services.vectorstore import VectorStore
v = VectorStore()
res = v._collection("p_1").get(where={"doc_id": "500b45c5-14de-4502-b952-1a97cc41245d"})
print(len(res["ids"]))
