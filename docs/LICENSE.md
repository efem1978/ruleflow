# License Generation & Verification (Demo)

本页提供可复制的示例（仅用于本地演示/测试），涵盖：
- hs256（对称盐）与 rs256（非对称）两种签名方式
- 示例私钥/公钥（演示用），示例 license JSON
- CLI 与脚本使用方式

重要声明
- 以下示例密钥与 license 仅用于本地演示，切勿用于生产。
- 生产环境请自行生成密钥对，并安全存储私钥；在 CI/运行环境通过 `MCP_LICENSE_PUBKEY` 注入公钥（PEM）。

## 一、hs256（演示）

- 环境变量：`MCP_LICENSE_SALT`（可选；未设置则使用内置演示盐）
- 生成：
```bash
mcp-rules-assistant license-generate \
  --issued-to "Alice" --expires 2026-01-01 --machine "" \
  --alg hs256 --out lic.json
```
- 激活与校验：
```bash
mcp-rules-assistant license-activate --file lic.json
mcp-rules-assistant license-verify
```
- 示例 license（hs256）：
```json
{
  "issued_to": "Alice",
  "expires": "2026-01-01",
  "machine": "",
  "alg": "hs256",
  "signature": "<sha256-hex-of-payload+salt>"
}
```

## 二、rs256（推荐）

- 生成密钥对（OpenSSL）：
```bash
# 生成私钥与公钥（演示）
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```
- 设置环境变量（用于校验）：
```bash
export MCP_LICENSE_PUBKEY="$(cat public.pem)"
```
- 生成 license：
```bash
mcp-rules-assistant license-generate \
  --issued-to "Alice" --expires 2026-01-01 --machine "" \
  --alg rs256 --private-key private.pem --out lic.json
```
- 激活与校验：
```bash
mcp-rules-assistant license-activate --file lic.json
mcp-rules-assistant license-verify
```

### 示例密钥（演示）

私钥（演示）
```pem
-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAK0ylF7hTHcC2mWH01hjZva8r4m1qkZPh1wE7RkK2N4u3P8VjKCY
k0qSIfHqp2qgqU2bYy1b9c7wP7lYfV1Q0/sCAwEAAQJAFg2wz9t0o2z7cSlN1q6q
z6l8q4xJmT8L3l2mFc5kRt1tq0Q8qm3cO1iYz7hQ7hGqXn6G6eEvmKjzDE6YkN2+
UQIhAOoP8w5X4T1GmJkM+6pZV8bP9o3u4m8pK0a9lXc2SeiVAiEAu7oFQF6fL8wz
kAvcPLaMM6g7ctf2zQvBqBzZyicVxV8CIQC19gqYv5r7oZIv4X1jeXxX3cJ1a8p9
b/YJ4k7cVZfoYwIgH1R7XcJ2sR3pH3TQ6HkqTphJc0mK+QACQ0cI9bV6l2UCIQCK
3m1rli8O562p1v3a1+3M2T0S9eN1m7eomZ3k7vX7l6mFZw==
-----END RSA PRIVATE KEY-----
```

公钥（演示）
```pem
-----BEGIN PUBLIC KEY-----
MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALTKUxu9tTbmq3v1Ecic9kCq1NHWwWQn
qUF+Z8F2qVvm1m9+9bE1q1zw6j+M0Xz8cESjFf7QdF4KfWcQqZzq4wECAwEAAQ==
-----END PUBLIC KEY-----
```

> 以上密钥仅为示例，不能用于生产。实际使用时请替换为你自己的密钥对。

## 三、脚本与 CI

- 一键演示脚本（rs256）：`scripts/license-demo-rs256.sh`
  - 生成密钥 → 发行 license → 激活 → 校验（依赖 openssl 与 Python cryptography）

- CI 可选依赖（已在仓库 CI 与生成 CI 中提供）
  - 安装 cryptography（用于 rs256 验签）：
    - `.github/workflows/ci.yml` 的 Install tools 步骤中包含：
      ```bash
      pip install cryptography || true
      ```
    - 生成的 CI（`mcp-rules-assistant generate-ci`）会在 `license.required: true` 时自动包含 `pip install cryptography`。

---

如需按许可证门禁限制敏感操作（enforce/ci/hooks），可在 `.mcp/assistant.yaml` 设置：
```yaml
license:
  required: true
```
