from config import settings
import httpx

base_url = f'http://{settings.API_HOST}:{settings.API_PORT}'

class APIbase():
    operation_name: str = None
    operation: function = None

    @classmethod
    async def fetch_post(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json = data)
            return response.json()
        
    @classmethod
    async def fetch_get(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, json = data)
            return response.json()
        
    @classmethod
    async def fetch_patch(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, json = data)
            return response.json()
        
    @classmethod
    async def fetch_delete(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, json = data)
            return response.json()

    @classmethod
    async def agent(cls, data: dict) -> dict:
        url = f'{base_url}/{cls.operation_name}/agents'
        response = await cls.operation(url, data)
        return response
    
    @classmethod
    async def agentDocs(cls, data: dict) -> dict:
        url = f'{base_url}/{cls.operation_name}/agentsDocs'
        response = await cls.operation(url, data)
        return response
    
    
class APIcreate(APIbase):
    operation_name = 'create'
    operation = APIbase.fetch_post

class APIread(APIbase):
    operation_name = 'read'
    operation = APIbase.fetch_get

class APIupdate(APIbase):
    operation_name = 'update'
    operation = APIbase.fetch_patch

class APIcreate(APIbase):
    operation_name = 'delete'
    operation = APIbase.fetch_delete
