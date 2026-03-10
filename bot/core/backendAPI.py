from datetime import date

from core.config import settings
import httpx
from typing import Awaitable, Callable, Any
from aiogram.types import Document

from fastapi import status

base_url = f'http://{settings.API_HOST}:{settings.API_PORT}/api'

class APIbase():
    operation: Callable[..., Awaitable[Any]] = None

    @classmethod
    async def fetch_post(cls, url: str, data: dict, file_name: str|None, file_bytes: bytes|None) -> dict:
        async with httpx.AsyncClient() as client:
            if file_name and file_bytes:
                files = {
                    'file': (file_name, file_bytes, 'application/octet-stream')
                }

                response = await client.post(url, data = data, files=files, timeout=600.0)
            else:
                response = await client.post(url, json = data)
            
            if not response.is_success:
                return {'error_code': response.status_code}
            if response.content:
                result = response.json()

                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}
        
    @classmethod
    async def fetch_get(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params = data)
            
            if not response.is_success:
                return {'error_code': response.status_code}
            if response.content:
                result = response.json()
                
                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}
        
    @classmethod
    async def fetch_patch(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, json = data)
            
            if not response.is_success:
                return {'error_code': response.status_code}
            if response.content:
                result = response.json()

                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}
        
    @classmethod
    async def fetch_delete(cls, url: str, data: dict) -> dict|list:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, params = data)
            
            if not response.is_success:
                return {'error_code': response.status_code}
            if response.content:
                result = response.json()
                
                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}

    @classmethod
    async def agent(cls, data: dict, add_url = None) -> dict:
        url = f'{base_url}/agents/{f"/{add_url}" if add_url else ""}'
        response = await cls.operation(url, data)
        return response
    
    @classmethod
    async def user(cls, data: dict, add_url = None) -> dict:
        url = f'{base_url}/users/{f"/{add_url}" if add_url else ""}'
        response = await cls.operation(url, data)
        return response
    
    @classmethod
    async def document(cls, data: dict, file_name: str|None, file_bytes: bytes|None, add_url = None) -> dict:
        url = f'{base_url}/documents/{f"/{add_url}" if add_url else ""}'
        response = await cls.operation(url, data, file_name, file_bytes)
        return response
    

    
class APIcreate(APIbase):
    operation = APIbase.fetch_post

    @classmethod
    async def agentBy_UserWith_tgID(cls, data: dict, tg_id: int) -> dict:
        data = data.copy()
        data['tg_id'] = tg_id
        return await cls.agent(data, add_url='ByUserWith_tgID')
    
    @classmethod
    async def documentBy_botID(cls, agent_id: int, file_name: str, file_bytes: bytes) -> dict:
        data = {'bot_id': agent_id}
        return await cls.document(data, file_name, file_bytes)
    

    

class APIread(APIbase):
    operation = APIbase.fetch_get
    # agents
    @classmethod
    async def agentBy_botID(cls, bot_id: int) -> dict:
        return await cls.agent({'bot_id': bot_id})
    
    @classmethod
    async def allAgentsBy_tgID(cls, tg_id: int) -> dict|list:
        add_url = 'allBy_tgID'
        return cls.agent({'id': tg_id}, add_url = add_url)
    
    # docs
    @classmethod
    async def allDocsBy_botID(cls, bot_id: int) -> dict|list:
        add_url = 'allBy_botID'
        return cls.document({'bot_id': bot_id}, add_url = add_url)
    
    @classmethod
    async def docBy_ID(cls, id: int) -> dict:
        add_url = f'{id}'
        return cls.document({}, add_url = add_url)
    
    @classmethod
    async def contextBy_botID(cls, bot_id: int, query: str) -> dict|list:
        add_url = 'getContextBy_agentID'
        return cls.document({'agent_id': bot_id, 'query': query}, add_url = add_url)
    
    # users
    @classmethod
    async def userBy_agentID(cls, bot_id: int) -> dict:
        add_url = 'by_agentID'
        return cls.user({'id': bot_id}, add_url = add_url)
    
    @classmethod
    async def userBy_tgID(cls, tg_id: int) -> dict:
        add_url = 'by_tgID'
        return cls.user({'id': tg_id}, add_url = add_url)



class APIupdate(APIbase):
    operation = APIbase.fetch_patch
    @classmethod
    async def agentPromptBy_botID(cls, prompt: str, bot_id: int) -> dict:
        add_url = 'by_botID'
        return cls.agent({'system_prompt': prompt, 'bot_id': bot_id}, add_url = add_url)
    
    @classmethod
    async def agentWelcomeBy_botID(cls, welcome: str, bot_id: int) -> dict:
        add_url = 'by_botID'
        return cls.agent({'welcome_message': welcome, 'bot_id': bot_id}, add_url = add_url)
    
    @classmethod
    async def agentToggle_status(cls, bot_id: int) -> dict:
        add_url = 'toggle_status'
        return cls.agent({'bot_id': bot_id}, add_url = add_url)
    @classmethod
    async def userSubBy_tgID(cls, sub_type: str|None, sub_end: date|None, tg_id: int) -> dict:
        add_url = 'by_tgID'
        data = {'telegram_id': tg_id}
        if sub_type:
            data['subscription_type'] = sub_type

        if sub_end:
            data['subscription_end_date'] = sub_end

        return cls.user(data, add_url = add_url)




class APIdelete(APIbase):
    operation = APIbase.fetch_delete
    @classmethod
    async def agentBy_botID(cls, bot_id: int) -> dict:
        return await cls.agent({'bot_id': bot_id})
    @classmethod
    async def documentBy_ID(cls, id: int) -> dict:
        add_url = f'{id}'
        return await cls.document({}, add_url=add_url)
    
# функция для понятной обрабоки ошибок  
def get_response_status(response: dict|list) -> int:
    if 'error_code' in response:
        return response.get('error_code')
    else:
        return status.HTTP_200_OK