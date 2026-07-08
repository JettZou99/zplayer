"""
有道词典 API 翻译服务 + 单词提取工具。

提供：
- TranslationResult: 翻译结果数据模型
- YoudaoTranslator: 有道词典 API 调用（含内存缓存）
- lemmatize: 词形还原（将变形词转为原型）
- extract_words: 从字幕文本提取英文单词
- normalize_query_word: 标准化单词用于 API 查询
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# 数据模型
# ------------------------------------------------------------------ #


@dataclass
class TranslationResult:
    """单次翻译查询的结构化结果。"""

    word: str
    us_phonetic: str | None = None
    uk_phonetic: str | None = None
    definitions: list[tuple[str, str]] = field(default_factory=list)
    # definitions: [(词性, 释义), ...] 如 [("vt.", "认出，识别；承认")]

    @property
    def is_empty(self) -> bool:
        """是否为空结果（未找到释义）。"""
        return not self.definitions and not self.us_phonetic and not self.uk_phonetic

    def to_dict(self) -> dict:
        """转为 dict，供 QThread 信号传递（避免 Qt 信号对自定义类的限制）。"""
        return {
            "word": self.word,
            "us_phonetic": self.us_phonetic,
            "uk_phonetic": self.uk_phonetic,
            "definitions": [list(d) for d in self.definitions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> TranslationResult:
        """从 dict 恢复实例。"""
        defs = [tuple(d_item) for d_item in d.get("definitions", [])]
        return cls(
            word=d["word"],
            us_phonetic=d.get("us_phonetic"),
            uk_phonetic=d.get("uk_phonetic"),
            definitions=defs,
        )

    @classmethod
    def empty(cls, word: str) -> TranslationResult:
        """创建空结果。"""
        return cls(word=word)


# ------------------------------------------------------------------ #
# 有道词典翻译器
# ------------------------------------------------------------------ #


class YoudaoTranslator:
    """
    有道词典 API 翻译器。

    使用公开的 jsonapi 端点，无需 API Key。
    内置类级内存缓存避免重复请求。
    """

    _API_URL = "https://dict.youdao.com/jsonapi"
    _TIMEOUT = 5  # 秒
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    _CACHE: dict[str, TranslationResult] = {}
    _CACHE_MAX = 500

    @classmethod
    def translate(cls, word: str) -> TranslationResult:
        """
        查询单词翻译。

        1. 检查缓存
        2. 构建 URL，发送 GET 请求
        3. 解析 JSON 响应
        4. 缓存结果并返回

        异常时返回空 TranslationResult（不抛异常）。
        """
        query = normalize_query_word(word)
        if not query:
            return TranslationResult.empty(word)

        # 尝试词形还原，查询原型词
        lemma = lemmatize(query)
        cache_key = lemma if lemma != query else query

        # 缓存命中
        if cache_key in cls._CACHE:
            logger.debug("翻译缓存命中: %s (原词: %s)", cache_key, query)
            result = cls._CACHE[cache_key]
            # 返回时显示用户输入的词（便于识别）
            result.word = word
            return result

        # 构建 URL（使用原型词查询，获得更准确的结果）
        url = f"{cls._API_URL}?q={urllib.parse.quote(lemma)}"
        logger.info("查询有道词典: %s (原词: %s)", lemma, query)

        try:
            req = urllib.request.Request(url, headers=cls._HEADERS)
            with urllib.request.urlopen(req, timeout=cls._TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
        except urllib.error.URLError as exc:
            logger.warning("网络请求失败: %s -> %s", lemma, exc)
            raise TranslationError(f"网络请求失败: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            logger.warning("JSON 解析失败: %s -> %s", lemma, exc)
            raise TranslationError("翻译服务返回了无效数据") from exc
        except Exception as exc:
            logger.warning("翻译查询异常: %s -> %s", lemma, exc)
            raise TranslationError(f"翻译查询失败: {exc}") from exc

        result = cls._parse_response(data, word)
        cls._cache_result(lemma, result)
        return result

    @classmethod
    def _parse_response(cls, data: dict, original_word: str) -> TranslationResult:
        """
        防御式解析有道 JSON 响应。

        优先使用 individual.trs（结构化的词性+释义），
        备选 ec.word[0].trs[0].tr[0].l.i[0] (单字符串释义)。
        """
        us_phone = cls._extract_phonetic(data, "usphone")
        uk_phone = cls._extract_phonetic(data, "ukphone")
        definitions = cls._extract_definitions(data)

        return TranslationResult(
            word=original_word,
            us_phonetic=us_phone,
            uk_phonetic=uk_phone,
            definitions=definitions,
        )

    @staticmethod
    def _extract_phonetic(data: dict, key: str) -> str | None:
        """从 simple.word[0] 或 ec.word[0] 中提取音标。"""
        # 尝试 simple.word[0][key]
        try:
            simple_word = data.get("simple", {}).get("word", [])
            if simple_word and simple_word[0].get(key):
                return simple_word[0][key]
        except (IndexError, AttributeError, TypeError):
            pass

        # 备选 ec.word[0][key]
        try:
            ec_word = data.get("ec", {}).get("word", [])
            if ec_word and ec_word[0].get(key):
                return ec_word[0][key]
        except (IndexError, AttributeError, TypeError):
            pass

        return None

    @staticmethod
    def _extract_definitions(data: dict) -> list[tuple[str, str]]:
        """
        提取释义列表。

        优先 individual.trs (结构化 [{pos, tran}])
        备选 ec.word[0].trs[0].tr[0].l.i[0] (单字符串)
        """
        definitions: list[tuple[str, str]] = []

        # 优先: individual.trs
        try:
            individual_trs = data.get("individual", {}).get("trs", [])
            for tr_entry in individual_trs:
                pos = tr_entry.get("pos", "") or ""
                tran = tr_entry.get("tran", "") or ""
                if tran:
                    definitions.append((pos, tran))
        except (AttributeError, TypeError):
            pass

        if definitions:
            return definitions

        # 备选: ec.word[0].trs[0].tr[0].l.i[0]
        try:
            ec_word = data.get("ec", {}).get("word", [])
            if ec_word:
                trs = ec_word[0].get("trs", [])
                if trs:
                    tr_list = trs[0].get("tr", [])
                    if tr_list:
                        i_list = tr_list[0].get("l", {}).get("i", [])
                        if i_list and isinstance(i_list[0], str):
                            raw_def = i_list[0]
                            # 尝试从 "v. 认识，辨别出..." 中分离词性和释义
                            pos, tran = _split_pos_and_tran(raw_def)
                            definitions.append((pos, tran))
        except (IndexError, AttributeError, TypeError):
            pass

        return definitions

    @classmethod
    def _cache_result(cls, key: str, result: TranslationResult) -> None:
        """缓存翻译结果，控制缓存大小。"""
        if len(cls._CACHE) >= cls._CACHE_MAX:
            # 简单淘汰：弹出最早的项
            oldest_key = next(iter(cls._CACHE))
            del cls._CACHE[oldest_key]
        cls._CACHE[key] = result

    @classmethod
    def clear_cache(cls) -> None:
        """清空翻译缓存。"""
        cls._CACHE.clear()


# ------------------------------------------------------------------ #
# 异常
# ------------------------------------------------------------------ #


class TranslationError(Exception):
    """翻译过程中的可预期错误。"""


# ------------------------------------------------------------------ #
# 词形还原（Lemmatization）
# ------------------------------------------------------------------ #

# 不规则动词/形容词/名词的原型映射表（常用词）
_IRREGULAR_FORMS = {
    # 不规则动词过去式/过去分词 -> 原型
    "became": "become", "become": "become",
    "began": "begin", "begun": "begin",
    "bought": "buy", "brought": "bring",
    "built": "build",
    "chose": "choose", "chosen": "choose",
    "came": "come",
    "did": "do", "done": "do",
    "drew": "draw", "drawn": "draw",
    "drank": "drink", "drunk": "drink",
    "drove": "drive", "driven": "drive",
    "ate": "eat", "eaten": "eat",
    "fell": "fall", "fallen": "fall",
    "felt": "feel", "found": "find",
    "flew": "fly", "flown": "fly",
    "forgot": "forget", "forgotten": "forget",
    "froze": "freeze", "frozen": "freeze",
    "got": "get", "gotten": "get",
    "gave": "give", "given": "give",
    "went": "go", "gone": "go",
    "grew": "grow", "grown": "grow",
    "had": "have", "has": "have",
    "heard": "hear",
    "held": "hold",
    "knew": "know", "known": "know",
    "left": "leave",
    "lay": "lie", "lain": "lie", "lied": "lie",
    "led": "lead",
    "lent": "lend",
    "let": "let",
    "laid": "lay",
    "made": "make",
    "meant": "mean",
    "met": "meet",
    "paid": "pay",
    "put": "put",
    "read": "read",
    "rode": "ride", "ridden": "ride",
    "rang": "ring", "rung": "ring",
    "rose": "rise", "risen": "rise",
    "ran": "run", "run": "run",
    "said": "say",
    "saw": "see", "seen": "see",
    "sold": "sell",
    "sent": "send",
    "set": "set",
    "shook": "shake", "shaken": "shake",
    "shot": "shoot",
    "showed": "show", "shown": "show",
    "shut": "shut",
    "sang": "sing", "sung": "sing",
    "sat": "sit",
    "slept": "sleep",
    "spoke": "speak", "spoken": "speak",
    "spent": "spend",
    "stood": "stand",
    "stole": "steal", "stolen": "steal",
    "swept": "sweep",
    "swam": "swim", "swum": "swim",
    "took": "take", "taken": "take",
    "taught": "teach",
    "tore": "tear", "torn": "tear",
    "told": "tell",
    "thought": "think",
    "threw": "throw", "thrown": "throw",
    "understood": "understand",
    "woke": "wake", "woken": "wake",
    "wore": "wear", "worn": "wear",
    "won": "win",
    "wrote": "write", "written": "write",
    # 不规则比较级/最高级 -> 原型
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    "more": "much",
    "most": "much",
    "farther": "far", "farthest": "far",
    "further": "far", "furthest": "far",
    # 不规则名词复数 -> 原型
    "children": "child",
    "feet": "foot",
    "geese": "goose",
    "men": "man",
    "mice": "mouse",
    "people": "person",
    "teeth": "tooth",
    "women": "woman",
}


def lemmatize(word: str) -> str:
    """
    将英文单词的词形变化还原为原型。

    处理顺序（从最具体到最通用）：
    1. 不规则词形映射表
    2. -ies → -y（countries → country）
    3. -ied → -y（studied → study）
    4. -es（watches → watch, boxes → box）
    5. -s（排除特殊词：this, us, etc.；至少3个字母）
    6. -ing（running → run, making → make）
    7. -ed（walked → walk, loved → love）
    8. -er（faster → fast, nicer → nice；至少4个字母）
    9. -est（fastest → fast, nicest → nice；至少6个字母）

    Returns:
        还原后的原型词（小写）
    """
    if not word:
        return word

    w = word.lower().strip()

    # 1. 不规则词形映射表
    if w in _IRREGULAR_FORMS:
        return _IRREGULAR_FORMS[w]

    # 2. -ies → -y（名词复数、动词第三人称）
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"

    # 3. -ied → -y（动词过去式，以-y结尾的动词：studied → study）
    if w.endswith("ied") and len(w) > 3:
        return w[:-3] + "y"

    # 4. -es（动词第三人称、名词复数）
    if w.endswith("es") and len(w) > 2:
        candidate = w[:-2]
        if len(candidate) > 1:
            return candidate

    # 5. -s（动词第三人称、名词复数，排除特殊词，至少3个字母才去掉-s）
    if w.endswith("s") and len(w) > 2:
        if w in ("this", "is", "us", "was", "has", "does", "goes"):
            return w
        candidate = w[:-1]
        if len(candidate) > 1:
            return candidate

    # 6. -ing（现在分词/动名词）
    if w.endswith("ing") and len(w) > 3:
        base = w[:-3]
        # 双写辅音：running → run, sitting → sit
        if len(base) > 1 and base[-1] == base[-2] and base[-1] not in "aeiou":
            return base[:-1]
        # 以不发音的e结尾的词去e加-ing：making → make, writing → write
        # 还原时尝试加回e
        candidate = base + "e"
        # 简单启发：如果base不以e结尾，且加e后看起来像英文单词，返回加e版本
        if not base.endswith("e") and len(base) <= 3:
            return candidate
        return base

    # 7. -ed（过去式/过去分词）
    if w.endswith("ed") and len(w) > 2:
        base = w[:-2]
        # 双写辅音：stopped → stop
        if len(base) > 1 and base[-1] == base[-2] and base[-1] not in "aeiou":
            return base[:-1]
        # 以不发音的e结尾的词去e加-ed：loved → love, used → use
        candidate = base + "e"
        if not base.endswith("e") and len(base) <= 3:
            return candidate
        return base

    # 8. -er（比较级，至少4个字母才处理，避免误判 her → h）
    if w.endswith("er") and len(w) > 3:
        base = w[:-2]
        if len(base) > 1 and base[-1] == base[-2] and base[-1] not in "aeiou":
            return base[:-1]
        # 以不发音的e结尾：nicer → nice
        candidate = base + "e"
        if not base.endswith("e") and len(base) <= 3:
            return candidate
        return base

    # 9. -est（最高级，至少6个字母才处理，避免误判 test → t）
    if w.endswith("est") and len(w) > 5:
        base = w[:-3]
        if len(base) > 1 and base[-1] == base[-2] and base[-1] not in "aeiou":
            return base[:-1]
        # 以不发音的e结尾：nicest → nice
        candidate = base + "e"
        if not base.endswith("e") and len(base) <= 3:
            return candidate
        return base

    return w


# ------------------------------------------------------------------ #
# 单词提取工具
# ------------------------------------------------------------------ #

# 匹配英文单词（含缩写如 don't、连字符如 state-of-the-art）
_WORD_PATTERN = re.compile(r"[a-zA-Z]+(?:['-][a-zA-Z]+)*")


def extract_words(text: str) -> list[str]:
    """
    从字幕文本中提取英文单词。

    规则:
    - 匹配英文字母序列，保留撇号(')和连字符(-)
    - 过滤纯数字、空字符串、纯标点
    - 去重但保序

    Returns:
        原始大小写的单词列表
    """
    if not text:
        return []

    matches = _WORD_PATTERN.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for word in matches:
        lower = word.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(word)
    return result


def normalize_query_word(word: str) -> str:
    """
    将 UI 显示的单词标准化为 API 查询词。

    规则:
    - 去首尾标点和空白
    - 转小写（API 不区分大小写）
    - 尝试词形还原（supports -> support, testing -> test）

    Examples:
        "Hello," -> "hello"
        "don't" -> "don't"
        "supports" -> "support"
        "testing" -> "test"
    """
    if not word:
        return ""

    # 去首尾非字母字符
    stripped = word.strip().strip(".,!?;:\"'()[]{}""''")
    w = stripped.lower()

    # 尝试词形还原
    lemma = lemmatize(w)
    return lemma


def _split_pos_and_tran(raw: str) -> tuple[str, str]:
    """
    从 "v. 认识，辨别出..." 中分离词性和释义。

    如果没有词性前缀，返回 ("", raw)。
    """
    # 匹配开头的词性标记: "v." "n." "vt." "vi." "adj." "adv." "prep." "conj." "pron."
    match = re.match(r"^(vt\.|vi\.|v\.|n\.|adj\.|adv\.|prep\.|conj\.|pron\.|aux\.|num\.|art\.)\s*(.*)", raw)
    if match:
        return match.group(1), match.group(2)
    return "", raw
