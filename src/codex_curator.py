"""Curated local classifier produced by Codex for this library.

It intentionally consumes only title, artist, album and release date.  QQ Music's
language, genre and tag fields are not used here.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from src.ai_classifier import AI_CATEGORIES


PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "codex_artist_profiles.json"


def _names(text):
    return {item.strip() for item in text.split("\n") if item.strip()}


# These are deliberately explicit identity decisions, not character/language guesses.
CHINESE_FEMALE = _names("""
王菲
孙燕姿
蔡健雅
G.E.M. 邓紫棋
田馥甄
梁静茹
BY2
杨丞琳
刘惜君
S.H.E
单依纯
卫兰
弦子
王心凌
郭采洁
徐佳莹
蔡依林
戴佩妮
莫文蔚
陈绮贞
温岚
张惠妹
王诗安
范玮琪
张韶涵
刘瑞琦
郭静
叶蒨文
丁芙妮
A-Lin
张靓颖
孙盛希
容祖儿
连诗雅
梁咏琪
林忆莲
金海心
印子月
洪佩瑜
林依晨
江语晨
薛凯琪
袁娅维TIA RAY
冯曦妤
Dizzy Dizzo (蔡诗芸)
范晓萱
张玉华
郁可唯
吴雨霏
谢安琪
张碧晨
张含韵
Twins
陈洁仪
泳儿
陈慧琳
任然
欧阳娜娜
汪佩蓉
金莎
王菀之
家家
Cannie
炎明熹
刘若英
陈婧霏
张悬
何洁
芮恩
魏如萱
卓文萱
蔡淳佳
孙燕姿/蔡健雅
AGA/李幸倪
陈粒
黄绮珊
萧亚轩
哥哥妹妹
黄淑惠
很美味
蔡宥绮
陈卓璇
元若蓝
习谱予
不靠谱组合
魏如昀
邓福如 AFÜ
小霞
蔡依林/周杰伦
Lara梁心颐
王若琳
一口甜
孟庭苇
邓丽君
阿桑
任素汐
窦靖童
五月天/陈绮贞
林忆莲/蓝战士
顺子
许哲珮
丁丁
祁紫檀
陈冠蒨
陈依依
Lara梁心颐/JZN
唐艾萱
关诗敏
陈佩贤 Jesslyn
七朵组合
徐俊雅
曹方
莲莉rei
万玲琳
梁静茹/卢广仲
吳卓源
李幸倪
张敬轩
王唯旖
房祖名/龚芝怡
黑Girl
许靖韵
JOYCE 就以斯
李想Evelyn
DreamBeach梦想海滩/邹沛沛
周笔畅
方大同/薛凯琪
King Sis
蓝又时
孙盛希/sunkis 宋秉勤
彭佳慧
本兮
许嵩/刘美麟
林子琪
林凡Freya
房东的猫/戴羽彤
卓文萱/曹格
徐怀钰
孟慧圆
徐怀钰/任贤齐
关心妍
杨千嬅
吴芊仪
邓丽欣/方力申
陶喆/袁娅维TIA RAY
黄晨晨
可楼
Sugar
陶喆/蔡依林
温岚/JZN
南拳妈妈/JZN
锦绣二重唱
Power Milk
Maggie_麦吉
Gifty
陈韵若/陈每文
范玮琪/MC HotDog 热狗
许慧欣
阿肆
阿肆/徐佳莹
戚薇
元若蓝/大Q秉洛
王俞匀
Ella陈嘉桦/苏打绿
树莉莉 Serrini
邓福如 AFÜ/费聿锋
龚芝怡/房祖名
莫文蔚/窦靖童
何璐
吴若希
二珂
泳儿/per se
泳儿/海鸣威
林俊杰/蔡宥绮
姚贝娜
杨紫
张杰/戴佩妮
T.R.Y
梁玉莹
朱彦安/张诗莉
谢沛恩
Faye 詹雯婷
F.I.R.飞儿乐团/彭佳慧
孙燕姿/仓木麻衣 (くらき まい)
陈柏宇/冯曦妤
曾轶可
阿肆/郭采洁
薛凯琪/方大同
萧萧
康士坦的变化球/郭采洁
金玟岐
高姗
谭维维
邓丽欣
华语群星
房东的猫
张韶涵/上海彩虹室内合唱团
方雅贤
陈壹千
First Aid Kit
奚缘
A Fine Frenzy
单依纯/Eric周兴哲
G.E.M. 邓紫棋/Eric周兴哲
张杰/张碧晨
G.E.M. 邓紫棋/张靓颖
张小斐
那英
蔡依林/G.E.M. 邓紫棋
CoCo李玟/G.E.M. 邓紫棋
蔡依林/田馥甄
Sweety
Twins/Boy'z
吴雨霏/周柏豪
寒/五熊
冯提莫
王蓝茵
棉花糖
卢巧音
温岚/周杰伦
刘惜君/李鑫一
薛之谦/刘惜君
容祖儿/林俊杰
范玮琪/张韶涵
纳豆nado
王菲/那英
许茹芸
王俊凯/蔡依林
苏运莹
""")

CHINESE_MALE = _names("""
周杰伦
陶喆
林俊杰
王力宏
方大同
陈奕迅
许嵩
五月天
周传雄
Tank
卢广仲
周柏豪
韦礼安
蛋堡
Eric周兴哲
后弦
张震岳
张杰
汪苏泷
吴青峰
张学友
赵雷
王杰
萧敬腾
薛之谦
伍佰 & China Blue
李玖哲
阿杜
汪苏泷/BY2
周杰伦/袁咏琳
丁世光
李荣浩
胡彦斌
八三夭乐团
焦迈奇
林宥嘉
回音哥
伍佰
梁博
林志炫
陈鸿宇
方大同/徐佳莹
五月天/陈绮贞
徐良
胡歌
逃跑计划
五月天 阿信
潘玮柏
MC HotDog 热狗
罗志祥
张震岳/MC HotDog 热狗/侯佩岑
曹格
林宇中/林俊杰
齐秦
孙子涵
王力宏/欧阳靖/李岩
余佳运
沈以诚
告五人
吴克群
李克勤
古巨基
五月天/萧敬腾
胡彦斌/单依纯
五月天/G.E.M. 邓紫棋
徐佳莹/伍佰
迪克牛仔
Gibb-Z/ICE杨长青
五月天/孙燕姿
林俊杰/孙燕姿
林俊杰/藤原浩 (藤原ヒロシ)
汪苏泷/炎亚纶
张震岳/蔡健雅
TFBOYS/嘻游记
谭咏麟
五月天/陈绮贞
陈奕迅/eason and the duo band
3Bangz
林峯
郝云
贰佰
任贤齐
海鸣威/吴琼
陶喆/卢广仲
刘昊霖/Kidult.
上海彩虹室内合唱团
五月天/萧敬腾
五月天 阿信
林俊杰/孙燕姿
王力宏/章子怡
梁静茹/严爵
潘玮柏/苏芮
蛋堡/方大同
蛋堡/阎韦伶
房祖名/龚芝怡
方大同/薛凯琪
潘玮柏/G.E.M. 邓紫棋/艾热AIR
许嵩/黄龄
许嵩/莫诗旎
许嵩/刘美麟
陶喆/蔡依林
陶喆/袁娅维TIA RAY
龚芝怡/房祖名
""")

CHINESE_GROUP = _names("""
BY2
S.H.E
南拳妈妈
五月天
阿福Fuzzi
F.I.R.飞儿乐团
苏打绿
Fine乐团
Twins
哥哥妹妹
不靠谱组合
八三夭乐团
七朵组合
后海大鲨鱼
牛奶咖啡
黑Girl
DreamBeach梦想海滩/邹沛沛
房东的猫
棉花糖
上海彩虹室内合唱团
逃跑计划
Sweety
Twins/Boy'z
TFBOYS/嘻游记
华语群星
告五人
T.R.Y
F.I.R.飞儿乐团/彭佳慧
陈奕迅/eason and the duo band
康士坦的变化球/郭采洁
""")

# Second-pass identities found while reviewing the generated library.  Keeping
# these explicit avoids turning Chinese/Japanese characters into a language rule.
CHINESE_FEMALE.update(_names("""
梁雨恩
英雄联盟/G.E.M. 邓紫棋
韩雪
单依纯/王力宏
LaLa徐佳瑩FM
曾沛慈
段奥娟
汪小敏
张叶蕾
郑融/周柏豪
Olivia Ong
郭静/韦礼安
阿达娃/法老
花玲/喵酱油/宴宁/Kinsen
曲锦楠
郁欢
苏菲
ai mini
棉子
沙总啊
"""))

CHINESE_MALE.update(_names("""
王绎龙
单依纯/王力宏
崔健
YELLOW黄宣
Gareth.T
郑融/周柏豪
郭静/韦礼安
阿达娃/法老
花玲/喵酱油/宴宁/Kinsen
陈忠义
BEYOND
"""))

CHINESE_GROUP.update(_names("""
BEYOND
Mi2
ai mini
"""))

WESTERN_FEMALE = _names("""
Taylor Swift
Avril Lavigne
Billie Eilish
Olivia Rodrigo
Ariana Grande
Bic Runga
Corrinne May
Lady Gaga
Lenka
Carly Rae Jepsen
Christina Aguilera
Jamelia
Miley Cyrus
Jewel
Fefe Dobson
Marcela Mangabeira
Selena Gomez & The Scene
Agnes Obel
Tonya Mitchell
t.A.T.u.
Little Birdy
Play
Dido
Maggie Reilly
Adele
Jennifer Lopez
Tamia
Kesha
Britney Spears
Gracie Abrams
Azure Ray
Toni Braxton
Mariah Carey
Luisa Sobral
Noah Cyrus
Shannon Hurley
Enya
Juice Newton
Carpenters
Jane & The Boy
Olive Marie
Ina Wroldsen
Taylor Swift/Lana Del Rey
Vanille
Lola Marsh
The Pussycat Dolls
Ava Max
Taylor Swift/Bon Iver
Alicia Keys
Jessica Mauboy
Ingrid Michaelson
Em Beihold
Mae Stephens
Tessa Violet
Miranda Cosgrove
Sweet California
Natasha Thomas
M2M
Sasha Alex Sloan/Charlie Puth
Taylor Swift/The Chicks
First Aid Kit
A Fine Frenzy
Taylor Swift/Ed Sheeran/Future
Taylor Swift/Lana Del Rey
Taylor Swift/The Chicks
Hillary Scott & The Scott Family
MADILYN
PJ Harvey
""")

WESTERN_FEMALE.update(_names("""
M2M
Glee Cast/Amber Riley
Ariana Grande/Iggy Azalea
Seraphine/Jasmine Clarke/Absofacto
Babyface/Mariah Carey/Kenny G/Sheila E.
Owl City/Carly Rae Jepsen
Owl City/Britt Nicole
Eminem/Rihanna
Shawn Mendes/Camila Cabello
Jocelyn Pook/Russian Red
Darren Korb/Ashley Barrett
Glen Hansard/Marketa Irglova
Hugh Grant/Drew Barrymore
Nostalghia/Tyler Bates/Joel J. Richard
Elena Johnson
"""))

# Narrow styles are intentionally positive lists, curated from the actual tracks.
JAZZ_HIPHOP_ARTISTS = _names("""
Nujabes (せば じゅん)/Shing02 (安念真吾)
Nujabes (せば じゅん)/Fat Jon
Nujabes (せば じゅん)
Shing02 (安念真吾)
Cradle/Nieve & Cook
Cradle Orchestra (クレイドル・オーケストラ)
Hidetake Takayama
Hidetake Takayama/Amanda Silvera/Matt Brevner
Hidetake Takayama/Stacy Epps/Toby
西原健一郎 (Kenichiro Nishihara)
西原健一郎 (Kenichiro Nishihara)/Loumina
西原健一郎 (Kenichiro Nishihara)/Substantial
西原健一郎 (Kenichiro Nishihara)/Tamala (塔玛拉)
Robert de Boron (ロベルト・デ・ボロン)/Daichi Diez/Shaira
DJ Deckstream
FLY COAST/二宮愛 (にのみや あい)
Nieve/Ine
시로스카이 (Shirosky)
""")

INDIE_ROCK_ARTISTS = _names("""
Oasis
Radiohead
The Cure
bôa
LOVE PSYCHEDELICO (爱的魔幻)
后海大鲨鱼
Half Moon Run
Nirvana
Blur
PJ Harvey
The Middle East
康士坦的变化球/郭采洁
""")

INDIE_POP_ARTISTS = _names("""
陈绮贞
陈婧霏
张悬
陈粒
魏如萱
窦靖童
Agnes Obel
Azure Ray
Tennis
曹方
万玲琳
祁紫檀
别野加奈
別野加奈
First Aid Kit
The Middle East
房东的猫
阿肆
阿肆/徐佳莹
阿肆/林宥嘉
阿肆/郭采洁
曾轶可
Lola Marsh
Tessa Violet
Vanille
""")

INDIE_POP_ARTISTS.update(_names("""
Humbert Humbert (ハンバート ハンバート)
ラッキーオールドサン (LUCKY OLD SUN)
nishina (にしな)
Fine乐团
"""))

INDIE_ROCK_ARTISTS.update(_names("""
ヨルシカ (Yorushika)
あたらよ (Atarayo)
苏打绿
告五人
"""))

DREAM_ARTISTS = _names("""
bôa
Salyu (森绫子)
Azure Ray
Agnes Obel
Enya
Mazzy Star
Pink Floyd
新居昭乃 (あらい あきの)
麗美 (Remedios)
別野加奈
陈婧霏
窦靖童
Let's Eat Grandma
""")

CITY_POP_ARTISTS = _names("""
竹内まりや (竹内玛利亚)
BLU-SWING (ブルー・スウィング)
Special Favorite Music (スペシャル・フェイバリット・ミュージック)
cinnamons/evening cinema
Furui Riho
""")

URBAN_RNB_ARTISTS = _names("""
陶喆
方大同
孙盛希
袁娅维TIA RAY
王诗安
丁世光
小霞
李玖哲
王若琳
吳卓源
YELLOW黄宣
顺子
Alicia Keys
Tamia
Toni Braxton
Babyface/Mariah Carey/Kenny G/Sheila E.
Mariah Carey
The Weeknd
MALIYA/Ryohu (呂布)
King Sis
""")

BALLAD_ROCK_ARTISTS = _names("""
Green Day
伍佰 & China Blue
伍佰
逃跑计划
BEYOND
Led Zeppelin
Pink Floyd
Eagles
Chicago
Plain White T's
Liam Gallagher
""")

Y2K_ARTISTS = _names("""
M2M
Britney Spears
t.A.T.u.
Play
The Pussycat Dolls
Kesha
Lady Gaga
""")

Y2K_TRACKS = _names("""
BY2::发呆
BY2::Because Of You (Guitar Ver.)
BY2::Because Of You (Piano Ver.)
BY2::不够成熟
BY2::爱上你
BY2::红蜻蜓
BY2::爱的双重魔力
BY2::好好爱^0^ (甜蜜真实版)
BY2::好好爱^0^ (心动时刻版)
BY2::这叫爱
BY2::我知道
BY2::爱丫爱丫
BY2::DNA
S.H.E::天灰
S.H.E::热带雨林
S.H.E::紫藤花
S.H.E::候鸟
S.H.E::河滨公园
S.H.E::五月天
S.H.E::Super Star
S.H.E::触电
S.H.E::白色恋歌
S.H.E::天使在唱歌
S.H.E::不想长大
S.H.E::恋人未满
王心凌::当你
王心凌::Honey
王心凌::彩虹的微笑
王心凌::花的嫁纱
王心凌::睫毛弯弯
王心凌::爱你
王心凌::梦的光点
王心凌::第一次爱的人
蔡依林::Love Love Love
蔡依林::爱情三十六计
蔡依林::马德里不思议 (Live)
蔡依林::你怎么连话都说不清楚
蔡依林::日不落
蔡依林::就是爱
蔡依林::说爱你
Twins::梨涡浅笑
Twins::恋爱大过天
Twins::星光游乐园
Twins::莫斯科没有眼泪
Sweety::樱花草
黑Girl::123木头人
Avril Lavigne::Complicated
Avril Lavigne::Girlfriend (Clean)
Avril Lavigne::My Happy Ending
Avril Lavigne::Don't Tell Me (Explicit)
Christina Aguilera::Infatuation
Jamelia::Superstar
Natasha Thomas::Skin Deep
Miranda Cosgrove::Kissin U
""")

BALLAD_ROCK_TRACKS = _names("""
Oasis::Don't Look Back in Anger (Remastered)
Oasis::Don't Look Back in Anger
Oasis::Champagne Supernova
Oasis::I'm Outta Time
Oasis::Stand by Me
Oasis::Live Forever (Remastered)
Coldplay::The Scientist
Coldplay::Yellow
五月天::知足 (07 最知足版)
五月天::步步
五月天::转眼
五月天::温柔
五月天::如烟
F.I.R.飞儿乐团::刺鸟
F.I.R.飞儿乐团::我们​​的爱
F.I.R.飞儿乐团::我们的爱
F.I.R.飞儿乐团::Lydia
F.I.R.飞儿乐团::月牙湾
Avril Lavigne::Adia (Live)
Avril Lavigne::The Scientist (Live)
Avril Lavigne::Innocence
Avril Lavigne::Fly
Avril Lavigne::Remember When
Avril Lavigne::Wish You Were Here
Avril Lavigne::Wish You Were Here (Explicit)
Avril Lavigne::Tomorrow
Avril Lavigne::My Happy Ending
Avril Lavigne::Everybody Hurts
Avril Lavigne::When You're Gone
Queen::Somebody To Love
Queen::Love Of My Life
Glen Hansard/Marketa Irglova::Falling Slowly
Måneskin::If I Can Dream
Fine乐团::没有人不比我快乐
Fine乐团::配不上你
八三夭乐团::想见你想见你想见你
告五人::唯一
迪克牛仔::三万英尺
""")

DREAM_TRACKS = _names("""
王菲::无常
王菲::邮差
王菲::当时的月亮
王菲::享受
王菲::一半
王菲::分裂
王菲::暗涌 (Live)
王菲::暗涌
王菲::闷
王菲::脸
王菲::色诫
王菲::开到荼蘼
王菲::讨好自己
王菲::怀念 (Live)
王菲::推翻 (Live)
王菲::百年孤寂 (Live)
王菲::玩具
王菲::梦中人 (Live)
王菲::梦游 (Live)
Radiohead::No Surprises
The Cure::To The Sky
Billie Eilish::everything i wanted
Billie Eilish::Six Feet Under
Taylor Swift/Lana Del Rey::Snow On The Beach (Explicit)
NewJeans (뉴진스)::Ditto
Heize (헤이즈)/韩秀智 (한수지)::Round and round
nishina (にしな)::夜間飛行
""")

URBAN_RNB_TRACKS = _names("""
王力宏::公转自转
王力宏::你不在
王力宏::Kiss Goodbye
王力宏::春雨里洗过的太阳
王力宏::爱在哪里
王力宏::心跳
王力宏::我们的歌
王力宏::需要人陪
王力宏::爱错
王力宏::爱错 (Live)
王力宏::爱的就是你
Ariana Grande::Honeymoon Avenue
Ariana Grande::the boy is mine (Explicit)
Justin Timberlake::Cry Me a River
Jamelia::Superstar
卫兰::心乱如麻 + My Cookie Can (Live)
卫兰::心乱如麻
卫兰::街灯晚餐
卫兰::退
卫兰::My Cookie Can
卫兰::一格格
AGA/李幸倪::一加一
AGA/李幸倪::独一无二
宇多田光 (宇多田ヒカル)::Prisoner Of Love
宇多田光 (宇多田ヒカル)::First Love
Utada (宇多田光)::Come Back To Me (Radio Edit)
Utada (宇多田光)::Come Back To Me
青山黛玛 (青山テルマ)/SoulJa::はなさないでよ (别离开我)
青山黛玛 (青山テルマ)/SoulJa::そばにいるね (留在我身边)
加藤ミリヤ (加藤米莉亚)::Paradise
加藤ミリヤ (加藤米莉亚)::You don't know me
3rd Coast (써드코스트)::My Jealousy (Original ver)
Crush (크러쉬)::Beautiful
NewJeans (뉴진스)::Ditto
Furui Riho::Candle Light (Furui Riho Billboard Live Tour -Do What Makes You Happy-)
""")

URBAN_RNB_EXCLUDE = _names("""
陶喆::黑色柳丁
陶喆::讨厌红楼梦 (Live)
陶喆::王八蛋
""")

# QQ album dates can point at compilations/remasters.  These are well-known
# originals or covers whose representative work year is unambiguous.
ORIGINAL_YEAR_OVERRIDES = {
    "A Fine Frenzy::Almost Lover": 2007,
    "Natasha Thomas::Skin Deep": 2004,
    "Plain White T's::Hey There Delilah": 2006,
    "Chicago::If You Leave Me Now": 1976,
    "Eagles::加州旅馆 (Live)": 1976,
    "The Rolling Stones::Wild Horses": 1971,
    "Babyface/Mariah Carey/Kenny G/Sheila E.::Every Time I Close My Eyes": 1996,
    "Bee Gees::How Deep Is Your Love (From \"Saturday Night Fever\" Soundtrack)": 1977,
    "Bill Withers::Just the Two of Us": 1981,
    "Eric Clapton::Wonderful Tonight": 1977,
    "Europe::The Final Countdown": 1986,
    "Gerry Rafferty::Baker Street": 1978,
    "Gilbert O'Sullivan::Alone Again (Naturally)": 1972,
    "Gilbert O' Sullivan::Alone Again Naturally": 1972,
    "Herman's Hermits::The End Of The World": 1963,
    "Juice Newton::Angel Of The Morning (Single Version)": 1981,
    "Ozzy Osbourne::Goodbye To Romance (2002 Version)": 1980,
    "Pink Floyd::Wish You Were Here (2011 - Remaster)": 1975,
    "王菲::梦醒了 (Live)": 1998,
    "王菲::天空 (Live)": 1994,
    "王菲::怀念 (Live)": 1997,
    "王菲::推翻 (Live)": 1999,
    "王菲::百年孤寂 (Live)": 1999,
    "王菲::棋子 (Live)": 1994,
    "王菲::梦中人 (Live)": 1994,
    "王菲::梦游 (Live)": 1994,
    "王菲::执迷不悔 (Live)": 1993,
    "陶喆::Run Away (Live)": 2002,
    "陶喆::讨厌红楼梦 (Live)": 2002,
    "陶喆::二十二 (Live)": 2002,
    "单依纯::Dear Friend (Live)": 1999,
    "单依纯::天空 (Live)": 1994,
    "单依纯::下雨天 (Live)": 2008,
    "单依纯::给电影人的情书": 2008,
    "G.E.M. 邓紫棋::你不是真正的快乐": 2008,
}

DEEP_NIGHT_ARTISTS = _names("""
王菲
蔡健雅
田馥甄
梁静茹
卫兰
陈奕迅
陈绮贞
莫文蔚
戴佩妮
林忆莲
洪佩瑜
Billie Eilish
Radiohead
The Cure
张悬
陈粒
陈婧霏
小霞
窦靖童
阿桑
吴雨霏
谢安琪
王菀之
Mazzy Star
Agnes Obel
Azure Ray
Lene Marlin
蔡淳佳
林宥嘉
梁博
陈鸿宇
刘若英
树莉莉 Serrini
李幸倪
""")


def _year(date):
    match = re.match(r"(19|20)\d{2}", str(date or ""))
    return int(match.group(0)) if match else None


_VERSION_BLOCK = re.compile(
    r"\s*[（(][^（）()]*?(?:live|remaster|version|ver\.?|taylor.?s version|现场|版本|版|"
    r"acoustic|piano|guitar|explicit|album)[^（）()]*?[）)]",
    re.IGNORECASE,
)


def _canonical_work(title):
    """Fold obvious live/remaster variants without consulting platform tags."""
    value = _VERSION_BLOCK.sub("", str(title or ""))
    return re.sub(r"\s+", " ", value).strip().casefold()


def _add(scores, reasons, category, confidence, reason):
    if category not in AI_CATEGORIES:
        return
    if confidence > scores.get(category, 0):
        scores[category] = confidence
        reasons[category] = reason


class CodexMusicCurator:
    model = "codex-local-curator"
    VERSION = "codex-curator-v1"

    @property
    def prompt_version(self):
        source = Path(__file__).read_bytes()
        return f"{self.VERSION}:{hashlib.sha256(source).hexdigest()[:12]}"

    def classify(self, song, release_date="", effective_year=None):
        artist = str(song.get("singer", "")).strip()
        title = str(song.get("name", "")).strip()
        album = str(song.get("album", "")).strip()
        raw_year = _year(release_date)
        year = effective_year or raw_year
        scores, reasons = {}, {}

        if artist in CHINESE_FEMALE:
            _add(scores, reasons, "华语女声", .96, "Codex 已识别为华语女性艺人或女子组合")
        if artist in CHINESE_MALE:
            _add(scores, reasons, "华语男声", .96, "Codex 已识别为华语男性艺人或男子组合")
        if artist in CHINESE_GROUP:
            _add(scores, reasons, "华语乐队与组合", .97, "Codex 已识别为固定华语乐队或演唱组合")
        if artist in WESTERN_FEMALE:
            _add(scores, reasons, "欧美女声", .96, "Codex 已识别为欧美女性艺人或女子组合")

        is_chinese = artist in CHINESE_FEMALE or artist in CHINESE_MALE or artist in CHINESE_GROUP
        is_western = artist in WESTERN_FEMALE or artist in {
            "Oasis", "The Beatles", "Shawn Mendes", "Green Day", "Coldplay", "Queen",
            "Radiohead", "The Cure", "John Lennon", "Weezer", "Pink Floyd", "Nirvana",
            "Blur", "Ed Sheeran", "Bruno Mars", "The Weeknd", "Westlife", "Bee Gees",
            "Maroon 5/Wiz Khalifa", "Justin Bieber/Sean Kingston", "Justin Bieber/Various Artists",
            "Justin Timberlake", "Justin Timberlake/Carey Mulligan/Stark Sands", "Sam Smith/A$AP Rocky",
            "Lewis Capaldi", "Måneskin", "Led Zeppelin", "Ozzy Osbourne", "AC/DC", "Eagles",
            "Chicago", "Eric Clapton", "Europe", "Plain White T's", "Liam Gallagher",
            "The Rolling Stones", "One-T", "Diddy - Dirty Money", "Ye (侃爷)",
            "Ye (侃爷)/Paul McCartney", "Lil Tjay", "Adam Lambert", "Gerry Rafferty",
        }

        year_basis = "同艺人同作品的最早可比版本" if raw_year and year != raw_year else "发行日期"
        if year and 2000 <= year <= 2009 and is_chinese:
            _add(scores, reasons, "千禧华语", .94, f"{year_basis}为 {year} 年且作品属于华语音乐")
        if year and 1990 <= year <= 1999 and is_chinese:
            _add(scores, reasons, "90 年代华语", .94, f"{year_basis}为 {year} 年且作品属于华语音乐")
        if year and 2000 <= year <= 2009 and is_western:
            _add(scores, reasons, "千禧欧美", .94, f"{year_basis}为 {year} 年且作品属于欧美音乐")

        key = f"{artist}::{title}"

        if artist in JAZZ_HIPHOP_ARTISTS:
            _add(scores, reasons, "爵士嘻哈", .93, "该作品属于明确的 Jazz Rap / 爵士采样嘻哈脉络")
        if artist in INDIE_POP_ARTISTS:
            _add(scores, reasons, "独立流行", .84, "艺人与作品具有明确的独立流行创作审美")
        if artist in INDIE_ROCK_ARTISTS:
            _add(scores, reasons, "独立摇滚", .86, "艺人与作品处于明确的独立/另类摇滚脉络")
        if artist in CITY_POP_ARTISTS:
            _add(scores, reasons, "City Pop", .9, "作品具有明确的日本都市流行编曲与审美")
        if artist in DREAM_ARTISTS or key in DREAM_TRACKS:
            _add(scores, reasons, "梦幻迷幻", .79, "作品以氛围化、朦胧或迷幻质感见长")
        if (artist in URBAN_RNB_ARTISTS and key not in URBAN_RNB_EXCLUDE) or key in URBAN_RNB_TRACKS:
            _add(scores, reasons, "都市 R&B", .84, "艺人与作品具有成熟 R&B / Neo-Soul 都市律动")
        if artist in BALLAD_ROCK_ARTISTS or key in BALLAD_ROCK_TRACKS:
            _add(scores, reasons, "抒情摇滚", .78, "作品由摇滚编制承载明显的旋律与情感抒发")
        if (artist in Y2K_ARTISTS and year and 1999 <= year <= 2009) or key in Y2K_TRACKS:
            _add(scores, reasons, "Y2K 氛围", .83, "发行年代与 Teen Pop / 早期数码千禧审美明确吻合")
        if artist in DEEP_NIGHT_ARTISTS:
            _add(scores, reasons, "深夜情绪", .8, "作品整体适合低照度、克制或沉浸式夜间聆听")

        # Track-level corrections where the artist's whole catalogue is too broad.
        if key in {
            "伍佰 & China Blue::夏夜晚风", "伍佰::夏夜晚风", "五月天::如烟",
            "Green Day::Wake Me Up When September Ends", "Green Day::21 Guns",
            "Coldplay::The Scientist", "Coldplay::Yellow", "Oasis::Don't Look Back in Anger",
            "Oasis::Don't Look Back in Anger (Remastered)", "Avril Lavigne::My Happy Ending",
            "Avril Lavigne::When You're Gone", "BEYOND::无悔这一生", "逃跑计划::一万次悲伤",
        }:
            _add(scores, reasons, "抒情摇滚", .94, "该曲以摇滚编制和递进动态承载强旋律抒情")
        if key in {
            "王菲::暗涌", "王菲::百年孤寂 (Live)", "王菲::开到荼蘼", "王菲::梦游 (Live)",
            "陈婧霏::逝去的海", "陈婧霏::晚风", "Mazzy Star::Look On Down From The Bridge",
            "Radiohead::No Surprises", "bôa::Duvet", "bôa::Duvet (Acoustic)",
            "新居昭乃 (あらい あきの)::きれいな感情", "麗美 (Remedios)::Platform",
        }:
            _add(scores, reasons, "梦幻迷幻", .92, "该曲具有明确的朦胧声场、漂浮感或梦幻摇滚质地")
        if key == "竹内まりや (竹内玛利亚)::Plastic Love":
            _add(scores, reasons, "City Pop", .99, "日本 City Pop 代表作品")
        if key in {
            "蛋堡::收敛水", "蛋堡::I Want You", "蛋堡::少年维持着烦恼", "蛋堡::关于小熊",
            "蛋堡/方大同::写一首歌", "蛋堡/阎韦伶::偷偷", "陈冠希/陈奂仁/胡蓓蔚/MC仁::战争",
        }:
            _add(scores, reasons, "爵士嘻哈", .82, "说唱表达与爵士/灵魂采样和声形成核心听感")
        if any(token in title for token in ("夜", "失眠", "寂寞", "孤独", "雨", "月", "晚风")):
            if artist in DEEP_NIGHT_ARTISTS or artist in DREAM_ARTISTS or artist in INDIE_POP_ARTISTS:
                _add(scores, reasons, "深夜情绪", .87, "歌曲意象与克制氛围适合深夜沉浸聆听")

        categories = [name for name in AI_CATEGORIES if name in scores]
        overall = round(min((scores[name] for name in categories), default=0), 2)
        # Empty means it genuinely misses all 16 curatorial playlists, not necessarily an error.
        needs_review = not categories
        if not categories:
            uncertainty = "该作品未明确命中当前 16 个策展歌单"
        else:
            uncertainty = ""
        return {
            "categories": categories,
            "confidence": {"overall": overall, "by_category": {k: round(v, 2) for k, v in scores.items()}},
            "reasons": reasons,
            "evidence": [f"codex:{name}:{reasons[name]}" for name in categories],
            "needs_review": needs_review,
            "uncertainty_reason": uncertainty,
            "source": "codex",
            "model": self.model,
            "prompt_version": self.prompt_version,
            "input_evidence": {
                "name": title,
                "singer": artist,
                "album": album,
                "release_date": str(release_date or ""),
                "effective_year": year,
            },
        }

    def classify_all(self, songs, metadata_cache):
        earliest_year = {}
        for song in songs:
            mid = str(song.get("mid", ""))
            year = _year(metadata_cache.get(mid, {}).get("release_date", ""))
            if not year:
                continue
            work_key = (str(song.get("singer", "")).strip(), _canonical_work(song.get("name", "")))
            earliest_year[work_key] = min(year, earliest_year.get(work_key, year))

        return {
            str(song["mid"]): self.classify(
                song,
                metadata_cache.get(str(song["mid"]), {}).get("release_date", ""),
                ORIGINAL_YEAR_OVERRIDES.get(
                    f"{str(song.get('singer', '')).strip()}::{str(song.get('name', '')).strip()}",
                    earliest_year.get(
                        (str(song.get("singer", "")).strip(), _canonical_work(song.get("name", "")))
                    ),
                ),
            )
            for song in songs
        }
