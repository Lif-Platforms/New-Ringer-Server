from fastapi import APIRouter, UploadFile, Depends, HTTPException
from fastapi.responses import FileResponse
from app.auth import useAuth
import app.config as config
import requests
import os

router = APIRouter()

@router.post("/client-bg/v1/upload")
async def upload_client_bg(file: UploadFile, account = Depends(useAuth)) -> dict:
    if file.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    authURL = config.get_config("auth-server-url")
    authResponse = requests.get(f"{authURL}/account/v1/get_id/{account[0]}")

    if authResponse.status_code != 200:
        raise HTTPException(status_code=500)
    else:
        userId = authResponse.text[1:-1]

    fileContents = await file.read()
    filePath = f"userUploads/userBackgrounds/{userId}.{file.content_type[6:]}"

    if os.path.isfile(filePath):
        os.remove(filePath)

    with open(filePath, "wb") as writeFile:
        writeFile.write(fileContents)

    return {"status": "ok"}

@router.get("/client-bg/v1/get")
def get_client_bg(account = Depends(useAuth)) -> FileResponse:
    authURL = config.get_config("auth-server-url")
    authResponse = requests.get(f"{authURL}/account/v1/get_id/{account[0]}")

    if authResponse.status_code != 200:
        raise HTTPException(status_code=500)
    else:
        userId = authResponse.text[1:-1]

    def get_bg_dir(userId: str):
        uploadFiles = os.listdir("userUploads/userBackgrounds")

        for file in uploadFiles:
            if file.startswith(userId): return file

        return None
    
    clientBgFileDir = get_bg_dir(userId)

    if not clientBgFileDir: 
        raise HTTPException(status_code=404, detail="No background found.")
    else:
        responseFileName, responseFileType = os.path.splitext(clientBgFileDir)
    
    return FileResponse(
        path=f"userUploads/userBackgrounds/{responseFileName + responseFileType}",
        media_type=f"image/{responseFileType[1:]}"
    )

@router.delete("/client-bg/v1/delete")
def delete_client_bg(account = Depends(useAuth)):
    authURL = config.get_config("auth-server-url")
    authResponse = requests.get(f"{authURL}/account/v1/get_id/{account[0]}")

    if authResponse.status_code != 200:
        raise HTTPException(status_code=500)
    else:
        userId = authResponse.text[1:-1]

    def get_bg_dir(userId: str):
        uploadFiles = os.listdir("userUploads/userBackgrounds")

        for file in uploadFiles:
            if file.startswith(userId): return file

        return None
    
    userBgDir = get_bg_dir(userId)

    if userBgDir:
        os.remove("userUploads/userBackgrounds/" + userBgDir)

    return {"status": "ok"}