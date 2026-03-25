from datetime import date, datetime

from core.config import settings
import httpx
from typing import Awaitable, Callable, Any
import json
from fastapi import status
 
import inspect
base_url = f'http://{settings.API_HOST}:{settings.API_PORT}/api'


def _internal_headers() -> dict:
    return {"X-Internal-API-Key": settings.INTERNAL_API_KEY}

class APIbase():
    operation: Callable[..., Awaitable[Any]] = None

    @classmethod
    async def fetch_post(cls, url: str, data: dict, file_name: str|None = None, file_bytes: bytes|None = None) -> dict:
        async with httpx.AsyncClient() as client:
            if file_name and file_bytes:
                files = {
                    'file': (file_name, file_bytes, 'application/octet-stream')
                }

                response = await client.post(url, data=data, files=files, timeout=600.0, headers=_internal_headers())
            else:
                response = await client.post(url, json=data, headers=_internal_headers())
            if not response.is_success:
                return {
                    'error_code': response.status_code,
                    'error_detail': response.text
                    }
            if response.content:
                result = response.json()

                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}
        
    @classmethod
    async def fetch_get(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=data, headers=_internal_headers())
            if not response.is_success:
                return {
                    'error_code': response.status_code,
                    'error_detail': response.text
                    }
            if response.content:
                result = response.json()
                
                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}
        
    @classmethod
    async def fetch_patch(cls, url: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, json=data, headers=_internal_headers())
            
            if not response.is_success:
                return {
                    'error_code': response.status_code,
                    'error_detail': response.text
                    }
            if response.content:
                result = response.json()

                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}
        
    @classmethod
    async def fetch_delete(cls, url: str, data: dict) -> dict|list:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, params=data, headers=_internal_headers())
            
            if not response.is_success:
                return {
                    'error_code': response.status_code,
                    'error_detail': response.text
                    }
            if response.content:
                result = response.json()
                
                return result
            else:
                return {'no_body': True, 'status_code': response.status_code}

    @classmethod
    async def agent(cls, data: dict, add_url = None) -> dict:
        url = f'{base_url}/agents{f"/{add_url}" if add_url else ""}'
        response = await cls.operation(url, data)
        return response
    
    @classmethod
    async def user(cls, data: dict, add_url = None) -> dict:
        url = f'{base_url}/users{f"/{add_url}" if add_url else ""}'
        response = await cls.operation(url, data)
        return response
    
    @classmethod
    async def document(cls, data: dict, file_name: str|None = None, file_bytes: bytes|None = None, add_url = None) -> dict:
        url = f'{base_url}/documents{f"/{add_url}" if add_url else ""}'
        
        sig = inspect.signature(cls.operation)
        
        if 'file_name' in sig.parameters:
            response = await cls.operation(url, data, file_name=file_name, file_bytes=file_bytes)
        else:
            response = await cls.operation(url, data)
        
        return response


    
class APIcreate(APIbase):
    operation = APIbase.fetch_post

    @classmethod
    async def agentBy_UserWith_tgID(
        cls,
        bot_id: int = None,
        tg_id: int = None,
        encrypted_token: str = None,
        bot_username:str = None
    ) -> dict:
        
        data = {
            'bot_id': bot_id,
            'encrypted_token': encrypted_token,
            'bot_username': bot_username,
            'tg_id': tg_id
            }

        return await cls.agent(data, add_url='ByUserWith_tgID')
    
    @classmethod
    async def userBy_tgID(cls, name:str, tg_id: int) -> dict:
        data = {'name':name, 'telegram_id': tg_id}
        return await cls.user(data)
    
    @classmethod
    async def documentBy_botID(cls, agent_id: int, file_name: str, file_bytes: bytes) -> dict:
        agent_data = {'bot_id': agent_id}
        return await cls.document(data = {'agent_data' : json.dumps(agent_data)}, file_name=file_name, file_bytes = file_bytes)
    

    

class APIread(APIbase):
    operation = APIbase.fetch_get
    # agents
    @classmethod
    async def agentBy_botID(cls, bot_id: int) -> dict:
        return await cls.agent({'bot_id': bot_id})
    
    @classmethod
    async def allAgentsBy_tgID(cls, tg_id: int) -> dict|list:
        add_url = 'allBy_tgID'
        return await cls.agent({'id': tg_id}, add_url = add_url)
    
    # docs
    @classmethod
    async def allDocsBy_botID(cls, bot_id: int) -> dict|list:
        add_url = 'allBy_botID'
        return await cls.document({'bot_id': bot_id}, add_url = add_url)
    
    @classmethod
    async def docBy_ID(cls, id: int) -> dict:
        add_url = f'{id}'
        return await cls.document({}, add_url = add_url)
    
    @classmethod
    async def contextBy_botID(cls, bot_id: int, query: str) -> dict|list:
        add_url = 'getContextBy_agentID'
        return await cls.document({'agent_id': bot_id, 'query': query}, add_url = add_url)
    
    # users
    @classmethod
    async def userBy_agentID(cls, bot_id: int) -> dict:
        add_url = 'by_agentID'
        return await cls.user({'id': bot_id}, add_url = add_url)
    
    @classmethod
    async def userBy_tgID(cls, tg_id: int) -> dict:
        add_url = 'by_tgID'
        return await cls.user({'id': tg_id}, add_url = add_url)



class APIupdate(APIbase):
    operation = APIbase.fetch_patch
    @classmethod
    async def agentPromptBy_botID(cls, prompt: str, bot_id: int) -> dict:
        add_url = 'by_botID'
        return await cls.agent({'system_prompt': prompt, 'bot_id': bot_id}, add_url = add_url)
    
    @classmethod
    async def agentWelcomeBy_botID(cls, welcome: str, bot_id: int) -> dict:
        add_url = 'by_botID'
        return await cls.agent({'welcome_message': welcome, 'bot_id': bot_id}, add_url = add_url)
    
    @classmethod
    async def agentToggle_status(cls, bot_id: int) -> dict:
        add_url = 'toggle_status'
        return await cls.agent({'bot_id': bot_id}, add_url = add_url)
    @classmethod
    async def userSubBy_tgID(cls, sub_type: str|None, sub_end: date|None, tg_id: int) -> dict:
        add_url = 'by_tgID'
        data = {'telegram_id': tg_id}
        if sub_type:
            data['subscription_type'] = sub_type

        if sub_end:
            data['subscription_end_date'] = sub_end.isoformat()

        return await cls.user(data, add_url = add_url)




class APIdelete(APIbase):
    operation = APIbase.fetch_delete
    @classmethod
    async def agentBy_botID(cls, bot_id: int) -> dict:
        return await cls.agent({'bot_id': bot_id})
    @classmethod
    async def documentBy_ID(cls, id: int) -> dict:
        add_url = f'{id}'
        return await cls.document({}, add_url=add_url)

import logging
# функция для понятной обрабоки ошибок  
def get_response_status(response: dict|list) -> int:
    if 'error_code' in response:
        logging.info(f"HTTP ERROR({response.get('error_code')}) {response.get('error_detail')}")
        return response.get('error_code')
    else:
        return status.HTTP_200_OK