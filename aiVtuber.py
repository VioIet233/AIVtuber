# -*- coding: utf-8 -*-
import asyncio

import http.cookies
from typing import *
from collections import *

from zhipuai import ZhipuAI
import edge_tts

import aiohttp

import pygame
import json
import os

import blivedm
import blivedm.models.web as web_models


CONFIG_PATH = 'config.json'
OUTPUT = '.\\sound\\'

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    SESSDATA = config['sessdata']
    ROOM_ID = config['room_id']
    VOICE = config['voice']
    RATE = config['rate']
    VOLUME = config['volume']
    PITCH = config['pitch']
    ZHIPUAI_API_KEY = config['api_key']



session: Optional[aiohttp.ClientSession] = None

async def main():
    init_config()
    pygame.mixer.init()
    try:
        await run_single_client()
    finally:
        await session.close()


def init_config():
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)
    


async def run_single_client():
    client = blivedm.BLiveClient(ROOM_ID, session=session)
    handler = MyHandler()
    client.set_handler(handler)

    client.start()
    try:
        await client.join()
    finally:
        await client.stop_and_close()

class MyHandler(blivedm.BaseHandler):
    def __init__(self):
        self.message_list = ["","",""]
        self.response_list = ["","",""]
        self.ai_client = ZhipuAI(api_key = ZHIPUAI_API_KEY)
        self.tts_begin = False
        

    async def _do_tts(self, task_id: str):
        task_status = ''
        get_cnt = 0
        await asyncio.sleep(2)
        while task_status != 'SUCCESS' and task_status != 'FAILED' and get_cnt <= 5 :
            result_response = self.ai_client.chat.asyncCompletions.retrieve_completion_result( id = task_id)
            task_status = result_response.task_status
            get_cnt += 1
            await asyncio.sleep(1)
        text = result_response.choices[0].message.content
        print(text)
        self.response_list.append(text)
        if len(self.response_list) > 3:
            self.response_list.pop(0)
        tts = edge_tts.Communicate(text, voice=VOICE, rate=RATE, volume=VOLUME, pitch=PITCH)
        mp3 = f'{OUTPUT}{task_id}.mp3'
        await tts.save(mp3)
        while pygame.mixer.get_busy() and get_cnt <= 10:
            get_cnt += 1
            await asyncio.sleep(1)
        if not pygame.mixer.get_busy():
            pygame.mixer.music.load(mp3)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            pygame.mixer.music.unload()
        os.remove(mp3)

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        print(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
              f' （{message.coin_type}瓜子x{message.total_coin}）')

    def _on_buy_guard(self, client: blivedm.BLiveClient, message: web_models.GuardBuyMessage):
        print(f'[{client.room_id}] {message.username} 购买{message.gift_name}')

    def _on_super_chat(self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage):
        print(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')            

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        print(f'[{client.room_id}] {message.uname}：{message.msg}')
        self.message_list.append(message.msg)
        if len(self.message_list) > 4:
            self.message_list.pop(0)
        response = self.ai_client.chat.asyncCompletions.create(
                model="glm-4",
                messages=[
                    {"role": "system","content": "你是一个虚拟主播，主播名叫白白，虚拟形象是一只小白猫，会回复弹幕的问题，回复问题时简洁明了,但最好不少于3个字，需要带上喵的语气词。只回答最后一个问题就可以了，不需要强调其他。对于违规敏感的问题，回复哼哼，我可不上当喵之类的话"},
                    {"role": "user","content": f'上文1：{self.message_list[0]} ：{self.response_list[0]} '},
                    {"role": "user","content": f'上文2：{self.message_list[1]} ：{self.response_list[1]} '},
                    {"role": "user","content": f'上文3：{self.message_list[2]} ：{self.response_list[2]} '},
                    {"role": "user","content": f'问题：{self.message_list[3]}'}
                ],
        )
        asyncio.create_task(self._do_tts(response.id))
            

        
if __name__ == '__main__':
    asyncio.run(main())
