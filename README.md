# MachCore

MC/NC マシニング加工管理システム

## システム構成
- **NC システム** (S3): NC旋盤プログラム管理
- **MC システム** (S2): マシニングセンタ管理

## 技術スタック
- Frontend: Next.js 15 (App Router) + Tailwind CSS 4
- Backend: NestJS 11 + Fastify
- ORM: Prisma 6
- DB: PostgreSQL 16
- Cache: Redis 7

## 開発環境起動
\`\`\`bash
docker compose up -d
pnpm install
pnpm run dev
\`\`\`
