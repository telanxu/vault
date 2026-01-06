""" Panasonic Smart Home China """
import logging
import asyncio
from http import HTTPStatus
import aiohttp
from getpass import getpass
import json
from datetime import datetime
from typing import Literal, Final
import hashlib

HA_USER_AGENT = "SmartApp"
BASE_URL = 'https://app.psmartcloud.com/App'

CONTENT_TYPE_JSON: Final = "application/json"
REQUEST_TIMEOUT = 15

_LOGGER = logging.getLogger(__name__)

class apis(object):

    def get_token():
        return f"{BASE_URL}/UsrGetToken"

    def login():
        return f"{BASE_URL}/UsrLogin"

    def get_user_devices():
        return f"{BASE_URL}/UsrGetBindDevInfo"

class PanasonicSmartHome(object):
    """
    Panasonic Smart Home Object for China
    """
    def __init__(self, hass, session, username, password):
        self.hass = hass
        self.username = username
        self.password = password
        self._session = session
        self._devices = []
        self._commands = []
        self._devices_info = {}
        self._commands_info = {}
        self.real_usr_id = None
        self.ssid = None
        self.familyId = None
        self.realFamilyId = None
        self._mversion = None
        self._update_timestamp = None
        self._api_counts = 0
        self._api_counts_per_hour = 0

    async def request(
        self,
        method: Literal["GET", "POST"],
        headers,
        endpoint: str,
        params=None,
        data=None,
    ):
        """Shared request method"""
        res = {}
        headers["user-agent"] = HA_USER_AGENT
        headers["Content-Type"] = CONTENT_TYPE_JSON

        self._api_counts = self._api_counts + 1
        self._api_counts_per_hour = self._api_counts_per_hour + 1
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.request(
                    method,
                    url=endpoint,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    ssl=False
                )
                if response.status == HTTPStatus.OK:
                    try:
                        res = await response.json()
                    except:
                        res = {}
                elif response.status == HTTPStatus.BAD_REQUEST:
                    raise Exception("Exceed rate limit")
                elif response.status == HTTPStatus.FORBIDDEN:
                    raise Exception("Login failed")
                elif response.status == HTTPStatus.TOO_MANY_REQUESTS:
                    raise Exception("Too many requests")
                elif response.status == HTTPStatus.EXPECTATION_FAILED:
                    raise Exception("Expectation failed")
                elif response.status == HTTPStatus.NOT_FOUND:
                    _LOGGER.warning(f"Use wrong method or parameters")
                    res = {}
                else:
                    raise Exception("Token not found")
        except Exception as e:
            _LOGGER.error(f"Request exception: {e}")
            return {}

        if isinstance(res, list):
            return {"data": res}

        return res

    async def login(self):
        """
        Login to get access token for China.
        """
        headers = {'User-Agent': 'SmartApp', 'Content-Type': 'application/json'}

        # 1. GetToken
        response = await self.request(
            method="POST",
            headers=headers,
            endpoint=apis.get_token(),
            data={
                "id": 1, "uiVersion": 4.0, "params": {"usrId": self.username}
            }
        )
        token_start = response.get('results', {}).get('token')

        if not token_start:
            raise Exception("GetToken Failed")

        # 2. Calc Password
        pwd_md5 = hashlib.md5(self.password.encode()).hexdigest().upper()
        inter_md5 = hashlib.md5((pwd_md5 + self.username).encode()).hexdigest().upper()
        final_token = hashlib.md5((inter_md5 + token_start).encode()).hexdigest().upper()

        # 3. Login
        response = await self.request(
            method="POST",
            headers=headers,
            endpoint=apis.login(),
            data={
                "id": 2, "uiVersion": 4.0, 
                "params": {"telId": "00:00:00:00:00:00", "checkFailCount": 0, "usrId": self.username, "pwd": final_token}
            }
        )
        login_res = response.get('results', {})

        if not login_res:
            raise Exception("Login Failed")

        self.real_usr_id = login_res.get('usrId')
        self.ssid = login_res.get('ssId')
        self.realFamilyId = login_res.get('realFamilyId')
        self.familyId = login_res.get('familyId')

    async def get_user_devices(self):
        """
        List devices that the user has permission for China.
        """
        headers = {"Cookie": f"SSID={self.ssid}"}
        response = await self.request(
            method="POST",
            headers=headers,
            endpoint=apis.get_user_devices(),
            data={
                "id": 3, "uiVersion": 4.0,
                "params": {"realFamilyId": self.realFamilyId, "familyId": self.familyId, "usrId": self.real_usr_id}
            }
        )

        devices = response.get("results", {}).get("devList", [])
        commands = []  # CommandList not directly available in China API, set to empty

        return devices, commands

    async def get_devices_info(self):
        """
        get devices for China
        """
        await self.login()
        info = {
            "GwList": [],
            "CommandList": []
        }
        devices, commands = await self.get_user_devices()
        info["GwList"] = devices
        info["CommandList"] = commands
        return info

async def get_devices(username, password):
    client = PanasonicSmartHome(None, None, username, password)

    info = await client.get_devices_info()
    if len(info["GwList"]) >= 1:
        with open("panasonic_devices.json", "w", encoding="utf-8") as f_out:
            f_out.write(json.dumps(info["GwList"], indent=2, ensure_ascii=False))
        with open("panasonic_commands.json", "w", encoding="utf-8") as f_out:
            f_out.write(json.dumps(info["CommandList"], indent=2, ensure_ascii=False))
        print("\nThe panasonic_devices.json and panasonic_commands.json are generated, please send them to the developer!")

##################################################

def main():  # noqa MC0001
    basic_version = "0.0.1"
    print(f"Version: {basic_version}\n")
    username = input("Account (Phone Number): ")
    password = getpass()
    asyncio.run(get_devices(username, password))

if __name__ == '__main__':
    main()
