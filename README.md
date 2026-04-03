# MachCore

NC旋盤プログラム管理システム（NC System）の移行プロジェクト。
Microsoft Access 2010 製の NC/MC 管理データベースを NestJS / Next.js ベースの Web アプリケーションへ刷新する。

> **社内限定 / Confidential** — karkyon/machcore

---

## システム概要

| システム | 旧環境 | 新環境 | 説明 |
|---------|--------|--------|------|
| NC System (S3) | Access 2010 (NC2023.mdb) | このリポジトリ | NC旋盤プログラム管理・工具・段取シート |
| MC System (S2) | Access 2010 (imotomc.mdb) | 今後実装予定 | マシニングセンタ加工管理 |

---

## 技術スタック

| 層 | 技術 | バージョン |
|----|------|-----------|
| Frontend | Next.js (App Router) + Tailwind CSS | 16.x / 4.x |
| Backend | NestJS + Fastify | 11.x |
| ORM | Prisma | 7.x |
| DB | PostgreSQL | 16 (port: 5440) |
| Cache | Redis | 7 (port: 6390) |
| Process | PM2 | 6.x |
| Runtime | Node.js (nvm v20.20.0) | v20.20.0 |
| Package | pnpm (workspace) | 10.x |

---

## サーバ情報（開発環境）

| 項目 | 値 |
|------|----|
| サーバ | omega-dev2 (192.168.1.11) |
| API | http://localhost:3011/api |
| Web | http://localhost:3010 |
| DB | localhost:5440 / machcore_dev |
| Redis | localhost:6390 |

---

## ディレクトリ構成
machcore/
├── apps/
│   ├── api/                  # NestJS バックエンド
│   │   └── src/
│   │       ├── auth/         # JWT認証・WorkSession
│   │       ├── nc/           # NCプログラム CRUD・PGファイル
│   │       ├── files/        # ファイルアップロード・配信
│   │       ├── admin/        # 管理者API・ユーザ管理
│   │       ├── machines/     # 機械マスタ
│   │       └── prisma/       # PrismaService
│   └── web/                  # Next.js フロントエンド
│       └── app/
│           ├── nc/search/    # SCR-01: 部品検索
│           ├── nc/[nc_id]/   # SCR-02: NC詳細
│           │   ├── edit/     # SCR-03: 変更・登録
│           │   ├── print/    # SCR-04: 段取シート
│           │   └── record/   # SCR-05: 作業記録
│           └── admin/        # 管理者画面
│               ├── login/
│               ├── users/
│               ├── settings/
│               └── raw/
├── docker/
│   └── postgres/init/        # DB初期化SQL
├── docker-compose.yml        # PostgreSQL + Redis
├── pnpm-workspace.yaml
├── dev.sh                    # ✅ TypeCheck + pm2 restart + 疎通確認
└── README.md

---

## 初回セットアップ

### 前提条件
```bash
# Node.js v20.20.0 (nvm)
nvm use v20.20.0

# pm2 シンボリックリンク（新規サーバの場合）
sudo ln -sf ~/.nvm/versions/node/v20.20.0/bin/pm2 /usr/local/bin/pm2

# pnpm
npm install -g pnpm
```

### 環境変数
```bash
cp .env.example .env
# .envを編集（DB接続情報・JWT_SECRET等）
```

`.env` の主要項目:
```env
DATABASE_URL="postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev"
REDIS_URL="redis://:redis_pass@localhost:6390"
JWT_SECRET="your-secret-key-change-me"
JWT_EXPIRES_IN="12h"
UPLOAD_BASE_PATH="/home/karkyon/projects/machcore/uploads"
NEXT_PUBLIC_API_URL="http://localhost:3011/api"
```

### DB起動・マイグレーション
```bash
# Docker (PostgreSQL + Redis)
docker compose up -d

# 依存パッケージ
pnpm install

# DBマイグレーション
cd apps/api
npx prisma migrate deploy
npx prisma generate
```

### PM2 起動（本番/開発）
```bash
# APIサーバ起動（NestJS dist使用）
pm2 start ecosystem.config.js

# または個別起動
pm2 start "pnpm --filter api start:prod" --name machcore-api
pm2 start "pnpm --filter web start" --name machcore-web

# 起動状態確認
pm2 list
pm2 logs machcore-api --lines 30
```

---

## 日常開発ワークフロー

### コード変更後のTypeCheck + 再起動（推奨）
```bash
# プロジェクトルートから一発実行
~/projects/machcore/dev.sh
```

`dev.sh` の処理内容:
1. `apps/api` TypeScript型チェック (`tsc --noEmit`)
2. `apps/web` TypeScript型チェック (`tsc --noEmit`)
3. `pm2 restart machcore-api`
4. API疎通確認 (HTTP 200)

### APIサーバのみ再起動
```bash
pm2 restart machcore-api
pm2 logs machcore-api --lines 20 --nostream
```

### ログ確認
```bash
pm2 logs machcore-api --lines 50    # APIログ
pm2 logs machcore-web --lines 20    # Webログ
```

---

## 主要APIエンドポイント

| ID | メソッド | パス | 認証 | 概要 |
|----|---------|------|------|------|
| - | GET | `/api/nc/search` | 不要 | 部品検索 |
| - | GET | `/api/nc/:id` | 不要 | NC詳細取得 |
| NC-04 | POST | `/api/nc` | JWT | NC新規登録 |
| NC-05 | PUT | `/api/nc/:id` | JWT | NC更新 |
| NC-06 | GET | `/api/nc/:id/pg-file` | JWT | PGファイル読込 |
| NC-06b | PUT | `/api/nc/:id/pg-file` | JWT | PGファイル保存 |
| NC-07 | GET | `/api/nc/:id/download` | JWT | PGファイルDL(USB書出し) |
| NC-08 | POST | `/api/nc/:id/print` | JWT | 段取シートPDF生成 |
| FIL-01 | GET | `/api/nc/:id/files` | 不要 | ファイル一覧 |
| FIL-02 | POST | `/api/files/upload` | JWT | ファイルアップロード |
| FIL-04 | DELETE | `/api/files/:id` | JWT | ファイル削除 |
| FIL-EDIT | POST | `/api/files/:id/save-edited` | JWT | 編集済み画像保存 |
| WR-01 | GET | `/api/nc/:id/work-records` | 不要 | 作業記録一覧 |
| WR-02 | POST | `/api/nc/:id/work-records` | JWT | 作業記録登録 |
| WR-03 | PUT | `/api/nc/:id/work-records/:rid` | JWT | 作業記録更新 |
| WR-04 | DELETE | `/api/nc/:id/work-records/:rid` | JWT | 作業記録削除 |
| AUTH-01 | POST | `/api/auth/work-session` | 不要 | WorkSession JWT発行 |
| AUTH-02 | DELETE | `/api/auth/work-session` | JWT | WorkSession終了 |
| AUTH-03 | POST | `/api/auth/login` | 不要 | 管理者ログイン |
| ADM-01 | GET | `/api/admin/users` | JWT(ADMIN) | ユーザ一覧 |
| ADM-02 | POST | `/api/admin/users` | JWT(ADMIN) | ユーザ作成 |
| ADM-03 | PUT | `/api/admin/users/:id` | JWT(ADMIN) | ユーザ更新 |
| ADM-03b | PUT | `/api/admin/users/:id/password` | JWT(ADMIN) | PW変更 |
| ADM-04 | DELETE | `/api/admin/users/:id` | JWT(ADMIN) | ユーザ無効化 |

---

## 認証フロー
オペレーター操作（NC詳細/変更/段取/作業記録）
→ POST /auth/work-session (operator_id + password + session_type + nc_program_id)
→ Work Session JWT (有効期限: session_typeごとに異なる)
→ 操作完了後 DELETE /auth/work-session
管理者操作（ユーザ管理/設定）
→ POST /auth/login (employee_code + password)
→ Admin JWT (有効期限: 8h)
→ sessionStorage に保存

---

## 既知の問題・未対応

| 優先度 | 項目 | 詳細 |
|--------|------|------|
| 🟡中 | nc_tools 1,996件移行失敗 | K_id不整合によりmigrate再実行が必要 |
| 🟡中 | nc_programs 5件 一意制約違反 | 個別確認が必要 |
| 🟡中 | PGファイル本体未移行 | 元NCサーバ → uploads/nc_files/{id}/pg/ へ転送スクリプトが必要 |
| 🟡中 | 全ユーザPW不明 | id:22(ADMIN001)のみ Admin@1234 確認済み。他は再設定が必要 |
| 🟢低 | 段取シートPDFレイアウト | print/page.tsx Puppeteerレイアウト調整残 |

---

## 関連資料

- `NC_機能仕様書_v2.pdf` — 全画面・API仕様
- `NCシステム_技術スタック資料_v2.pdf` — 技術選定根拠
- `MachCore_作業引継ぎ資料_v*.docx` — 作業進捗・引継ぎ
