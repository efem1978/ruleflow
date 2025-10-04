# 规则短语快速索引 / Rules Phrases Quick Index

## 覆盖率下限 Min

- 中文：不少于/不低于/至少/≥/大于/高于/超过/九成/十成/九成五
- 英文：at least / no(not) less than / >= / greater than / more than / over / above / ninety five percent
- 小数：95.5% / 96.7 percent

## 覆盖率上限 Max（提示 monitor，不作门禁）

- 中文：不高于/不超过/至多/≤/< / 介于…之间（上界）
- 英文：at most / no(not) more than / less than / under / below / <= / < / between … and …（上界）
- 词数：at most ninety five percent / no more than ninety percent

## 区间 Range（下限入 min，上限为 monitor）

- 中文：≥ 90% 且 < 95% / 覆盖率 介于 96% 和 99% 之间
- 英文：between 90% and 95% coverage

## 禁止跳过 / 警告视为错误 / 变异测试

- test.no_skip_xfail / test.warnings_as_errors / test.mutation_required

## 安全与容器

- security.secrets_scan / security.sast_strict / container.required / container.policy.baseline
