from __future__ import annotations

import json as _json
import platform
import re
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RAW_PATH = Path(".mcp/rules_raw.json")
COMPILED_JSON = Path(".mcp/rules_compiled.json")
COMPILED_MD = Path(".mcp/rules_compiled.md")
SUGGESTIONS_MD = Path(".mcp/rules_suggestions.md")


@dataclass
class Source:
    file: str
    line: int


@dataclass
class RuleItem:
    key: str
    value: Any
    text: str
    source: Source
    severity: str = "must"  # must/should
    # Optional conditions parsed from tags like [env:container] [ide:vscode] [os:windows|linux|darwin]
    conditions: dict[str, list[str]] | None = None


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    yield f
        elif p.is_file():
            yield p


_TEXT_EXT = {".md", ".txt", ".rst"}
_YAML_EXT = {".yaml", ".yml"}
_JSON_EXT = {".json"}


def _parse_text_file(path: Path) -> list[RuleItem]:
    items: list[RuleItem] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return items  # nosec B110 - unreadable file yields no items
    in_code = False
    for i, line in enumerate(lines, 1):
        t = line.strip()
        if not t:
            continue
        # 跳过 Markdown 代码块内容（``` 开/闭）
        if t.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # 提取条件标签并清洗文本
        conds, clean = _extract_conditions(t)
        # 仅解析条目风格的行（列表/编号/短句）
        if re.match(r"^(?:[-*] |\d+\.|[•·] )", clean) or len(clean) < 160:
            mapped = _interpret_policy(clean)
            for key, val in mapped.items():
                items.append(
                    RuleItem(
                        key=key,
                        value=val,
                        text=clean,
                        source=Source(str(path), i),
                        conditions=(conds or None),
                    ),
                )
    return items


def _extract_conditions(text: str) -> tuple[dict[str, list[str]], str]:
    """Extract condition tags from text and return (conditions, clean_text).

    Supported tags: [env:container], [ide:vscode], [os:windows|linux|darwin]
    Multiple values can be separated by comma or '|'. Unknown tags are ignored.
    """
    conds: dict[str, list[str]] = {}
    clean = text
    # Find all [key:value] tags
    pattern = re.compile(r"\[(\w+):([^\]]+)\]")
    for m in list(pattern.finditer(text)):
        key = m.group(1).strip().lower()
        vals = [v.strip().lower() for v in re.split(r"[|,]", m.group(2)) if v.strip()]
        if key in {"env", "ide", "os"} and vals:
            conds.setdefault(key, [])
            for v in vals:
                if v not in conds[key]:
                    conds[key].append(v)
        # remove this tag from clean text
        clean = clean.replace(m.group(0), "").strip()
    # normalize whitespace
    clean = re.sub(r"\s+", " ", clean)
    return conds, clean


def _interpret_policy(text: str) -> dict[str, Any]:
    t = text.lower()
    out: dict[str, Any] = {}

    # 覆盖率（模块/核心）
    # 先匹配“核心”关键词（即便不含“覆盖率/%”也可提取），否则再匹配覆盖率/百分号
    # 辅助：上/下限关键词
    # 下限关键词（避免与上限短语冲突，例如“不超过/ no more than”）
    lower_kw_1 = r"(>=|≥|不少于|不低于|至少|no\s+less\s+than|not\s+less\s+than|at\s+least|>|大于|高于)"
    lower_kw_2 = r"(?<!不)超过|(?<!not\s)greater\s+than|(?<!no\s)(?<!not\s)more\s+than|(?<!no\s)(?<!not\s)(over|above)"
    has_lower_kw = bool(re.search(lower_kw_1, t) or re.search(lower_kw_2, t))
    has_upper_kw = bool(
        re.search(
            r"(<=|<|≤|不高于|不超过|至多|at\s+most|no\s+more\s+than|not\s+more\s+than|less\s+than|under|below)",
            t,
        ),
    )

    # 明确的覆盖率上下文（避免仅因出现 % 就误判）
    # 视为覆盖率语境：出现“覆盖率/coverage/核心/core”任一关键词
    mentions_cov = (
        ("coverage" in t) or ("覆盖率" in t) or ("core" in t) or ("核心" in t)
    )
    # 近阈值/窗口语境：不要将其当作 min_*（例如 within 3% / 近阈值 3% / coverage-near）
    near_ctx = bool(
        re.search(r"within\s+\d+(?:\.\d+)?\s*%", t)
        or re.search(r"近阈值|距阈值|coverage-near|near\s+threshold|阈值窗口|窗口", t),
    )
    # 下限语境提示（保留，可用于后续权重或提示；当前不强制要求）
    # 已不直接使用，仅预留注释（避免未使用变量告警）

    perc = _extract_percentage(t)
    # 放宽语义：当明确是覆盖率语境且不存在“仅上限”关键词时，
    # 将裸百分比默认解释为最低阈值（min），以兼容常见简写“覆盖率 90%”。
    if perc is not None and mentions_cov and not near_ctx:
        # 若仅出现上限关键词且无下限关键词，则不设置 min（避免误判）
        if not (has_upper_kw and not has_lower_kw):
            if any(k in t for k in ["core", "核心"]):
                out["coverage.min_core"] = max(0.0, min(1.0, float(perc) / 100.0))
            else:
                out["coverage.min_module"] = max(0.0, min(1.0, float(perc) / 100.0))

    # 解析上限（不作门禁，仅做建议/元信息）：<= / < / 不高于/不超过/至多 / at most / no more than / less than / under / below
    mmax = re.search(
        r"(?:<=|<|≤|不高于|不超过|至多|at\s+most|no\s+more\s+than|not\s+more\s+than|less\s+than|under|below)\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)?",
        t,
    )
    if mmax:
        try:
            vmax = float(mmax.group(1))
            key = (
                "coverage.max_core"
                if ("core" in t or "核心" in t)
                else "coverage.max_module"
            )
            out[key] = max(0.0, min(1.0, vmax / 100.0))
        except Exception:
            pass  # nosec B110 - percent parsing failure ignored
    else:
        # 英文词数值：例如 "at most ninety five percent" / "no more than ninety percent"
        mmaxw = re.search(
            r"(?:at\s+most|no\s+more\s+than|not\s+more\s+than|less\s+than|under|below)\s+([a-z\s-]+?)\s*percent",
            t,
        )
        if mmaxw:
            valw = _english_words_to_int(mmaxw.group(1))
            if valw is not None:
                key = (
                    "coverage.max_core"
                    if ("core" in t or "核心" in t)
                    else "coverage.max_module"
                )
                out[key] = max(0.0, min(1.0, float(valw) / 100.0))

    # 区间 between X and Y（英文）
    mbt = re.search(
        r"between\s+(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)?\s+and\s+(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)?",
        t,
    )
    if mbt and mentions_cov and not near_ctx:
        try:
            v1 = float(mbt.group(1))
            v2 = float(mbt.group(2))
            vmin, vmax = min(v1, v2), max(v1, v2)
            if "core" in t or "核心" in t:
                out["coverage.min_core"] = max(0.0, min(1.0, vmin / 100.0))
                out["coverage.max_core"] = max(0.0, min(1.0, vmax / 100.0))
            else:
                out["coverage.min_module"] = max(0.0, min(1.0, vmin / 100.0))
                out["coverage.max_module"] = max(0.0, min(1.0, vmax / 100.0))
        except Exception:
            pass  # nosec B110 - between-range parse failure ignored
    # 区间 介于/在 X 和/到 Y 之间（中文）
    mbtc = re.search(
        r"(?:介于|在)\s*(\d{1,3}(?:\.\d{1,2})?)\s*%?\s*(?:和|到)\s*(\d{1,3}(?:\.\d{1,2})?)\s*%?\s*(?:之间)?",
        t,
    )
    if mbtc and mentions_cov and not near_ctx:
        try:
            v1 = float(mbtc.group(1))
            v2 = float(mbtc.group(2))
            vmin, vmax = min(v1, v2), max(v1, v2)
            if "core" in t or "核心" in t:
                out["coverage.min_core"] = max(0.0, min(1.0, vmin / 100.0))
                out["coverage.max_core"] = max(0.0, min(1.0, vmax / 100.0))
            else:
                out["coverage.min_module"] = max(0.0, min(1.0, vmin / 100.0))
                out["coverage.max_module"] = max(0.0, min(1.0, vmax / 100.0))
        except Exception:
            pass

    # 禁止 skip/xfail
    if any(
        k in t
        for k in [
            "no skip",
            "禁止 skip",
            "禁止跳过",
            "不允许跳过",
            "xfail",
            "skip/xfail",
        ]
    ):
        out["test.no_skip_xfail"] = True

    # 警告视为错误
    if "-w error" in t or "warnings as errors" in t or ("警告" in t and "错误" in t):
        out["test.warnings_as_errors"] = True

    # 变异测试
    if any(k in t for k in ["mutmut", "mutatest", "mutation test", "变异测试"]):
        out["test.mutation_required"] = True

    # TDD/顺序执行（记录偏好，不做冲突计算）
    if any(k in t for k in ["tdd", "测试先行", "红-绿-重构", "红—绿—重构"]):
        out["dev.tdd"] = True
    if any(
        k in t
        for k in ["按顺序", "不得跳跃", "禁止跳跃", "严格按顺序", "no skipping steps"]
    ):
        out["process.strict_order"] = True

    # 安全与密钥扫描
    if any(
        k in t
        for k in [
            "secret",
            "secrets",
            "密钥",
            "凭据",
            "gitleaks",
            "detect-secrets",
            "secretlint",
        ]
    ):
        out["security.secrets_scan"] = True
    if any(k in t for k in ["sast", "静态安全", "严格安全扫描", "security strict"]):
        out["security.sast_strict"] = True

    # 容器/镜像策略
    if any(k in t for k in ["docker", "容器化", "容器", "devcontainer", "dockerfile"]):
        out["container.required"] = True
    if any(k in t for k in ["镜像基线", "image baseline", "rootless", "nonroot"]):
        out["container.policy.baseline"] = True

    # 性能预算（提取毫秒）
    if any(k in t for k in ["性能预算", "performance budget", "响应时间", "latency"]):
        perc = _extract_percentage(t)
        # 若出现诸如 "< 200ms" 或 "小于200ms"
        m = re.search(r"(\d{2,5})\s*ms", t)
        if m:
            out["perf.budget_ms"] = int(m.group(1))

    # CI/分支/提交规范
    if any(k in t for k in ["ci 必须通过", "require ci", "ci required"]):
        out["ci.required"] = True
    if any(k in t for k in ["conventional commits", "约定式提交", "提交规范"]):
        out["vcs.conventional_commits"] = True
    if any(
        k in t for k in ["trunk-based", "主干开发", "gitflow", "git flow", "分支策略"]
    ):
        # 简化：仅标识存在分支策略约束
        out["vcs.branch_policy"] = True

    return out


def _extract_percentage(text: str) -> float | None:
    # 纯数字 + %
    m = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*%", text)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    # 不等式+数字（中文/符号）
    m2 = re.search(
        r"(>=|≥|不少于|不低于|至少|no\s+less\s+than|not\s+less\s+than|at\s+least)\s*(\d{1,3}(?:\.\d{1,2})?)",
        text,
    )
    if m2:
        try:
            return float(m2.group(2))
        except Exception:
            return None
    # 英文 percent：如 95 percent
    m3 = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*percent", text)
    if m3:
        try:
            return float(m3.group(1))
        except Exception:
            return None
    # 百分之 + 中文数字：百分之九十五
    m4 = re.search(r"百分之\s*([一二三四五六七八九十百零]+)", text)
    if m4:
        val = _chinese_numeral_to_int(m4.group(1))
        if val is not None:
            return val
    # 不少于/至少 + 中文数字（需语境包含'覆盖率'或'核心'）；也支持口语“九成/十成/九成五”等
    if "覆盖率" in text or "core" in text or "核心" in text or "coverage" in text:
        # 先处理“成”，包括可选的小数位：九成五 -> 95%
        m7b = re.search(
            r"([一二三四五六七八九十两])\s*成\s*([一二三四五六七八九两])",
            text,
        )
        if m7b:
            a = _chinese_numeral_to_int(m7b.group(1))
            b = _chinese_numeral_to_int(m7b.group(2))
            if a is not None and b is not None:
                return min(100, a * 10 + b)
        m7 = re.search(r"([一二三四五六七八九十两]{1,2})\s*成", text)
        if m7:
            val = _chinese_numeral_to_int(m7.group(1))
            if val is not None:
                return min(100, (val * 10 if val <= 10 else val))
        m5 = re.search(
            r"(不少于|不低于|至少)\s*([一二三四五六七八九十百零两]{1,6})",
            text,
        )
        if m5:
            val = _chinese_numeral_to_int(m5.group(2))
            if val is not None:
                return val
        # 兜底：直接跟随中文数字（如“覆盖率 一百零一”）
        m5b = re.search(
            r"(?:覆盖率|core|核心|coverage)\s*([一二三四五六七八九十百零两]{1,6})",
            text,
        )
        if m5b:
            val = _chinese_numeral_to_int(m5b.group(1))
            if val is not None:
                return val
    # 英文数字词 + percent：优先匹配含前缀，再匹配通用
    m6a = re.search(
        r"(?:no\s+less\s+than|not\s+less\s+than|at\s+least)\s+([a-z\s-]+?)\s*percent",
        text,
    )
    if m6a:
        val = _english_words_to_int(m6a.group(1))
        if val is not None:
            return val
    m6b = re.search(r"([a-z\s-]+?)\s*percent", text)
    if m6b:
        val = _english_words_to_int(m6b.group(1))
        if val is not None:
            return val

    return None


def _chinese_numeral_to_int(s: str) -> int | None:
    digits = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if s == "一百":
        return 100
    # 处理十、九十、九十五 等
    if "十" in s:
        parts = s.split("十")
        if parts[0] == "":  # 十五
            tens = 1
        else:
            tens = digits.get(parts[0], 0)
        units = 0
        if len(parts) > 1 and parts[1] != "":
            units = digits.get(parts[1], 0)
        return tens * 10 + units
    # 处理一百零一等形式
    if "百" in s:
        parts = s.split("百")
        hundreds = digits.get(parts[0] or "一", 1) * 100
        rest = parts[1] if len(parts) > 1 else ""
        rest = rest.replace("零", "")
        if not rest:
            return hundreds
        # 支持 十/九/二十/二十五 等
        if rest == "十":
            return hundreds + 10
        if rest.endswith("十") and len(rest) == 2:
            return hundreds + digits.get(rest[0], 0) * 10
        if rest.startswith("十"):
            return hundreds + 10 + (digits.get(rest[1], 0) if len(rest) > 1 else 0)
        # 单位数
        return hundreds + digits.get(rest, 0)
    # 单个数字：九、八
    if len(s) == 1 and s in digits:
        return digits[s]
    # 九五（不常见，忽略）
    return None


def _english_words_to_int(s: str) -> int | None:
    words = s.strip().lower().replace("-", " ").split()
    if not words:
        return None
    mapping = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
    }
    total = 0
    i = 0
    while i < len(words):
        w = words[i]
        if w == "and":
            i += 1
            continue
        if w not in mapping:
            if w in ("coverage", "core"):
                i += 1
                continue
            return None
        val = mapping[w]
        if val == 100:
            # assume previous number times 100 (only support 'one hundred')
            total = max(1, total) * 100
        else:
            total += val
        i += 1
    if total < 0:
        return None
    if total > 100:
        total = 100
    return total


def _parse_yaml_json(path: Path) -> list[RuleItem]:
    import yaml  # type: ignore[import-untyped]  # lazy

    items: list[RuleItem] = []
    try:
        if path.suffix in _YAML_EXT:
            data = yaml.safe_load(path.read_text(encoding="utf-8", errors="ignore"))
        else:
            import json as _json

            data = _json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return items

    flat = _flatten_kv(data)
    for k, v in flat.items():
        items.append(
            RuleItem(key=k, value=v, text=f"{k}: {v}", source=Source(str(path), 1)),
        )
    return items


def _flatten_kv(d: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten_kv(v, key))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            key = f"{prefix}.{i}" if prefix else str(i)
            out.update(_flatten_kv(v, key))
    else:
        out[prefix] = d
    return out


def ingest(paths: list[str], project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    pths = [Path(p) if Path(p).is_absolute() else (root / p) for p in paths]
    # Deterministic ordering: ensure stable, lexicographic processing so that
    # first-seen values are consistent across runs (e.g., prefer 'a.yaml' over 'b.yaml').
    files = sorted(_iter_files(pths), key=lambda f: str(f).lower())
    # 轻量缓存：.mcp/rules_ingest_cache.json 基于 mtime/size
    cache_path = root / ".mcp/rules_ingest_cache.json"
    cache: dict[str, Any] = {}
    if cache_path.exists():
        try:
            cache = _json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    items: list[RuleItem] = []
    for f in files:
        if f.suffix.lower() in _TEXT_EXT:
            use_cache = False
            try:
                st = f.stat()
                try:
                    data_bytes = f.read_bytes()
                except Exception:
                    data_bytes = b""
                import hashlib

                sig_hash = hashlib.sha256(data_bytes).hexdigest()
                sig = f"{int(getattr(st,'st_mtime_ns', int(st.st_mtime*1e9)))}-{st.st_size}-{sig_hash}"
                rec = (
                    (cache.get("files") or {}).get(str(f))
                    if isinstance(cache.get("files", {}), dict)
                    else None
                )
                if (
                    isinstance(rec, dict)
                    and rec.get("sig") == sig
                    and isinstance(rec.get("items"), list)
                ):
                    for it in rec["items"]:
                        try:
                            items.append(
                                RuleItem(**{**it, "source": Source(**it["source"])}),
                            )
                            use_cache = True
                        except Exception:
                            use_cache = False
                            break
            except Exception:
                use_cache = False
            if not use_cache:
                parsed = _parse_text_file(f)
                items.extend(parsed)
                # 写缓存
                try:
                    cache.setdefault("files", {})
                    if isinstance(cache["files"], dict):
                        st = f.stat()
                        try:
                            data_bytes = f.read_bytes()
                        except Exception:
                            data_bytes = b""
                        import hashlib

                        sig_hash = hashlib.sha256(data_bytes).hexdigest()
                        sig = f"{int(getattr(st,'st_mtime_ns', int(st.st_mtime*1e9)))}-{st.st_size}-{sig_hash}"
                        cache["files"][str(f)] = {
                            "sig": sig,
                            "items": [asdict(i) for i in parsed],
                        }
                except Exception:
                    pass  # nosec B110 - cache write best-effort
        elif f.suffix.lower() in _YAML_EXT | _JSON_EXT:
            items.extend(_parse_yaml_json(f))

    raw = {"items": [asdict(i) for i in items], "files": [str(f) for f in files]}
    (root / RAW_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / RAW_PATH).write_text(
        _json.dumps(raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 落盘缓存
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache["version"] = 1
        cache_path.write_text(
            _json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass  # nosec B110 - cache write best-effort
    comp = compile_rules(project_root=root)
    return {"files": len(files), "extracted": len(items), "compiled": comp}


def compile_rules(project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    raw_path = root / RAW_PATH
    if not raw_path.exists():
        return {"ok": False, "message": "no raw rules ingested"}
    raw = _json.loads(raw_path.read_text(encoding="utf-8"))
    items = [
        RuleItem(**{**it, "source": Source(**it["source"])})
        for it in raw.get("items", [])
    ]

    # 聚合策略：key 去重；选择更严格值；记录冲突来源
    policy: dict[str, Any] = {}
    origins: dict[str, list[Source]] = {}
    conflicts: list[dict[str, Any]] = []

    # 从配置读取冲突阈值（默认 5%）
    conflict_delta = 0.05
    per_key_delta: dict[str, float] = {}
    try:
        import yaml  # type: ignore[import-untyped]  # lazy

        cfg_path = root / ".mcp/assistant.yaml"
        if cfg_path.exists():
            y = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            cd = (y.get("rules", {}) or {}).get("conflict_delta", 0.05)
            if isinstance(cd, dict):
                for k, v in cd.items():
                    try:
                        per_key_delta[str(k)] = max(0.0, min(1.0, float(v)))
                    except Exception:
                        continue  # nosec B112 - per-key parse ignored
                # fallback global
                conflict_delta = (
                    float(cd.get("__default__", conflict_delta))
                    if "__default__" in cd
                    else conflict_delta
                )
            else:
                conflict_delta = max(0.0, min(1.0, float(cd)))
    except Exception:
        pass  # nosec B110 - YAML read/parsing not critical

    def stricter(key: str, a: Any, b: Any) -> Any:
        # 对布尔：True 更严格；对数值阈值：较大更严格；否则保留 a
        if isinstance(a, bool) and isinstance(b, bool):
            return a or b
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return max(a, b)
        return a

    def threshold_for_key(key: str) -> float:
        return float(per_key_delta.get(key, conflict_delta))

    used_delta: dict[str, float] = {}

    def conflict(key: str, old: Any, new: Any) -> bool:
        if isinstance(old, bool) and isinstance(new, bool):
            return old != new
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            # 分歧 > delta 认为有冲突（默认 5%，可按键覆盖）
            d = threshold_for_key(key)
            used_delta[key] = d
            return abs(float(old) - float(new)) > float(d)
        return False

    # Environment snapshot for conditional rules
    os_name = platform.system().lower()
    is_windows = os_name.startswith("win")
    is_linux = os_name == "linux"
    is_darwin = os_name == "darwin"
    docker_ok = shutil.which("docker") is not None
    code_ok = (shutil.which("code") is not None) or (
        shutil.which("code-insiders") is not None
    )
    dockerfile_exists = (root / "Dockerfile").exists()

    def _match_conditions(conds: dict[str, list[str]] | None) -> bool:
        if not conds:
            return True
        # OS
        os_vals = set(conds.get("os") or [])
        if os_vals:
            ok = False
            if (
                ("windows" in os_vals and is_windows)
                or ("linux" in os_vals and is_linux)
                or ("darwin" in os_vals and is_darwin)
            ):
                ok = True
            if not ok:
                return False
        # IDE
        ide_vals = set(conds.get("ide") or [])
        if ide_vals:
            # Consider vscode if code CLI exists
            if "vscode" in ide_vals and not code_ok:
                return False
        # ENV
        env_vals = set(conds.get("env") or [])
        if env_vals:
            # container: either docker CLI available or Dockerfile exists
            if "container" in env_vals or "docker" in env_vals:
                if not (docker_ok or dockerfile_exists):
                    return False
        return True

    maxima: dict[str, float] = {}
    maxima_origins: dict[str, list[Source]] = {}
    for it in items:
        # Skip items whose conditions do not match current environment
        try:
            if not _match_conditions(getattr(it, "conditions", None)):
                continue
        except Exception:
            # If any error happens evaluating conditions, be permissive
            pass
        k, v = it.key, it.value
        # 收集 coverage.max_* 到 meta，不并入 policy
        if k.startswith("coverage.max_"):
            try:
                vf = float(v)
                if k not in maxima:
                    maxima[k] = vf
                    maxima_origins[k] = [it.source]
                else:
                    # 上限取更低（更严格）
                    if vf < maxima[k]:
                        maxima[k] = vf
                        maxima_origins[k].append(it.source)
                continue
            except Exception:
                continue  # nosec B112 - invalid maxima, skip
        if k not in policy:
            policy[k] = v
            origins[k] = [it.source]
        else:
            if conflict(k, policy[k], v):
                conflicts.append(
                    {
                        "key": k,
                        "keep": stricter(k, policy[k], v),
                        "old": policy[k],
                        "new": v,
                        "sources": [asdict(s) for s in origins[k] + [it.source]],
                    },
                )
                policy[k] = stricter(k, policy[k], v)
                origins[k].append(it.source)
            else:
                # 合并同类项，保留更严格值
                policy[k] = stricter(k, policy[k], v)
                origins[k].append(it.source)

    suggestions = _build_suggestions(policy, conflicts)
    # 针对上限添加“监控/提示”建议
    for mk, mv in maxima.items():
        suggestions.append(
            {
                "key": mk,
                "action": "monitor",
                "value": mv,
                "note": "文档包含覆盖率上限（仅提示，不作门禁）。",
                "severity": "info",
            },
        )

    compiled = {
        "policy": policy,
        "origins": {k: [asdict(s) for s in v] for k, v in origins.items()},
        "conflicts": conflicts,
        "suggestions": suggestions,
        "meta": {
            "conflict_delta": used_delta or {"default": conflict_delta},
            "maxima": maxima,
        },
    }
    (root / COMPILED_JSON).write_text(
        _json.dumps(compiled, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / COMPILED_MD).write_text(_to_markdown(compiled), encoding="utf-8")
    (root / SUGGESTIONS_MD).write_text(_to_suggestions_md(compiled), encoding="utf-8")
    return {
        "ok": True,
        "policy": policy,
        "conflicts": conflicts,
        "suggestions": suggestions,
        "meta": compiled.get("meta", {}),
        "compiled_md": str(root / COMPILED_MD),
        "suggestions_md": str(root / SUGGESTIONS_MD),
    }


def _to_markdown(compiled: dict[str, Any]) -> str:
    pol: dict[str, Any] = compiled.get("policy", {})
    confs: list[dict[str, Any]] = compiled.get("conflicts", [])
    meta: dict[str, Any] = (
        compiled.get("meta", {}) if isinstance(compiled.get("meta", {}), dict) else {}
    )
    maxima: dict[str, float] = (
        meta.get("maxima", {}) if isinstance(meta.get("maxima", {}), dict) else {}
    )
    lines: list[str] = []
    lines.append("# 项目规则（编译版） / Project Rules (Compiled)\n")
    lines.append(
        "- coverage.min_module: {}%".format(
            int(pol.get("coverage.min_module", 0) * 100),
        ),
    )
    lines.append(
        "- coverage.min_core: {}%".format(int(pol.get("coverage.min_core", 0) * 100)),
    )
    lines.append(
        "- test.no_skip_xfail: {}".format(bool(pol.get("test.no_skip_xfail", False))),
    )
    lines.append(
        "- test.warnings_as_errors: {}".format(
            bool(pol.get("test.warnings_as_errors", False)),
        ),
    )
    lines.append(
        "- test.mutation_required: {}".format(
            bool(pol.get("test.mutation_required", False)),
        ),
    )
    lines.append(
        "- security.secrets_scan: {}".format(
            bool(pol.get("security.secrets_scan", False)),
        ),
    )
    lines.append(
        "- security.sast_strict: {}".format(
            bool(pol.get("security.sast_strict", False)),
        ),
    )
    lines.append(
        "- container.required: {}".format(bool(pol.get("container.required", False))),
    )
    if pol.get("container.policy.baseline"):
        lines.append("- container.policy.baseline: true")
    if pol.get("perf.budget_ms"):
        lines.append(f"- perf.budget_ms: {pol['perf.budget_ms']} ms")
    if pol.get("ci.required"):
        lines.append("- ci.required: true")
    if pol.get("vcs.conventional_commits"):
        lines.append("- vcs.conventional_commits: true")
    if pol.get("vcs.branch_policy"):
        lines.append("- vcs.branch_policy: true")
    if pol.get("dev.tdd"):
        lines.append("- dev.tdd: true")
    if pol.get("process.strict_order"):
        lines.append("- process.strict_order: true")
    # 显示上限（提示性质）
    if maxima:
        for k in sorted(maxima.keys()):
            try:
                v = float(maxima[k])
                lines.append(f"- {k}: {int(v*100)}% (monitor)")
            except Exception:
                continue  # nosec B112 - skip non-numeric maxima
    lines.append("")
    if confs:
        lines.append("## 冲突 / Conflicts\n")
        for c in confs:
            lines.append(
                f"- {c['key']}: old={c['old']} new={c['new']} keep={c['keep']}",
            )
    return "\n".join(lines) + "\n"


def _build_suggestions(
    policy: dict[str, Any],
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sugg: list[dict[str, Any]] = []
    for c in conflicts:
        sugg.append(
            {
                "key": c["key"],
                "action": "unify",
                "keep": c["keep"],
                "note": "建议统一该规则值到 keep，并在源文档中修订以消除冲突",
                "severity": "warn",
            },
        )
    # 基础建议：确保门禁与策略一致
    if policy.get("test.no_skip_xfail"):
        sugg.append(
            {
                "key": "test.no_skip_xfail",
                "action": "enforce",
                "note": "在 pre-push/CI 禁止 skip/xfail（已在 hooks 模板中包含）",
                "severity": "must",
            },
        )
    if policy.get("test.warnings_as_errors"):
        sugg.append(
            {
                "key": "test.warnings_as_errors",
                "action": "enforce",
                "note": "pytest 加 -W error；在 CI 中严格执行",
                "severity": "must",
            },
        )
    if "coverage.min_module" in policy:
        sugg.append(
            {
                "key": "coverage.min_module",
                "action": "enforce",
                "value": policy["coverage.min_module"],
                "note": "在 CI/推送阶段设置 --cov-fail-under 对齐该阈值",
                "severity": "must",
            },
        )
    if "coverage.min_core" in policy:
        sugg.append(
            {
                "key": "coverage.min_core",
                "action": "monitor",
                "value": policy["coverage.min_core"],
                "note": "对核心模块单独跟踪覆盖率（可在后续扩展实现模块清单）",
                "severity": "info",
            },
        )
    if policy.get("security.secrets_scan"):
        sugg.append(
            {
                "key": "security.secrets_scan",
                "action": "enforce",
                "note": "在 pre-commit/CI 启用 detect-secrets 或等价工具",
                "severity": "must",
            },
        )
    if policy.get("container.required"):
        sugg.append(
            {
                "key": "container.required",
                "action": "enforce",
                "note": "确保仓库包含 Dockerfile/devcontainer，并在 CI 中校验存在性",
                "severity": "must",
            },
        )
    if policy.get("ci.required"):
        sugg.append(
            {
                "key": "ci.required",
                "action": "enforce",
                "note": "生成 CI 工作流并将其设为合并条件",
                "severity": "must",
            },
        )
    return sugg


def _to_suggestions_md(compiled: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 规则冲突与修改建议 / Conflicts & Suggestions\n")
    confs: list[dict[str, Any]] = compiled.get("conflicts", [])
    if not confs:
        lines.append("- 无显著冲突 / No significant conflicts\n")
    else:
        lines.append("## 冲突摘要\n")
        for c in confs:
            lines.append(
                f"- {c['key']}: old={c['old']}, new={c['new']}, 建议保留 keep={c['keep']}",
            )
    lines.append("")
    lines.append("## 建议\n")
    for s in compiled.get("suggestions", []):
        if "value" in s:
            lines.append(f"- [{s['action']}] {s['key']} → {s['value']}: {s['note']}")
        else:
            lines.append(f"- [{s['action']}] {s['key']}: {s['note']}")
    return "\n".join(lines) + "\n"
