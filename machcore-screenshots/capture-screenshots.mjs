// capture-screenshots.mjs
// -----------------------------------------------------------------------------
// MachCore マニュアル用スクリーンショットを自動撮影し、
// マニュアル内の「挿入エリア」で指定されたファイル名でそのまま保存するスクリプト。
//
// 前提:
//   - Node.js 18+ / このリポジトリ（machcore）内、または任意のフォルダで実行
//   - npm install -D playwright   (初回のみ)
//   - npx playwright install chromium   (初回のみ)
//   - omega-dev2上のMachCore Web (http://192.168.1.11:3010 等) が起動していること
//
// 使い方:
//   node capture-screenshots.mjs                 → recipes.json 全件を撮影
//   node capture-screenshots.mjs mc-01            → scenario/menuキーで絞り込み撮影
//   node capture-screenshots.mjs --file=mc-01-dashboard.png  → ファイル名で1件だけ撮影
//
// 出力:
//   ./screenshots/{マニュアルのファイル名}.png  ← そのままoutputs/にコピーしてembedスクリプトへ
// -----------------------------------------------------------------------------

import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ========== 環境設定（自分の環境に合わせて書き換える） ==========
//
// baseUrl は2択:
//   A) Next.js開発サーバーに直接（推奨・証明書の問題が一切出ない）
//        "http://192.168.1.11:3010"
//   B) nginx経由のSSL（mkcert自己署名証明書、実際のユーザーが見るURLに近い）
//        "https://192.168.1.11:8443"
//      ※ B の場合は必ず https:// にすること。http://…:8443 でアクセスすると
//        「400 Bad Request: The plain HTTP request was sent to HTTPS port」になる
//        （まさに直前に発生していたエラーはこれが原因）。
//      ※ mkcertの自己署名証明書はChromeが正規CA発行と認めないため、
//        下記 captureOne() 内で ignoreHTTPSErrors: true を設定済み。
//
const CONFIG = {
  baseUrl: "http://192.168.1.11:3010",
  adminCode: "ADMIN001",
  adminPassword: "Admin@1234",
  // OPERATOR認証（MC/NC側の「作業を開始する」モーダル用）
  operatorName: "アン",
  operatorPassword: "an",
  // 撮影に使う「実在するサンプルデータ」のID。
  // 実際にDBに存在するMC_ID/NC_IDに書き換えてから実行してください。
  sampleMcId: "296668",
  sampleNcId: "1",
  outDir: path.join(__dirname, "screenshots"),
};
// ================================================================

fs.mkdirSync(CONFIG.outDir, { recursive: true });

const recipes = JSON.parse(fs.readFileSync(path.join(__dirname, "recipes.json"), "utf-8"));

function parseViewport(sizeStr) {
  // "1280×720" のような文字列を {width,height} に変換
  const m = String(sizeStr).match(/(\d+)\s*[×x]\s*(\d+)/);
  if (!m) return { width: 1280, height: 800 };
  return { width: parseInt(m[1], 10), height: parseInt(m[2], 10) };
}

async function login(page) {
  // 管理者ログインが必要な画面用（/admin/login）。
  // OPERATOR認証（作業開始モーダル）は各レシピのactions内で個別に処理する。
  await page.goto(`${CONFIG.baseUrl}/admin/login`);
  const codeInput = page.locator('input[placeholder*="ADMIN001"], input[name="employee_code"]').first();
  if (await codeInput.count()) {
    await codeInput.fill(CONFIG.adminCode);
    await page.locator('input[type="password"]').first().fill(CONFIG.adminPassword);
    await page.getByRole("button", { name: /ログイン/ }).click();
    await page.waitForTimeout(800);
  }
}

async function tryOperatorAuth(page) {
  // 「作業を開始する」系のトリガーボタンを探す（文言は画面により微妙に異なる）
  // 例: "この作業を開始する" / "この作業を開始する（担当者確認）" / "🔓 作業を開始する"
  const trigger = page.getByText(/作業を開始する/).first();
  if ((await trigger.count()) === 0) return false; // 認証不要な画面はそのまま何もしない

  await trigger.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(400);

  // 担当者ボタン（アン）を選択
  const operatorBtn = page.getByText(CONFIG.operatorName, { exact: true }).first();
  if ((await operatorBtn.count()) === 0) {
    console.log(`  ⚠ 担当者ボタン「${CONFIG.operatorName}」が見つかりません（画面が想定と違う可能性）`);
    return false;
  }
  await operatorBtn.click({ timeout: 5000 });
  await page.waitForTimeout(300);

  // パスワード入力
  const pwInput = page.locator('input[type="password"]').first();
  if ((await pwInput.count()) === 0) {
    console.log("  ⚠ パスワード入力欄が見つかりません（担当者選択後に表示される想定）");
    return false;
  }
  await pwInput.fill(CONFIG.operatorPassword);

  // 確認ボタン（「確認してこの作業を開始する」等）
  const confirmBtn = page.getByText(/確認して.*開始する|開始する$/).last();
  await confirmBtn.click({ timeout: 5000 }).catch(async () => {
    // 見つからない場合はEnterキーでフォーム送信を試みる
    await pwInput.press("Enter");
  });
  await page.waitForTimeout(600);
  return true;
}

async function runActions(page, actions = []) {
  for (const act of actions) {
    switch (act.type) {
      case "click":
        await page.getByText(act.text, { exact: act.exact ?? false }).first().click({ timeout: act.timeout ?? 8000 });
        break;
      case "clickRole":
        await page.getByRole(act.role, { name: act.name }).first().click({ timeout: act.timeout ?? 8000 });
        break;
      case "fill":
        await page.locator(act.selector).fill(
          String(act.value).replace("{mcId}", CONFIG.sampleMcId).replace("{ncId}", CONFIG.sampleNcId)
        );
        break;
      case "wait":
        await page.waitForTimeout(act.ms ?? 500);
        break;
      case "waitForSelector":
        await page.waitForSelector(act.selector, { timeout: act.timeout ?? 5000 });
        break;
      default:
        console.warn("  ! 未対応のaction type:", act.type);
    }
  }
}

async function captureOne(browser, item) {
  const { width, height } = parseViewport(item.size);
  const context = await browser.newContext({
    viewport: { width, height },
    ignoreHTTPSErrors: true, // mkcertの自己署名証明書エラーを無視（httpsのbaseUrl使用時のみ関係）
  });
  const page = await context.newPage();

  // 4xx/5xxのAPIレスポンスを全部コンソールに出す（「どのAPIが失敗したか」を即座に特定するため）
  page.on("response", (res) => {
    if (res.status() >= 400) {
      console.log(`  ⚠ HTTP ${res.status()}  ${res.url()}`);
    }
  });
  page.on("pageerror", (err) => {
    console.log(`  ⚠ ページ内JSエラー: ${err.message}`);
  });

  try {
    if (item.needsLogin) await login(page);

    const url = item.path.replace("{mcId}", CONFIG.sampleMcId).replace("{ncId}", CONFIG.sampleNcId);
    await page.goto(`${CONFIG.baseUrl}${url}`, { waitUntil: "networkidle" });

    // 「作業を開始する」認証画面が出たら自動突破する（item.autoAuth === false で明示的に無効化可能。
    // 認証モーダル自体を撮りたいショット（例: mc-03-auth-modal.png）はrecipes.jsonでfalseにしてある）
    if (item.autoAuth !== false) {
      const didAuth = await tryOperatorAuth(page);
      if (didAuth) console.log("  🔓 担当者認証を自動突破しました");
    }

    await runActions(page, item.actions);
    await page.waitForTimeout(300);

    // 「撮れたけど中身がエラー画面だった」を検知する簡易チェック
    const bodyText = await page.locator("body").innerText().catch(() => "");
    const looksBroken =
      /Request failed with status code|エラーが発生しました|読み込み中…?$/i.test(bodyText.trim().slice(-40)) ||
      bodyText.includes("Request failed with status code");

    const outPath = path.join(CONFIG.outDir, item.file);
    if (item.selector) {
      await page.locator(item.selector).screenshot({ path: outPath });
    } else {
      await page.screenshot({ path: outPath, fullPage: !!item.fullPage });
    }

    if (looksBroken) {
      console.log(`⚠️  ${item.file}  ← 撮影はしたが画面内にエラー/読み込み中の文言を検出。中身を確認してください`);
    } else {
      console.log("✅", item.file);
    }
  } catch (e) {
    console.error("❌", item.file, "-", e.message);
    console.error("   → recipes.json の該当エントリの path/actions/selector を確認してください");
    // デバッグ用：失敗した瞬間の画面をそのまま保存（原因調査用）
    try {
      const debugPath = path.join(CONFIG.outDir, `_debug_${item.file}`);
      await page.screenshot({ path: debugPath, fullPage: true });
      console.error(`   → 失敗時の画面を保存しました: ${debugPath}`);
      console.error(`      （ロック画面／エラー画面／別画面に飛んでいないか目視確認してください）`);
    } catch (e2) {
      // ページ自体が死んでいる場合はデバッグスクショも取れない
    }
  } finally {
    await context.close();
  }
}

async function main() {
  const args = process.argv.slice(2);
  const fileArg = args.find((a) => a.startsWith("--file="))?.split("=")[1];
  const filterArg = args.find((a) => !a.startsWith("--"));
  const headless = process.env.HEADLESS !== "false"; // HEADLESS=false node capture-screenshots.mjs で画面が見える

  let targets = recipes;
  if (fileArg) targets = recipes.filter((r) => r.file === fileArg);
  else if (filterArg) targets = recipes.filter((r) => r.scenario === filterArg || r.file.startsWith(filterArg));

  if (targets.length === 0) {
    console.log("対象が見つかりません。scenario名またはファイル名を確認してください。");
    return;
  }

  console.log(`撮影対象: ${targets.length}件${headless ? "" : "（画面表示モード）"}\n`);
  const browser = await chromium.launch({ headless, slowMo: headless ? 0 : 300 });
  for (const item of targets) {
    console.log(`--- ${item.file} ---`);
    await captureOne(browser, item);
  }
  await browser.close();
  console.log(`\n完了。${CONFIG.outDir} に保存しました。`);
}

main();
