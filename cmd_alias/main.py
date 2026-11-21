import re

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig
import astrbot.api.message_components as Comp


@register("cmd_alias", "逍遥", "指令替换", "1.4.0")
class CmdAlias(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.rules = []

        raw_rules = self.config.get("rules", "")
        if isinstance(raw_rules, str):
            lines = raw_rules.splitlines()
        elif isinstance(raw_rules, list):
            lines = [str(x) for x in raw_rules]
        else:
            lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 正则规则：行首 re: 开头，例如 re:^[Yy][Ss](.*)=ys\1
            is_regex = line.lower().startswith("re:")
            if is_regex:
                line = line[3:].strip()

            # 支持 = 或 → 作为分隔符
            if "=" in line:
                left, _, dst = line.partition("=")
            elif "→" in line:
                left, _, dst = line.partition("→")
            else:
                continue
            left = left.strip()
            dst = dst.strip()
            if not left or not dst:
                continue

            if is_regex:
                try:
                    pattern = re.compile(left)
                except re.error:
                    # 非法正则直接跳过，不影响其他规则
                    continue
                self.rules.append({"kind": "regex", "pattern": pattern, "dst": dst})
            else:
                self.rules.append({"kind": "prefix", "src": left, "dst": dst})

    def _rewrite(self, event: AstrMessageEvent, new_text: str):
        msg_obj = event.message_obj
        msg_obj.message_str = new_text

        # 同步改写消息链里的 Plain 文本，保留 At/Image 等其他段
        chain = list(msg_obj.message or [])
        plain_idx = None
        for i, seg in enumerate(chain):
            if isinstance(seg, Comp.Plain):
                plain_idx = i
                break
        if plain_idx is not None:
            chain[plain_idx] = Comp.Plain(text=new_text)
        else:
            chain.insert(0, Comp.Plain(text=new_text))
        msg_obj.message = chain

    @filter.event_message_type(filter.EventMessageType.ALL, priority=99)
    async def alias_replace(self, event: AstrMessageEvent):
        raw = event.get_message_str().strip()
        if not raw:
            return

        for rule in self.rules:
            if rule["kind"] == "prefix":
                if raw.startswith(rule["src"]):
                    rest = raw[len(rule["src"]):]
                    new_text = f"{rule['dst']}{rest}"
                    self._rewrite(event, new_text)
                    return
            else:
                m = rule["pattern"].search(raw)
                if m:
                    try:
                        new_text = m.expand(rule["dst"])
                    except re.error:
                        continue
                    self._rewrite(event, new_text)
                    return
