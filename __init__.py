import time
import random
from nonebot import on_command
from models.bag_user import BagUser
from nonebot.params import CommandArg
from utils.message_builder import image
from utils.image_utils import text2image
from utils.utils import get_message_at
from nonebot.permission import SUPERUSER
from configs.config import NICKNAME, Config
from nonebot_plugin_apscheduler import scheduler
from utils.utils import is_number, UserBlockLimiter
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, Message, MessageSegment
from nonebot.adapters.onebot.v11.permission import GROUP


__zx_plugin_name__ = "亡命神抽"
__plugin_usage__ = f"""
usage：
    第一位玩家发起游戏，指令：亡命神抽
    加入亡命神抽，指令：参加神抽
    人齐后开局，指令：神抽开始，至少2位玩家，至多5位
    抽卡指令：抽卡
    宣布停止，指令：不抽了
    查看所有玩家战利品指令：查看战利品
    超时150s后，游戏结束指令：神抽结束
    卡牌使用指令：卡牌动作 + 卡牌ID + @目标玩家（如果需要）
    例如：大炮：炮击卡B6@死肥宅，弯刀：抢劫卡P3@死肥宅
    藏宝图：挖宝卡Z5，美人鱼：移动卡C8，钩子：钩取卡Y7
    特别注意：本游戏采取桌游版规则，与steam版与iOS版存在一定出入
    当存在可执行目标时必须发动卡牌效果，即使一定引起爆炸
    大炮和钩子和弯刀只能以某类卡最上方一张（分最高的）作为目标
    海怪是要求右方有2张卡即可，不一定需要再抽2张（比如抽到刀再抢一张）
    爆炸时即使船锚保护了钥匙和宝箱也不会触发奖励
    其他详细规则这里就不一一介绍了，自己去百度吧
    另外：原版一副卡牌堆50+弃牌堆10对于4-5人太少了2人又太多了
    本游戏总卡堆扩充到80+20，2人时为随机32+8，3人48+12，以此类推
    游戏结束后得分最高的所有玩家各奖励（50*总玩家人数）金币
    达成大满贯（一次收藏十张）的玩家无论是否胜利每达成一次奖励1000金币
    悄悄话：{NICKNAME}就是发牌姬，想要神抽就去讨好她吧
""".strip()
__plugin_des__ = f"{NICKNAME}小游戏-亡命神抽"
__plugin_cmd__ = ["亡命神抽"]
__plugin_type__ = ("群内小游戏",)
__plugin_version__ = 1.1
__plugin_author__ = "死肥宅"
__plugin_settings__ = {
    "level": 5,
    "default_status": True,
    "limit_superuser": False,
    "cmd": ["亡命神抽"],
}


Ginfo = {}
blk = UserBlockLimiter()

def getStartUserName(gid):
    global Ginfo
    return Ginfo[gid]["players"][Ginfo[gid]["startUid"]]["uname"]



opendraw = on_command("亡命神抽", priority=5, permission=GROUP, block=True)

ruchang = on_command("参加神抽", priority=5, permission=GROUP, block=True)

kaiju = on_command("神抽开始", priority=5, permission=GROUP, block=True)

napai = on_command("抽卡", priority=5, permission=GROUP, block=True)

tingpai = on_command("不抽了", priority=5, permission=GROUP, block=True)

jiesuan = on_command("神抽结束", priority=5, permission=GROUP, block=True)

chakan = on_command("查看战利品", priority=5, permission=GROUP, block=True)

yidong = on_command("移动卡", priority=5, permission=GROUP, block=True)

paoji = on_command("炮击卡", priority=5, permission=GROUP, block=True)

gouqu = on_command("钩取卡", priority=5, permission=GROUP, block=True)

wabao = on_command("挖宝卡", priority=5, permission=GROUP, block=True)

qiangjie = on_command("抢劫卡", priority=5, permission=GROUP, block=True)



@opendraw.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    gid = event.group_id
    uid = event.user_id
    if blk.check(gid):
        await opendraw.finish()
    blk.set_true(gid)

    global Ginfo
    # 获取用户名
    uname = event.sender.card if event.sender.card else event.sender.nickname
    # 判断上一场是否结束
    if gid in Ginfo:
        #有这个群的数据
        if Ginfo[gid]["state"] != 0:
            blk.set_false(gid)
        if Ginfo[gid]["state"] == 1:
            #state : 已开场，未开局
            blk.set_false(gid)
            await opendraw.finish(f"上一场亡命神抽还未开始，请输入参加神抽")
        if Ginfo[gid]["state"] == 2:
            #state : 已开局，未结束
            blk.set_false(gid)
            await opendraw.finish(f"上一场亡命神抽还未结束，请等待")

    if gid not in Ginfo:
        Ginfo[gid] = {"state": 1}

    #重置游戏状态，牌堆后移至开局后根据人数生成
    Ginfo[gid]["players"] = {}
    Ginfo[gid]["playerInfo"] = []
    Ginfo[gid]["state"] = 1
    Ginfo[gid]["startUid"] = uid
    Ginfo[gid]["deck"] = []
    Ginfo[gid]["turn"] = 0
    #预留回合控制
    #Ginfo[gid]["round"] = 5
    Ginfo[gid]["treasure"] = []
    #记录当前甲板卡牌效果发动中的状态，M为美人鱼发动中，D为刀，P为炮，G为钩子，H1-2为海怪，Y为钥匙，B为宝箱，C0-9为船锚，T为藏宝图
    Ginfo[gid]["special"] = []
    Ginfo[gid]["time"] = time.time()

    await ruchangx(gid, uid, uname)
    blk.set_false(gid)
    await opendraw.finish(f'{uname}发起了一场亡命神抽游戏\n{uname}已自动入场')



@ruchang.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    global Ginfo
    gid = event.group_id
    uid = event.user_id
    #阻断 防止触发过快
    if blk.check(gid):
        await ruchang.finish()
    blk.set_true(gid)

    # 判断上一场是否结束
    if gid in Ginfo:
        #有这个群的数据
        if Ginfo[gid]["state"] == 0:
            #state : 未开场
            blk.set_false(gid)
            await ruchang.finish(f"请先开场、开场后会自动入场")
        if Ginfo[gid]["state"] == 2:
            #state : 已开局，未结束
            blk.set_false(gid)
            await ruchang.finish(f"上一场亡命神抽还未结束，请等待")
    else:
        #没有本群数据
        blk.set_false(gid)
        await ruchang.finish(f"请先开场、开场后会自动入场")

    # 人数判断
    if len(Ginfo[gid]["players"]) >= 5:
        blk.set_false(gid)
        await ruchang.finish(f"最多支持5名玩家")

    # 判断是否已经入场
    if uid in Ginfo[gid]["players"]:
        blk.set_false(gid)
        await ruchang.finish(f"你已入场，请勿重复操作")

    Ginfo[gid]["time"] = time.time()
    uname = event.sender.card if event.sender.card else event.sender.nickname
    blk.set_false(gid)
    await ruchangx(gid, uid, uname)
    # await ruchang.send("你已入场，请等待开局",at_sender = True)

    text = f'你已加入 {getStartUserName(gid)} 创建的亡命神抽游戏\n全部已入场的玩家：'
    for user in Ginfo[gid]["players"].values():
        text += f'\n\t·{user["uname"]}'

    #发送
    await ruchang.send(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()),at_sender = True)

# 入场 记录
async def ruchangx(gid: int, uid: int, uname: str):
    global Ginfo
    Ginfo[gid]["playerInfo"].append({
        "uname": uname,
        "uid": uid,
        "cards": {
            "M": [],
            "T": [],
            "D": [],
            "G": [],
            "C": [],
            "Y": [],
            "B": [],
            "H": [],
            "P": [],
            "Z": [],
        },
        "num": {
            "M": 0,
            "T": 0,
            "D": 0,
            "G": 0,
            "C": 0,
            "Y": 0,
            "B": 0,
            "H": 0,
            "P": 0,
            "Z": 0,
        },
        "score": 0,
        "total": 0,
        #你是真的牛逼
        "niubi": 0,
        #预留技能位
        #"skill": "",
    })
    Ginfo[gid]["players"][uid] = {
        "uname": uname,
        "uid": uid,
        "index": len(Ginfo[gid]["playerInfo"]) - 1
    }
    Ginfo[gid]["time"] = time.time()


# 开局
@kaiju.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    global Ginfo
    gid = event.group_id
    uid = event.user_id
    #阻断 防止触发过快
    if blk.check(gid):
        await kaiju.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if gid in Ginfo:
        #有这个群的数据
        if Ginfo[gid]["state"] == 0:
            #state : 未开场
            blk.set_false(gid)
            await kaiju.finish(f"请先开场、开场后等待他人入场结束后在输入")
        if Ginfo[gid]["state"] == 2:
            #state : 已开局，未结束
            blk.set_false(gid)
            await kaiju.finish(f"上一场亡命神抽还未结束，请等待")
    else:
        #没有本群数据
        blk.set_false(gid)
        await kaiju.finish(f"请先开场、开场后等待他人入场结束后在输入")

    # 判断是不是开场的人发的开局
    if Ginfo[gid]["startUid"] != uid:
        blk.set_false(gid)
        await kaiju.finish(f"开局失败\n需由创建者 {getStartUserName(gid)} 开局")

    # 判断人数够不够
    if len(Ginfo[gid]["players"]) < 2:
        blk.set_false(gid)
        await kaiju.finish(f"开局失败\n至少需要2位玩家")

    # 停止入场
    Ginfo[gid]["state"] = 2

    #根据人数算牌堆
    Ginfo[gid]["card"] = startCard(gid)
    Ginfo[gid]["drop"] = startDrop(gid)

    Ginfo[gid]["time"] = time.time()
    text = f"现已开局，无法再入场\n轮到 {getStartUserName(gid)} 的回合，请抽卡"
    blk.set_false(gid)
    await kaiju.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))



@napai.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await napai.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await napai.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await napai.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await napai.finish(f"还没轮到你呢，急什么")

    #检查是否存在特殊卡牌未结算
    if checkSpecial(gid):
        blk.set_false(gid)
        await napai.finish(f"你还有卡牌效果未使用")

    Ginfo[gid]["time"] = time.time()

    #牌库拿光了结束游戏
    if len(Ginfo[gid]["card"]) == 0:
        txt = f"牌库已抽光，游戏结束，开始结算，先结算当前回合：\n"
        txt = afterStop(gid, txt)
        txt += f"然后结算游戏结果：\n"
        txt = await end(gid, txt)
        blk.set_false(gid)
        await napai.finish(image(b64=(await text2image(txt, color="#f9f6f2", padding=10)).pic2bs4()))

    #拿牌
    cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
    dCard = Ginfo[gid]["card"][0]
    del Ginfo[gid]["card"][0]
    Ginfo[gid]["deck"].append(dCard)
    text = f"{cUser['uname']} 抽到了一张 {dCard}\n"
    text = showCard(gid, text)
    #看看爆了没
    if checkBoom(gid, dCard):
        #重置甲板状态并结束回合
        text = afterBoom(gid, text)
        text = showCollection(gid, text)
        nextTurn(gid)
        nUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
        text += f"爆炸了，回合结束。\n轮到 {nUser['uname']} 的回合，请抽卡"
        blk.set_false(gid)
        await napai.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))

    #结算海怪回合
    kraken(gid)

    #结算卡牌效果
    text = cardSkill(gid, dCard, text)

    text += f"回合继续"
    blk.set_false(gid)
    await napai.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))



@tingpai.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await tingpai.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await tingpai.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await tingpai.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await tingpai.finish(f"你想阻止别人神抽是吧")

    #检查是否存在特殊卡牌未结算
    if checkSpecial(gid):
        blk.set_false(gid)
        await tingpai.finish(f"你还有卡牌效果未使用")
    for spec in Ginfo[gid]["special"]:
        if spec[0] == "H":
            blk.set_false(gid)
            await tingpai.finish(f"海怪堵住回家的路了")

    Ginfo[gid]["time"] = time.time()

    #正常回合结算
    text = afterStop(gid, "")
    text = showCollection(gid, text)
    nextTurn(gid)
    nUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
    text += f"回合结束，轮到 {nUser['uname']} 的回合，请抽卡"

    blk.set_false(gid)
    await tingpai.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))



@jiesuan.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await jiesuan.finish()
    blk.set_true(gid)
    # 判断是否开场
    if Ginfo[gid]["state"] == 0:
        #state : 未开场
        blk.set_false(gid)
        await jiesuan.finish(f"游戏都没有创建呢")

    #超时后可以直接结束
    if  time.time() - Ginfo[gid]["time"] < 150:
        blk.set_false(gid)
        await jiesuan.finish(f"超时150秒后才能结算")

    text = f""
    if Ginfo[gid]["state"] == 2:
        #已创建并开局
        text = await end(gid, "")
    else:
        #已创建，未开局
        text = f"游戏长时间未开局，直接结束"
        # 恢复状态
        Ginfo[gid]["state"] = 0
    blk.set_false(gid)
    await jiesuan.finish(message=image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()), group_id=gid)


@paoji.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await paoji.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await paoji.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await paoji.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await paoji.finish(f"还没轮到你呢，急什么")

    #检查是否存在炮击效果
    if "P" not in Ginfo[gid]["special"]:
        blk.set_false(gid)
        await paoji.finish(f"你没有炮啊，不能开炮")

    #检查被炮击玩家是否在游戏中
    qq = get_message_at(event.json())
    if len(qq) > 0:
        qq = qq[0]
    else:
        blk.set_false(gid)
        await paoji.finish(f"你需要指定一个炮击目标玩家")
    if qq not in Ginfo[gid]["players"]:
        blk.set_false(gid)
        await paoji.finish(f"你炮击无辜路人干啥")
    if qq == uid:
        blk.set_false(gid)
        await paoji.finish(f"你疯了吗？居然对自己开炮")

    #检查炮击目标是否合法
    msg = arg.extract_plain_text().strip()
    text = f""
    if "MTDGCYBHPZ".find(msg[0]) > -1 and "1234567890".find(msg[1]) > -1:
        tar = Ginfo[gid]["playerInfo"][Ginfo[gid]["players"][qq]["index"]]
        if tar["num"][msg[0]] > 0 and tar["cards"][msg[0]][0].find(msg[0:2]) > -1:
            #炮击逻辑实现
            card = tar["cards"][msg[0]][0]
            tar["num"][msg[0]] -= 1
            tar["total"] -= 1
            del tar["cards"][msg[0]][0]
            Ginfo[gid]["special"].remove("P")
            Ginfo[gid]["drop"].append(card)
            text += f"大炮打掉了 {tar['uname']} 的 {card}\n"
            text = showCard(gid, text)
        else:
            blk.set_false(gid)
            await paoji.finish(f"你只能炮击别人战利品最上面的卡")
    else:
        blk.set_false(gid)
        await paoji.finish(f"你炮击了个啥玩意啊")

    Ginfo[gid]["time"] = time.time()

    text += f"回合继续"
    blk.set_false(gid)
    await paoji.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))


@qiangjie.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await qiangjie.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await qiangjie.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await qiangjie.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await qiangjie.finish(f"还没轮到你呢，急什么")

    #检查是否存在抢劫效果
    if "D" not in Ginfo[gid]["special"]:
        blk.set_false(gid)
        await qiangjie.finish(f"你没有刀啊，不能抢劫")

    #检查被抢劫玩家是否在游戏中
    qq = get_message_at(event.json())
    if len(qq) > 0:
        qq = qq[0]
    else:
        blk.set_false(gid)
        await qiangjie.finish(f"你需要指定一个抢劫目标玩家")
    if qq not in Ginfo[gid]["players"]:
        blk.set_false(gid)
        await qiangjie.finish(f"你抢劫无辜路人干啥")
    if qq == uid:
        blk.set_false(gid)
        await qiangjie.finish(f"你疯了吗？居然抢劫自己")

    #检查抢劫目标是否合法
    msg = arg.extract_plain_text().strip()
    text = f""
    if "MTDGCYBHPZ".find(msg[0]) > -1 and "1234567890".find(msg[1]) > -1:
        tar = Ginfo[gid]["playerInfo"][Ginfo[gid]["players"][qq]["index"]]
        cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["players"][uid]["index"]]
        if tar["num"][msg[0]] > 0 and tar["cards"][msg[0]][0].find(msg[0:2]) > -1:
            if cUser["num"][msg[0]] == 0:
                #抢劫逻辑实现
                card = tar["cards"][msg[0]][0]
                tar["num"][msg[0]] -= 1
                tar["total"] -= 1
                del tar["cards"][msg[0]][0]
                Ginfo[gid]["special"].remove("D")
                Ginfo[gid]["deck"].append(card)
                text += f"抢劫了 {tar['uname']} 的 {card} 到甲板上\n"
                text = showCard(gid, text)
                #看看爆了没
                if checkBoom(gid, card):
                    #重置甲板状态并结束回合
                    text = afterBoom(gid, text)
                    text = showCollection(gid, text)
                    nextTurn(gid)
                    nUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
                    text += f"爆炸了，回合结束。\n轮到 {nUser['uname']} 的回合，请抽卡"
                    blk.set_false(gid)
                    await qiangjie.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))
                #结算海怪回合
                kraken(gid)
                #结算卡牌效果
                text = cardSkill(gid, card, text)
            else:
                blk.set_false(gid)
                await qiangjie.finish(f"你不能抢自己已经拥有的战利品类别")
        else:
            blk.set_false(gid)
            await qiangjie.finish(f"你只能抢劫别人战利品最上面的卡")
    else:
        blk.set_false(gid)
        await qiangjie.finish(f"你抢劫了个啥玩意啊")

    Ginfo[gid]["time"] = time.time()

    text += f"回合继续"
    blk.set_false(gid)
    await qiangjie.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))


@gouqu.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await gouqu.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await gouqu.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await gouqu.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await gouqu.finish(f"还没轮到你呢，急什么")

    #检查是否存在钩取效果
    if "G" not in Ginfo[gid]["special"]:
        blk.set_false(gid)
        await gouqu.finish(f"你没有钩子啊，不能钩取")

    #检查钩取目标是否合法
    msg = arg.extract_plain_text().strip()
    text = f""
    if "MTDGCYBHPZ".find(msg[0]) > -1 and "1234567890".find(msg[1]) > -1:
        cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["players"][uid]["index"]]
        if cUser["num"][msg[0]] > 0 and cUser["cards"][msg[0]][0].find(msg[0:2]) > -1:
            #钩子逻辑实现
            card = cUser["cards"][msg[0]][0]
            cUser["num"][msg[0]] -= 1
            cUser["total"] -= 1
            del cUser["cards"][msg[0]][0]
            Ginfo[gid]["special"].remove("G")
            Ginfo[gid]["deck"].append(card)
            text += f"钩取了自己的 {card} 到甲板上\n"
            text = showCard(gid, text)
            #看看爆了没
            if checkBoom(gid, card):
                #重置甲板状态并结束回合
                text = afterBoom(gid, text)
                text = showCollection(gid, text)
                nextTurn(gid)
                nUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
                text += f"爆炸了，回合结束。\n轮到 {nUser['uname']} 的回合，请抽卡"
                blk.set_false(gid)
                await gouqu.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))
            #结算海怪回合
            kraken(gid)
            #结算卡牌效果
            text = cardSkill(gid, card, text)
        else:
            blk.set_false(gid)
            await gouqu.finish(f"你只能钩取自己战利品最上面的卡")
    else:
        blk.set_false(gid)
        await gouqu.finish(f"你钩取了个啥玩意啊")

    Ginfo[gid]["time"] = time.time()

    text += f"回合继续"
    blk.set_false(gid)
    await gouqu.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))


@wabao.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await wabao.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await wabao.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await wabao.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await wabao.finish(f"还没轮到你呢，急什么")

    #检查是否存在挖宝效果
    if "T" not in Ginfo[gid]["special"]:
        blk.set_false(gid)
        await wabao.finish(f"你没有藏宝图啊，不能挖宝")

    #检查挖宝目标是否合法
    msg = arg.extract_plain_text().strip()
    text = f""
    if "MTDGCYBHPZ".find(msg[0]) > -1 and "1234567890".find(msg[1]) > -1:
        treasure = Ginfo[gid]["treasure"]
        card = ""
        for cards in treasure:
            if cards.find(msg[0:2]) > -1:
                card = cards
        if card != "":
            #挖宝逻辑实现
            Ginfo[gid]["special"].remove("T")
            Ginfo[gid]["deck"].append(card)
            treasure.remove(card)
            while len(treasure) > 0:
                Ginfo[gid]["drop"].append(treasure[0])
                del treasure[0]
            text += f"挖到了 {card} 到甲板上\n"
            text = showCard(gid, text)
            #看看爆了没
            if checkBoom(gid, card):
                #重置甲板状态并结束回合
                text = afterBoom(gid, text)
                text = showCollection(gid, text)
                nextTurn(gid)
                nUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
                text += f"爆炸了，回合结束。\n轮到 {nUser['uname']} 的回合，请抽卡"
                blk.set_false(gid)
                await wabao.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))
            #结算海怪回合
            kraken(gid)
            #结算卡牌效果
            text = cardSkill(gid, card, text)
        else:
            blk.set_false(gid)
            await wabao.finish(f"你只能挖藏宝图显示的宝藏卡")
    else:
        blk.set_false(gid)
        await wabao.finish(f"你挖了个啥宝贝啊")

    Ginfo[gid]["time"] = time.time()

    text += f"回合继续"
    blk.set_false(gid)
    await wabao.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))


@yidong.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await yidong.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await yidong.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await yidong.finish(f"无关人员不要捣乱")

    #还没轮到他的回合
    if checkTurn(gid, uid):
        await yidong.finish(f"还没轮到你呢，急什么")

    #检查是否存在移动效果
    if "M" not in Ginfo[gid]["special"]:
        blk.set_false(gid)
        await yidong.finish(f"你没有美人鱼啊，不能移动")

    #检查移动目标是否合法
    msg = arg.extract_plain_text().strip()
    text = f""
    if "MTDGCYBHPZ".find(msg[0]) > -1 and "1234567890".find(msg[1]) > -1:
        deck = Ginfo[gid]["deck"]
        card = ""
        for cards in deck:
            if cards.find(msg[0:2]) > -1:
                card = cards
        if card != "" and card != deck[-1]:
            #移动逻辑实现
            Ginfo[gid]["special"].remove("M")
            Ginfo[gid]["deck"].remove(card)
            Ginfo[gid]["deck"].append(card)
            text += f"移动了 {card} 到甲板最右边\n"
            text = showCard(gid, text)
            #结算海怪回合
            kraken(gid)
            #结算卡牌效果
            text = cardSkill(gid, card, text)
        else:
            blk.set_false(gid)
            await yidong.finish(f"你只能移动甲板上的美人鱼前面的卡")
    else:
        blk.set_false(gid)
        await yidong.finish(f"你移动了个啥玩意啊")

    Ginfo[gid]["time"] = time.time()

    text += f"回合继续"
    blk.set_false(gid)
    await yidong.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))


@chakan.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    global Ginfo
    uid = event.user_id
    gid = event.group_id
    #阻断 防止过快
    if blk.check(gid):
        await chakan.finish()
    blk.set_true(gid)
    # 判断上一场是否结束
    if checkGroup(gid):
        await chakan.finish(f"请先开场、开局后才能玩游戏")

    #如果玩家不在列表里
    if checkPlayer(gid, uid):
        await chakan.finish(f"无关人员不要捣乱")

    text = f""
    for uid in Ginfo[gid]["players"]:
        text = showCollectionByUID(gid, uid, text)
    text += f"以上为所有玩家战利品"

    Ginfo[gid]["time"] = time.time()

    blk.set_false(gid)
    await chakan.finish(image(b64=(await text2image(text, color="#f9f6f2", padding=10)).pic2bs4()))


#游戏结束结算
async def end(gid: int, text: str):
    global Ginfo

    maxScore = 0
    for player in Ginfo[gid]["playerInfo"]:
        cards = player["cards"]
        num = player["num"]
        if num["M"] > 0:
            player["score"] += int(cards["M"][0][-1])
        if num["T"] > 0:
            player["score"] += int(cards["T"][0][-1])
        if num["D"] > 0:
            player["score"] += int(cards["D"][0][-1])
        if num["G"] > 0:
            player["score"] += int(cards["G"][0][-1])
        if num["C"] > 0:
            player["score"] += int(cards["C"][0][-1])
        if num["Y"] > 0:
            player["score"] += int(cards["Y"][0][-1])
        if num["B"] > 0:
            player["score"] += int(cards["B"][0][-1])
        if num["H"] > 0:
            player["score"] += int(cards["H"][0][-1])
        if num["P"] > 0:
            player["score"] += int(cards["P"][0][-1])
        if num["Z"] > 0:
            player["score"] += int(cards["Z"][0][-1])
        text += f"{player['uname']} 的分数为 {player['score']}"
        if player["niubi"] > 0:
            text += f"，达成亡命神抽 {player['niubi']} 次，额外奖励 {player['niubi'] * 1000} 金币\n"
            await BagUser.add_gold(player["uid"], gid, player['niubi'] * 1000)
        else:
            text += f"\n"
        if player["score"] > maxScore:
            maxScore = player["score"]
    text += f"最终获胜者为:"
    n = len(Ginfo[gid]["playerInfo"])
    for player in Ginfo[gid]["playerInfo"]:
        if player["score"] == maxScore:
            text += f" {player['uname']}"
            await BagUser.add_gold(player["uid"], gid, 50*n)
    text += f"，奖励{50*n}金币，恭喜！"

    # 恢复状态
    Ginfo[gid]["state"] = 0
    return text


# 生成初始牌组
def startCard(gid):
    global Ginfo
    card = [
        '美人鱼M1', '藏宝图T1', '弯刀D1', '钩子G1', '船锚C1', '钥匙Y1', '宝箱B1', '海怪H1', '大炮P1', '占卜球Z1',
        '美人鱼M2', '藏宝图T2', '弯刀D2', '钩子G2', '船锚C2', '钥匙Y2', '宝箱B2', '海怪H2', '大炮P2', '占卜球Z2',
        '美人鱼M3', '藏宝图T3', '弯刀D3', '钩子G3', '船锚C3', '钥匙Y3', '宝箱B3', '海怪H3', '大炮P3', '占卜球Z3',
        '美人鱼M4', '藏宝图T4', '弯刀D4', '钩子G4', '船锚C4', '钥匙Y4', '宝箱B4', '海怪H4', '大炮P4', '占卜球Z4',
        '美人鱼M6', '藏宝图T6', '弯刀D6', '钩子G6', '船锚C6', '钥匙Y6', '宝箱B6', '海怪H6', '大炮P6', '占卜球Z6',
        '美人鱼M7', '藏宝图T7', '弯刀D7', '钩子G7', '船锚C7', '钥匙Y7', '宝箱B7', '海怪H7', '大炮P7', '占卜球Z7',
        '美人鱼M8', '藏宝图T8', '弯刀D8', '钩子G8', '船锚C8', '钥匙Y8', '宝箱B8', '海怪H8', '大炮P8', '占卜球Z8',
        '美人鱼M9', '藏宝图T9', '弯刀D9', '钩子G9', '船锚C9', '钥匙Y9', '宝箱B9', '海怪H9', '大炮P9', '占卜球Z9',
    ]
    random.shuffle(card)
    #多洗几遍
    random.shuffle(card)
    end = 16 * len(Ginfo[gid]["playerInfo"])
    return card[0:end]


#生成初始弃牌堆
def startDrop(gid):
    global Ginfo
    drop = [
        '美人鱼M0', '藏宝图T0', '弯刀D0', '钩子G0', '船锚C0', '钥匙Y0', '宝箱B0', '海怪H0', '大炮P0', '占卜球Z0',
        '美人鱼M5', '藏宝图T5', '弯刀D5', '钩子G5', '船锚C5', '钥匙Y5', '宝箱B5', '海怪H5', '大炮P5', '占卜球Z5',
    ]
    random.shuffle(drop)
    end = 4 * len(Ginfo[gid]["playerInfo"])
    return drop[0:end]


#检查是否爆炸
def checkBoom(gid: int, card: str):
    global Ginfo
    isBoom = False
    for cards in Ginfo[gid]["deck"]:
        if card != cards and cards.find(card[-2]) > -1:
            isBoom = True
    return isBoom


#展示当前甲板
def showCard(gid: int, text: str):
    global Ginfo
    cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
    text += f"{cUser['uname']} 当前甲板的卡是"
    for cards in Ginfo[gid]["deck"]:
        text += f" {cards}"
    text += f"\n"
    return text


#展示当前玩家收藏
def showCollection(gid: int, text: str):
    global Ginfo
    cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
    text += f"{cUser['uname']} 当前的战利品是"
    cards = cUser["cards"]
    i = 5
    for type in cards:
        for card in cards[type]:
            if card == cards[type][0]:
                text += f" {card}"
            else:
                text += f" {card[-2:]}"
        i -= 1
        if i == 0:
            text += f"\n"
    text += f"\n"
    return text


#展示特定玩家收藏
def showCollectionByUID(gid: int, uid: int, text: str):
    global Ginfo
    user = Ginfo[gid]["playerInfo"][Ginfo[gid]["players"][uid]["index"]]
    text += f"{user['uname']} 当前的战利品是"
    cards = user["cards"]
    i = 5
    for type in cards:
        for card in cards[type]:
            if card == cards[type][0]:
                text += f" {card}"
            else:
                text += f" {card[-2:]}"
        i -= 1
        if i == 0:
            text += f"\n"
    text += f"\n"
    return text


#重置甲板状态
def nextTurn(gid):
    global Ginfo
    Ginfo[gid]["deck"] = []
    Ginfo[gid]["special"] = []
    Ginfo[gid]["treasure"] = []
    Ginfo[gid]["turn"] += 1
    if Ginfo[gid]["turn"] == len(Ginfo[gid]["players"]):
        Ginfo[gid]["turn"] = 0
        #Ginfo[gid]["round"] -= 1
        #if Ginfo[gid]["round"] == 0:
            #return True
    return False


#爆炸后回合结算
def afterBoom(gid: int, text: str):
    global Ginfo
    cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
    chuanmao = 0
    deck = Ginfo[gid]["deck"]
    for spec in Ginfo[gid]["special"]:
        if spec[0] == "C":
            chuanmao = int(spec[1])
    if chuanmao > 0:
        text += f"由于船锚的效果，{cUser['uname']} 获得了"
        n = 0
        while n < chuanmao and len(deck) > 0:
            cUser["cards"][deck[0][-2]].append(deck[0])
            cUser["num"][deck[0][-2]] += 1
            cUser["total"] += 1
            sortStrArr(cUser["cards"][deck[0][-2]])
            text += f" {deck[0]}"
            del deck[0]
            n += 1
        text += f"\n"
    while len(deck) > 0:
        Ginfo[gid]["drop"].append(deck[0])
        del deck[0]
    return text


#拿牌停牌通用状态检查
def checkSpecial(gid):
    global Ginfo
    notOK = False
    for spec in Ginfo[gid]["special"]:
        if spec[0] == "M":
            notOK = True
        if spec[0] == "D":
            notOK = True
        if spec[0] == "P":
            notOK = True
        if spec[0] == "T":
            notOK = True
        if spec[0] == "G":
            notOK = True
    return notOK


#正常回合结算
def afterStop(gid: int, text: str):
    global Ginfo
    cUser = Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]
    yaoshi = False
    baoxiang = False
    deck = Ginfo[gid]["deck"]
    n = len(deck) or 0
    if n == 10:
        cUser["niubi"] += 1
        text += f"十张大满贯！达成亡命神抽一次\n"
    for spec in Ginfo[gid]["special"]:
        if spec[0] == "Y":
            yaoshi = True
        if spec[0] == "B":
            baoxiang = True
    if yaoshi and baoxiang:
        drop = Ginfo[gid]["drop"]
        random.shuffle(drop)
        text += f"由于钥匙和宝箱的效果，{cUser['uname']} 额外获得了"
        i = 0
        while i < n and len(drop) > 0:
            cUser["cards"][drop[0][-2]].append(drop[0])
            cUser["num"][drop[0][-2]] += 1
            cUser["total"] += 1
            sortStrArr(cUser["cards"][drop[0][-2]])
            text += f" {drop[0]}"
            del drop[0]
            i += 1
        text += f"\n"
    j = 0
    text += f"{cUser['uname']} 获得了甲板上的"
    while j < n and len(deck) > 0:
        cUser["cards"][deck[0][-2]].append(deck[0])
        cUser["num"][deck[0][-2]] += 1
        cUser["total"] += 1
        sortStrArr(cUser["cards"][deck[0][-2]])
        text += f" {deck[0]}"
        del deck[0]
        j += 1
    text += f"\n"
    return text
#获得牌后特殊效果移除，游戏结束结算


#同类型卡牌排序
def sortStrArr(arr: list):
    i = 0
    n = len(arr) or 0
    while i < n - 1:
        j = 0
        while j < n - i - 1:
            if int(arr[j][-1]) < int(arr[j + 1][-1]):
                str = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = str
            j += 1
        i += 1
    return arr


#通用海怪结算
def kraken(gid):
    global Ginfo
    special = Ginfo[gid]["special"]
    i = 0
    ind = -1
    while i < len(special):
        if special[i][0] == "H":
            n = int(special[i][1])
            if n > 1:
                special[i] = "H" + str(n - 1)
            else:
                ind = i
        i += 1
    if ind > -1:
        del special[ind]
    return True


#卡牌效果判定
def cardSkill(gid: int, card: str, text: str):
    global Ginfo
    deck = Ginfo[gid]["deck"]
    special = Ginfo[gid]["special"]
    drop = Ginfo[gid]["drop"]
    treasure = Ginfo[gid]["treasure"]
    players = Ginfo[gid]["playerInfo"]
    cUser = players[Ginfo[gid]["turn"]]
    if card[-2] == "M":
        if len(deck) > 1:
            special.append("M")
            text += f"传说中的美人鱼！请选择一张甲板上的卡移到最后方\n"
        else:
            text += f"甲板无可选择目标，美人鱼也帮不到你\n"
    if card[-2] == "T":
        if len(drop) > 0:
            random.shuffle(drop)
            special.append("T")
            text += f"藏宝图发现的宝藏为"
            i = 0
            while i < 3 and len(drop) > 0:
                treasure.append(drop[0])
                text += f" {drop[0]}"
                del drop[0]
                i += 1
            text += f"请选择一张卡移到甲板上\n"
        else:
            text += f"弃牌堆无可选择目标，宝藏都被别人拿走了\n"
    if card[-2] == "D":
        canRob = False
        text += f"可以抢的战利品类别有："
        for type in cUser["num"]:
            if cUser["num"][type] == 0:
                text += f" {type}"
                for player in players:
                    if player["uid"] != cUser["uid"] and player["num"][type] > 0:
                        canRob = True
        text += f"\n"
        if canRob:
            special.append("D")
            text += f"别人屯宝你屯刀，别人的就是你的，开抢\n"
        else:
            text += f"没有值得你抢的战利品，无敌真是寂寞啊\n"
    if card[-2] == "G":
        if cUser["total"] > 0:
            special.append("G")
            text += f"钩子钩一个战利品到甲板上来\n"
        else:
            text += f"可怜的娃，都穷成这样了，钩子都用不了\n"
    if card[-2] == "C":
        bef = ""
        for spec in special:
            if spec[0] == "C":
                bef = spec
        if bef != "":
            special.remove(bef)
        special.append("C" + str(len(deck) - 1))
        text += f"船锚前面的卡牌都被保护了\n"
    if card[-2] == "Y":
        if "Y" not in special:
            special.append("Y")
        text += f"钥匙出现了！当同时有宝箱时将获得奖励\n"
    if card[-2] == "B":
        if "B" not in special:
            special.append("B")
        text += f"宝箱出现了！当同时有钥匙时将获得奖励\n"
    if card[-2] == "H":
        bef = ""
        for spec in special:
            if spec[0] == "H":
                bef = spec
        if bef != "":
            special.remove(bef)
        special.append("H2")
        text += f"海怪出现了，在它后面有两张卡之前不能回家\n"
    if card[-2] == "P":
        canBoom = False
        for player in players:
            if player["uid"] != cUser["uid"] and player["total"] > 0:
                canBoom = True
        if canBoom:
            special.append("P")
            text += f"二营长的意大利炮拉上来了，轰他丫的\n"
        else:
            text += f"没人有东西给你轰，拿去打打蚊子吧\n"
    if card[-2] == "Z":
        if len(Ginfo[gid]["card"]) > 0:
            text += f"占卜球看到牌堆下一张卡是 {Ginfo[gid]['card'][0]}\n"
        else:
            text += f"占卜球看到牌堆没牌了\n"
    return text


#通用游戏状态判断
def checkGroup(gid):
    global Ginfo
    if gid in Ginfo:
        #有这个群的数据
        if Ginfo[gid]["state"] != 2:
            #state : 未开场
            blk.set_false(gid)
            return True
    else:
        #没有本群数据
        blk.set_false(gid)
        return True
    return False


#通用玩家是否参与游戏判断
def checkPlayer(gid: int, uid: int):
    global Ginfo
    if uid not in Ginfo[gid]["players"]:
        blk.set_false(gid)
        return True
    return False


#通用玩家是否当前回合判断
def checkTurn(gid: int, uid: int):
    global Ginfo
    if uid != Ginfo[gid]["playerInfo"][Ginfo[gid]["turn"]]["uid"]:
        blk.set_false(gid)
        return True
    return False