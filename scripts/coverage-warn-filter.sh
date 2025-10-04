#!/usr/bin/env bash
set -euo pipefail

# 说明：在某些路径映射场景（如容器内生成覆盖率、宿主机查看）下，coverage 可能打印
# “Couldn't parse '/work/...': No source for code ...” 的 CoverageWarning。该脚本提供一个
# 可选的过滤器，以隐藏该类非阻断的提示，不改变任何门禁逻辑或退出码。
# 用法示例：
#   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error \
#     --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing \
#     2> >(scripts/coverage-warn-filter.sh 1>&2)

grep -Ev "CoverageWarning: Couldn't parse '.*/work/.*'|CoverageWarning: Couldn't parse /.*/work/.*" || true

