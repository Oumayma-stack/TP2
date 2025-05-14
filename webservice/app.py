#################################################################################################
##                                                                                             ##
##                                 NE PAS TOUCHER CETTE PARTIE                                 ##
##                                                                                             ##
## 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 ##
import boto3
from botocore.config import Config
import os
import uuid
from dotenv import load_dotenv
from typing import Union
import logging
from fastapi import FastAPI, HTTPException, Request, status, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from getSignedUrl import getSignedUrl

load_dotenv()


app = FastAPI()
logger = logging.getLogger("uvicorn")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
	logger.error(f"{request}: {exc_str}")
	content = {'status_code': 10422, 'message': exc_str, 'data': None}
	return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class Post(BaseModel):
    title: str
    body: str

my_config = Config(
    region_name='us-east-1',
    signature_version='v4',
)

dynamodb = boto3.resource('dynamodb', config=my_config)
table = dynamodb.Table(os.getenv("DYNAMO_TABLE"))
s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
bucket = os.getenv("BUCKET")

## ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ##
##                                                                                                ##
####################################################################################################




@app.post("/posts")
async def post_a_post(post: Post, authorization: str | None = Header(default=None)):
    """
    Poste un post ! Les informations du poste sont dans post.title, post.body et le user dans authorization
    """
    logger.info(f"title : {post.title}")
    logger.info(f"body : {post.body}")
    logger.info(f"user : {authorization}")
    post_id = f"POST#{uuid.uuid4()}"
    res = table.put_item(
            Item={
             'user' : authorization,
             'id' : post_id,   
            'title': post.title,
            'body': post.body,
            }
            )
    # Doit retourner le résultat de la requête la table dynamodb
    return res

@app.get("/posts")
async def get_all_posts(user: Union[str, None] = None):
    """
    Récupère tout les postes. 
    - Si un user est présent dans le requête, récupère uniquement les siens
    - Si aucun user n'est présent, récupère TOUS les postes de la table !!
    """
    if user:
        logger.info(f"Récupération des postes de : {user}")
        res = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user").eq(user) &
                                   boto3.dynamodb.conditions.Key("id").begins_with("POST#")
        )
        items = res.get("Items", [])
        logger.info("anaa")
      
        for item in items:
            logger.info(item.get("key"))
    else:
        logger.info("Récupération de tous les postes")
        res = table.scan()
        items = res.get("Items", [])
        items = [item for item in items if item.get("id", "").startswith("POST#")]
        

    # Construction de la réponse attendue
    posts = []
    for item in items:
        try:
            # Générer l'URL pré-signée si 'key' est présent
            object_key = item.get("key")
            if object_key:
                url = s3_client.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={
                        "Bucket": bucket,
                        "Key": object_key
                    },
                    ExpiresIn=3600 
                )
            else:
                url = None

            posts.append({
                "id" : item.get("id"),
                "user": item.get("user"),
                "title": item.get("title"),
                "body": item.get("body"),
                "image": url,
                "label": item.get("labels", [])
            })
            

        except Exception as e:
            logger.warning(f"Erreur lors du traitement d’un post : {e}")

    return posts


    
@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, authorization: str | None = Header(default=None)):
    # Doit retourner le résultat de la requête la table dynamodb
    logger.info(f"post id : {post_id}")
    logger.info(f"user: {authorization}")
    # Récupération des infos du poste
    res = table.get_item(
            Key={
                'user': authorization,
                'id': post_id
            }
    )
    item = res.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Post introuvable")
    # S'il y a une image on la supprime de S3
    if "key" in item:
        try:
            s3_client.delete_object(Bucket=bucket, Key=item["key"])
            logger.info(f"Image supprimée de S3 : {item['key']}")
        except Exception as e:
            logger.warning(f"Erreur lors de la suppression de l'image S3 : {e}")

    # Suppression de la ligne dans la base dynamodb
    delete_res = table.delete_item(
            Key={
                'user': authorization,
                'id': post_id
            }
        )
    # Retourne le résultat de la requête de suppression
    return delete_res



#################################################################################################
##                                                                                             ##
##                                 NE PAS TOUCHER CETTE PARTIE                                 ##
##                                                                                             ##
## 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 👇 ##
@app.get("/signedUrlPut")
async def get_signed_url_put(filename: str,filetype: str, postId: str,authorization: str | None = Header(default=None)):

    return getSignedUrl(filename, filetype, postId, authorization)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")

## ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ☝️ ##
##                                                                                                ##
####################################################################################################