from __future__ import annotations

import json
from pathlib import Path


LOCALIZATION_PATH = Path(__file__).resolve().parent / "localization_zh.json"


DEFAULT_TEAM_NAMES = {
    "ALG": "阿尔及利亚",
    "ARG": "阿根廷",
    "AUS": "澳大利亚",
    "AUT": "奥地利",
    "BEL": "比利时",
    "BIH": "波黑",
    "BRA": "巴西",
    "CAN": "加拿大",
    "CIV": "科特迪瓦",
    "COL": "哥伦比亚",
    "CPV": "佛得角",
    "CRO": "克罗地亚",
    "CUW": "库拉索",
    "CZE": "捷克",
    "COD": "民主刚果",
    "ECU": "厄瓜多尔",
    "EGY": "埃及",
    "ENG": "英格兰",
    "ESP": "西班牙",
    "FRA": "法国",
    "GER": "德国",
    "GHA": "加纳",
    "HAI": "海地",
    "IRN": "伊朗",
    "IRQ": "伊拉克",
    "JOR": "约旦",
    "JPN": "日本",
    "KOR": "韩国",
    "KSA": "沙特阿拉伯",
    "MAR": "摩洛哥",
    "MEX": "墨西哥",
    "NED": "荷兰",
    "NOR": "挪威",
    "NZL": "新西兰",
    "PAN": "巴拿马",
    "PAR": "巴拉圭",
    "POR": "葡萄牙",
    "QAT": "卡塔尔",
    "RSA": "南非",
    "SCO": "苏格兰",
    "SEN": "塞内加尔",
    "SUI": "瑞士",
    "SWE": "瑞典",
    "TUN": "突尼斯",
    "TUR": "土耳其",
    "URU": "乌拉圭",
    "USA": "美国",
    "UZB": "乌兹别克斯坦",
}


EXTRA_TEAM_NAMES = {
    "Bosnia and Herzegovina": "波黑",
    "Cape Verde": "佛得角",
    "Czech Republic": "捷克",
    "Czechia": "捷克",
    "Democratic Republic of the Congo": "民主刚果",
    "DR Congo": "民主刚果",
    "Ivory Coast": "科特迪瓦",
    "Côte d'Ivoire": "科特迪瓦",
    "Netherlands": "荷兰",
    "South Africa": "南非",
    "South Korea": "韩国",
    "Saudi Arabia": "沙特阿拉伯",
    "United States": "美国",
}


PLAYER_NAME_OVERRIDES = {
    "Lionel Messi": "利昂内尔·梅西",
    "Cristiano Ronaldo": "克里斯蒂亚诺·罗纳尔多",
    "Kylian Mbappé": "基利安·姆巴佩",
    "Kylian Mbappe": "基利安·姆巴佩",
    "Harry Kane": "哈里·凯恩",
    "Jude Bellingham": "裘德·贝林厄姆",
    "Vinícius Júnior": "维尼修斯·儒尼奥尔",
    "Vinicius Junior": "维尼修斯·儒尼奥尔",
    "Neymar": "内马尔",
    "Erling Haaland": "埃尔林·哈兰德",
    "Kevin De Bruyne": "凯文·德布劳内",
    "Luka Modric": "卢卡·莫德里奇",
    "Luka Modrić": "卢卡·莫德里奇",
    "Robert Lewandowski": "罗伯特·莱万多夫斯基",
    "Virgil van Dijk": "维吉尔·范戴克",
    "Bruno Fernandes": "布鲁诺·费尔南德斯",
    "Bernardo Silva": "贝尔纳多·席尔瓦",
    "Joshua Kimmich": "约书亚·基米希",
    "Kai Havertz": "凯·哈弗茨",
    "Jamal Musiala": "贾马尔·穆西亚拉",
    "Florian Wirtz": "弗洛里安·维尔茨",
    "Christian Pulisic": "克里斯蒂安·普利西奇",
    "Folarin Balogun": "福拉林·巴洛贡",
    "Son Heung-Min": "孙兴慜",
    "Heung-Min Son": "孙兴慜",
    "Takefusa Kubo": "久保建英",
    "Kaoru Mitoma": "三笘薰",
    "Takumi Minamino": "南野拓实",
    "Alexander Isak": "亚历山大·伊萨克",
    "Ryan Gravenberch": "瑞安·赫拉芬贝赫",
    "Lamine Yamal": "拉明·亚马尔",
    "Pedri": "佩德里",
    "Álvaro Morata": "阿尔瓦罗·莫拉塔",
    "Alvaro Morata": "阿尔瓦罗·莫拉塔",
    "Achraf Hakimi": "阿什拉夫·哈基米",
    "Hakim Ziyech": "哈基姆·齐耶赫",
    "Mohamed Salah": "穆罕默德·萨拉赫",
    "Sadio Mané": "萨迪奥·马内",
    "Sadio Mane": "萨迪奥·马内",
    "Luis Díaz": "路易斯·迪亚斯",
    "Luis Diaz": "路易斯·迪亚斯",
    "Guillermo Ochoa": "吉列尔莫·奥乔亚",
}


POSITION_NAMES = {
    "Goalkeeper": "门将",
    "Defender": "后卫",
    "Midfielder": "中场",
    "Forward": "前锋",
    "Attacker": "前锋",
    "G": "门将",
    "D": "后卫",
    "M": "中场",
    "F": "前锋",
}


BOARD_NAMES = {
    "goalsLeaders": "射手榜",
    "assistsLeaders": "助攻榜",
    "goalContributions": "参与进球",
    "teamGoals": "球队进球",
    "teamGoalDifference": "净胜球",
    "teamPoints": "积分榜",
    "teamWins": "胜场榜",
    "teamDefense": "防守榜",
    "teamPlayed": "比赛场次",
    "appearancesLeaders": "出场榜",
    "startsLeaders": "首发榜",
    "shotsLeaders": "射门榜",
    "shotsOnTargetLeaders": "射正榜",
    "conversionLeaders": "射门转化率",
    "foulsLeaders": "犯规榜",
    "fouledLeaders": "被犯规榜",
    "offsidesLeaders": "越位榜",
    "yellowCardsLeaders": "黄牌榜",
    "redCardsLeaders": "红牌榜",
    "savesLeaders": "扑救榜",
}


class NameLocalizer:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or LOCALIZATION_PATH
        self.teams_by_abbr: dict[str, str] = dict(DEFAULT_TEAM_NAMES)
        self.teams_by_name: dict[str, str] = dict(EXTRA_TEAM_NAMES)
        self.players_by_id: dict[str, str] = {}
        self.players: dict[str, str] = dict(PLAYER_NAME_OVERRIDES)
        self.positions: dict[str, str] = dict(POSITION_NAMES)
        self.boards: dict[str, str] = dict(BOARD_NAMES)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.teams_by_abbr.update(data.get("teams_by_abbr") or {})
        self.teams_by_name.update(data.get("teams_by_name") or {})
        self.players_by_id.update({str(key): value for key, value in (data.get("players_by_id") or {}).items()})
        self.players.update(data.get("players") or {})
        self.positions.update(data.get("positions") or {})
        self.boards.update(data.get("boards") or {})

    def team(self, name: str, abbreviation: str = "", english: bool = False) -> str:
        if english:
            return name
        return self.teams_by_abbr.get(abbreviation) or self.teams_by_name.get(name) or name

    def player(self, name: str, player_id: str = "", english: bool = False) -> str:
        if english:
            return name
        return self.players_by_id.get(str(player_id or "")) or self.players.get(name) or name

    def position(self, name: str, english: bool = False) -> str:
        if english:
            return name
        return self.positions.get(name) or name

    def board(self, key: str, fallback: str, english: bool = False) -> str:
        if english:
            return fallback
        return self.boards.get(key) or fallback
