from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

class RPCRequest(BaseModel):
    jsonrpc: str
    method: str
    params: list | dict | None = None
    id: int | str | None = None

@app.post("/")
def rpc(req: RPCRequest):
    # Return canned responses based on method
    if req.method == "eth_blockNumber":
        return JSONResponse({"jsonrpc": "2.0", "id": req.id, "result": "0x1"})
    return JSONResponse({"jsonrpc": "2.0", "id": req.id, "result": None})
