from flask import Flask,request,jsonify
import asyncio,binascii,json,requests,aiohttp,os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import like_pb2,like_count_pb2,uid_generator_pb2
from google.protobuf.message import DecodeError
app=Flask(__name__)
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
def load_tokens(server_name):
    try:
        if server_name=="IND":
            filename="token_ind.json"
        elif server_name=="ME":
            filename="token_me.json"
        elif server_name in {"BR","US","SAC","NA"}:
            filename="token_br.json"
        else:
            filename="token_bd.json"
        with open(os.path.join(BASE_DIR,filename),"r",encoding="utf-8") as f:
            raw=json.load(f)
        # token_me.json contains plain JWT strings, while older token files
        # may contain {"token": "..."} objects. Normalize both formats.
        if not isinstance(raw,list):
            return None
        tokens=[]
        for item in raw:
            if isinstance(item,str) and item.strip():
                tokens.append({"token":item.strip()})
            elif isinstance(item,dict) and isinstance(item.get("token"),str) and item["token"].strip():
                tokens.append({"token":item["token"].strip()})
        return tokens or None
    except Exception:
        return None
def encrypt_message(plaintext):
    key=b'Yg&tc%DEuh6%Zc^8'
    iv=b'6oyZDr22E3ychjM%'
    cipher=AES.new(key,AES.MODE_CBC,iv)
    return binascii.hexlify(cipher.encrypt(pad(plaintext,AES.block_size))).decode()
def create_like_proto(uid,region):
    m=like_pb2.like()
    m.uid=int(uid)
    m.region=region
    return m.SerializeToString()
def create_info_proto(uid):
    m=uid_generator_pb2.uid_generator()
    m.uid=int(uid)
    m.value=1
    return m.SerializeToString()
def base_url(region):
    r=(region or "").upper()
    if r=="IND":
        return "https://client.ind.freefiremobile.com"
    if r in {"BR","US","SAC","NA"}:
        return "https://client.us.freefiremobile.com"
    if r == "ME":
        return "https://clientbp.ppmainecoonghj.com"
    return "https://clientbp.ggpolarbear.com"
async def send_one(enc_uid,token,url):
    try:
        headers={'User-Agent':"Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",'Connection':"Keep-Alive",'Accept-Encoding':"gzip",'Authorization':f"Bearer {token}",'Content-Type':"application/x-www-form-urlencoded",'Expect':"100-continue",'X-Unity-Version':"2018.4.11f1",'X-GA':"v1 1",'ReleaseVersion':"OB55"}
        async with aiohttp.ClientSession() as s:
            async with s.post(url,data=bytes.fromhex(enc_uid),headers=headers) as r:
                if r.status!=200:
                    return r.status
                return await r.text()
    except Exception:
        return None
async def send_multiple(uid,server,url):
    try:
        enc=encrypt_message(create_like_proto(uid,server))
        tokens=load_tokens(server)
        if tokens is None:
            return None
        tasks=[]
        for t in tokens:
            tasks.append(send_one(enc,t["token"],url))
        return await asyncio.gather(*tasks,return_exceptions=True)
    except Exception:
        return None
def get_player(enc,server,token):
    try:
        url=base_url(server)+"/GetPlayerPersonalShow"
        headers={'User-Agent':"Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",'Connection':"Keep-Alive",'Accept-Encoding':"gzip",'Authorization':f"Bearer {token}",'Content-Type':"application/x-www-form-urlencoded",'Expect':"100-continue",'X-Unity-Version':"2018.4.11f1",'X-GA':"v1 1",'ReleaseVersion':"OB55"}
        r=requests.post(url,data=bytes.fromhex(enc),headers=headers,verify=False)
        items=like_count_pb2.Info()
        items.ParseFromString(r.content)
        return items
    except DecodeError:
        return None
    except Exception:
        return None
@app.route('/like',methods=['GET'])
def handle_like():
    uid=request.args.get("uid")
    server=request.args.get("server_name","").upper()
    if not uid or not server:
        return jsonify({"error":"UID and server_name are required"}),400
    try:
        tokens=load_tokens(server)
        if tokens is None:
            return jsonify({"error":"Failed to load tokens"}),500
        token=tokens[0]["token"]
        enc_uid=encrypt_message(create_info_proto(uid))
        before=get_player(enc_uid,server,token)
        if before is None:
            return jsonify({"error":"Failed to retrieve initial player info"}),500
        data_before=json.loads(MessageToJson(before))
        before_like=int(data_before.get('AccountInfo',{}).get('Likes',0))
        url=base_url(server)+"/LikeProfile"
        asyncio.run(send_multiple(uid,server,url))
        after=get_player(enc_uid,server,token)
        if after is None:
            return jsonify({"error":"Failed to retrieve player info after like"}),500
        data_after=json.loads(MessageToJson(after))
        after_like=int(data_after.get('AccountInfo',{}).get('Likes',0))
        player_uid=int(data_after.get('AccountInfo',{}).get('UID',0))
        player_name=str(data_after.get('AccountInfo',{}).get('PlayerNickname',''))
        player_region=str(data_after.get('AccountInfo',{}).get('region',''))
        player_level=str(data_after.get('AccountInfo',{}).get('level',''))
        like_given=after_like-before_like
        return jsonify({"LikesGivenByAPI":like_given,"LikesbeforeCommand":before_like,"LikesafterCommand":after_like,"PlayerNickname":player_name,"Region":player_region,"Level":player_level,"UID":player_uid,"status":1 if like_given!=0 else 2})
    except Exception as e:
        return jsonify({"error":str(e)}),500
if __name__=='__main__':
    app.run(debug=False,use_reloader=False)