/**
 * 段取シート(MC: pdf-lib / NC: Puppeteer)の多言語対応(日本語 ja / ベトナム語 vi)と機械名の表記。
 *
 * ・表示言語: 画面と同じ「システム既定言語」(system_settings.default_language = ja|vi)。
 *   (画面側は個人設定を廃止して既定言語に一本化済みのため、印刷物も同じ値に従う)
 * ・機械名: 「機械コード <機械名>」。機械コードと機械名が(空白を除いて)同じなら機械コードだけ。
 *   (画面 apps/web/lib/machineLabel.tsx と同じ規則)
 * ・PDF(MC): テンプレートPDFに焼き込まれた日本語ラベルは assets/setup_sheet_labels.json の位置情報で
 *   白塗りしてベトナム語を上書きする。ベトナム語の文字(アクセント付き)は IPAゴシックに無いため、
 *   assets/fonts/NotoSansVN-Regular.ttf を併用し、1文字ずつフォントを切り替えて描画する(CompositeFont)。
 * ・HTML(NC): ラベル辞書(NC_SHEET_TEXT)と、Noto Sans の @font-face(base64)を使う。
 */
import * as fs from 'fs';
import * as path from 'path';
import { PDFPage, rgb } from 'pdf-lib';

export type SheetLang = 'ja' | 'vi';

export const IPAG_FONT_PATH = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';

export function assetsDir(): string {
  return path.join(process.cwd(), 'assets');
}

export function normalizeSheetLang(v: unknown): SheetLang {
  return v === 'vi' ? 'vi' : 'ja';
}

/** システム既定言語(画面の言語設定と同じ値)を返す。取得できなければ ja */
export async function getSheetLang(prisma: any): Promise<SheetLang> {
  try {
    const row = await prisma.systemSetting.findUnique({ where: { key: 'default_language' } });
    return normalizeSheetLang(row?.value);
  } catch {
    return 'ja';
  }
}

// ──────────────────────────────────────────────────────────────
// 機械名の表記(画面 machineLabel.tsx と同じ規則)
// ──────────────────────────────────────────────────────────────
const noSpace = (s: string) => s.replace(/[\s　]+/g, '');

/** 「機械コード <機械名>」。同じなら機械コードのみ。どちらかが空なら一方だけ。両方空なら '' */
export function machineLabel(m: { machineCode?: string | null; machineName?: string | null } | null | undefined): string {
  const code = String(m?.machineCode ?? '').trim();
  const name = String(m?.machineName ?? '').trim();
  if (!code && !name) return '';
  if (!name) return code;
  if (!code) return name;
  if (noSpace(code) === noSpace(name)) return code;
  return `${code} <${name}>`;
}

// ──────────────────────────────────────────────────────────────
// コード内で組み立てている文言(MC PDF)
// ──────────────────────────────────────────────────────────────
type Pair = { ja: string; vi: string };
const SHEET_TEXT: Record<string, Pair> = {
  issued:            { ja: '発行', vi: 'Phát hành' },
  pageSuffix:        { ja: 'ページ', vi: 'trang' },
  preview:           { ja: 'プレビュー', vi: 'XEM TRƯỚC' },
  cont:              { ja: '(続き)', vi: ' (tiếp)' },
  newSheetCont:      { ja: '新規段取シート(続き)', vi: 'Giấy set máy cho sp làm lần đầu (tiếp)' },
  partId:            { ja: '部品ID', vi: 'Mã số sp' },
  machiningId:       { ja: '加工ID', vi: 'Mã số gia công' },
  drawingNo:         { ja: '図面番号', vi: 'Số bảng vẽ' },
  toolingCont:       { ja: 'ツーリング(続き)', vi: 'Dụng cụ (tiếp)' },
  noteFull:          { ja: '備考(全文)', vi: 'Ghi chú (toàn văn)' },
  overflowFull:      { ja: '欄に入りきらない項目(全文)', vi: 'Mục không vừa ô (toàn văn)' },
  noteOverflowNote:  { ja: '※備考の全文は「新規段取シート(続き)」に印字', vi: '※ Toàn văn ghi chú in ở "Phiếu cài đặt mới (tiếp)"' },
  row:               { ja: '行', vi: 'Dòng' },
  note:              { ja: '備考', vi: 'Ghi chú' },
  clamp:             { ja: 'クランプ', vi: 'Kẹp' },
  tool:              { ja: '工具', vi: 'Dụng cụ' },
  dValue:            { ja: 'D値', vi: 'Giá trị D' },
  comment:           { ja: 'コメント', vi: 'Ghi chú' },
  axis1:             { ja: '第1軸', vi: 'Trục 1' },
  axis2:             { ja: '第2軸', vi: 'Trục 2' },
  purposeSetup:      { ja: '段取', vi: 'Cài đặt' },
  purposeReference:  { ja: '参考資料', vi: 'Tài liệu tham khảo' },
  purposeContinuous: { ja: '連続使用', vi: 'Dùng liên tục' },
};

export function sheetText(lang: SheetLang, key: keyof typeof SHEET_TEXT | string): string {
  const p = SHEET_TEXT[key];
  return p ? p[lang] : String(key);
}

/** ツーリング表の列見出し(N / 工具 / T / H / D / D値 / SUB / コメント) */
export function toolLabels(lang: SheetLang): string[] {
  return ['N', sheetText(lang, 'tool'), 'T', 'H', 'D', sheetText(lang, 'dValue'), 'SUB', sheetText(lang, 'comment')];
}

// ──────────────────────────────────────────────────────────────
// 複合フォント(日本語 + ベトナム語)
// ──────────────────────────────────────────────────────────────
export interface CompositeFont {
  __composite: true;
  primary: any;
  fallback: any | null;
  embedder: { font: { hasGlyphForCodePoint: (cp: number) => boolean } };
  widthOfTextAtSize(text: string, size: number): number;
  heightAtSize(size: number, options?: any): number;
}

const hasGlyph = (font: any, cp: number): boolean => {
  const fk = font?.embedder?.font;
  try { return !fk || typeof fk.hasGlyphForCodePoint !== 'function' || fk.hasGlyphForCodePoint(cp); }
  catch { return true; }
};

function runsOf(font: CompositeFont, text: string): { font: any; text: string }[] {
  const runs: { font: any; text: string }[] = [];
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    const f = hasGlyph(font.primary, cp) ? font.primary
            : (font.fallback && hasGlyph(font.fallback, cp)) ? font.fallback
            : font.primary;
    const last = runs[runs.length - 1];
    if (last && last.font === f) last.text += ch; else runs.push({ font: f, text: ch });
  }
  return runs;
}

/**
 * PDFDocument にフォントを埋め込み、複合フォントを返す(doc.registerFontkit 済みであること)。
 *  ja: 主 = IPAゴシック / 補助 = Noto Sans(IPAに無い文字をベトナム語等で補う)
 *  vi: 主 = Noto Sans   / 補助 = IPAゴシック(日本語の部品名・備考などのデータ用)
 */
export async function embedSheetFont(doc: any, lang: SheetLang): Promise<CompositeFont> {
  const notoPath = path.join(assetsDir(), 'fonts', 'NotoSansVN-Regular.ttf');
  const ipag = fs.existsSync(IPAG_FONT_PATH) ? await doc.embedFont(fs.readFileSync(IPAG_FONT_PATH), { subset: true }) : null;
  const noto = fs.existsSync(notoPath) ? await doc.embedFont(fs.readFileSync(notoPath), { subset: true }) : null;
  if (!ipag && !noto) throw new Error(`段取シート用フォントが見つかりません: ${IPAG_FONT_PATH}`);
  const primary  = lang === 'vi' ? (noto ?? ipag) : (ipag ?? noto);
  const fallback = lang === 'vi' ? (noto ? ipag : null) : (ipag ? noto : null);
  const comp: CompositeFont = {
    __composite: true,
    primary,
    fallback,
    embedder: { font: { hasGlyphForCodePoint: (cp: number) => hasGlyph(primary, cp) || (!!fallback && hasGlyph(fallback, cp)) } },
    widthOfTextAtSize(text: string, size: number): number {
      let w = 0;
      for (const r of runsOf(comp, String(text ?? ''))) w += r.font.widthOfTextAtSize(r.text, size);
      return w;
    },
    heightAtSize(size: number, options?: any): number {
      return primary.heightAtSize(size, options);
    },
  };
  return comp;
}

// PDFPage.drawText を、複合フォントのときだけ「文字ごとにフォントを切り替えて描画」に差し替える(1回だけ)
const PATCH_FLAG = '__setupSheetCompositePatched';
function patchDrawText(): void {
  const proto: any = (PDFPage as any).prototype;
  if (proto[PATCH_FLAG]) return;
  const orig = proto.drawText;
  proto.drawText = function (this: any, text: string, options: any = {}) {
    const font = options?.font;
    if (!font || !font.__composite) return orig.call(this, text, options);
    const size = Number(options.size ?? 12);
    const lineHeight = Number(options.lineHeight ?? font.heightAtSize(size));
    const rot = options.rotate;
    const theta = rot ? (rot.type === 'radians' ? rot.angle : (rot.angle * Math.PI) / 180) : 0;
    const cos = Math.cos(theta), sin = Math.sin(theta);
    const x0 = Number(options.x ?? 0), y0 = Number(options.y ?? 0);
    String(text ?? '').split(/\r\n|\r|\n/).forEach((line, li) => {
      // 行送りは回転方向に直交(下向き)
      let x = x0 + li * lineHeight * sin;
      let y = y0 - li * lineHeight * cos;
      for (const r of runsOf(font, line)) {
        orig.call(this, r.text, { ...options, font: r.font, x, y, lineHeight: undefined });
        const w = r.font.widthOfTextAtSize(r.text, size);
        x += w * cos; y += w * sin;
      }
    });
  };
  proto[PATCH_FLAG] = true;
}
patchDrawText();

// ──────────────────────────────────────────────────────────────
// テンプレートPDFに焼き込まれた日本語ラベルのベトナム語上書き
// ──────────────────────────────────────────────────────────────
type LabelDef = {
  tpl: string; ja: string; vi: string;
  x0: number; x1: number; top: number; bottom: number; size: number;
  boxL: number; boxR: number; boxT: number; boxB: number; pageH: number; bg?: number[] | null;
};
let labelCache: LabelDef[] | null = null;
function loadLabels(): LabelDef[] {
  if (labelCache) return labelCache;
  try {
    const j = JSON.parse(fs.readFileSync(path.join(assetsDir(), 'setup_sheet_labels.json'), 'utf-8'));
    labelCache = Array.isArray(j?.labels) ? j.labels : [];
  } catch (e: any) {
    console.warn('[setupsheet] setup_sheet_labels.json を読めません:', e?.message);
    labelCache = [];
  }
  return labelCache!;
}

/** 幅 W に収まる(必要なら2行以上に折り返した)フォントサイズと行を返す */
function fitLabel(font: CompositeFont, text: string, W: number, Hbox: number, start: number, min = 4.5) {
  const wrap = (fs: number): string[] => {
    const words = text.split(' ');
    const lines: string[] = [];
    let cur = '';
    for (const w of words) {
      const t = cur ? `${cur} ${w}` : w;
      if (!cur || font.widthOfTextAtSize(t, fs) <= W) cur = t; else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    return lines;
  };
  // まず1行のまま 6pt まで縮めて収める(折り返しは最後の手段)
  for (let fs = start; fs >= 6 - 1e-9; fs -= 0.25) {
    if (font.widthOfTextAtSize(text, fs) <= W + 0.01 && fs * 1.12 <= Hbox + 0.6) return { fs, lines: [text] };
  }
  for (let fs = start; fs >= min - 1e-9; fs -= 0.25) {
    const lines = wrap(fs);
    if (lines.every(l => font.widthOfTextAtSize(l, fs) <= W + 0.01) && lines.length * fs * 1.12 <= Hbox + 0.6) return { fs, lines };
  }
  return { fs: min, lines: wrap(min) };
}

/**
 * ベトナム語のとき、テンプレートページ(tpl = assets のPDFファイル名の拡張子なし)の日本語ラベルを
 * 白塗りしてベトナム語を重ねる。日本語のときは何もしない。値の印字より前に呼ぶこと。
 */
/** 範囲指定(参考資料の帯など、テンプレートの一部を移動・拡縮して再描画した所へラベルを重ねる場合) */
export interface LabelRegion { xMin: number; xMax: number; topMin: number; bottomMax: number; ox: number; sx: number }
export function applyTemplateLabels(page: any, tpl: string, lang: SheetLang, font: CompositeFont, region?: LabelRegion): void {
  if (lang !== 'vi') return;
  for (let L of loadLabels()) {
    if (L.tpl !== tpl) continue;
    if (region) {
      if (!(L.x0 >= region.xMin && L.x1 <= region.xMax && L.top >= region.topMin && L.bottom <= region.bottomMax)) continue;
      const mx = (x: number) => region.ox + (x - region.xMin) * region.sx;
      L = { ...L, x0: mx(L.x0), x1: mx(L.x1), boxL: mx(L.boxL), boxR: mx(L.boxR) };
    }
    try {
      const H = L.pageH;
      // 元の日本語を白塗り(字形の上端・下端まで。罫線は字形の外側にあるので消えない)
      page.drawRectangle({ x: L.x0 - 0.6, y: H - L.bottom - 0.8, width: L.x1 - L.x0 + 1.2, height: L.bottom - L.top + 2.6, color: L.bg ? rgb(L.bg[0], L.bg[1], L.bg[2]) : rgb(1, 1, 1), borderWidth: 0 });
      if (!L.vi) continue; // 空訳(単位の「枚」「件」など)は白塗りのみ
      const Hbox = Math.max(L.bottom - L.top, L.boxB - L.boxT);
      const start = L.size > 13 ? L.size * 0.85 : Math.min(L.size * 0.92, 11);
      // 元の位置から幅(boxR まで)に収める。小さくなりすぎる(6.5pt未満)ときは欄の左端から始めて幅を広げる
      let tx = L.x0;
      let fit = fitLabel(font, L.vi, Math.max(L.x1 - L.x0, L.boxR - L.x0), Hbox, start);
      if (fit.fs < 6.5 && L.boxL + 1.5 < L.x0 - 1) {
        const alt = fitLabel(font, L.vi, Math.max(L.x1 - L.x0, L.boxR - (L.boxL + 1.5)), Hbox, start);
        if (alt.fs > fit.fs) { fit = alt; tx = L.boxL + 1.5; }
      }
      const { fs, lines } = fit;
      const lh = fs * 1.12;
      const yc = H - (L.top + L.bottom) / 2;
      const firstBase = yc + ((lines.length - 1) * lh) / 2 - fs * 0.34;
      lines.forEach((ln, i) => {
        page.drawText(ln, { x: tx, y: firstBase - i * lh, size: fs, font, color: rgb(0, 0, 0) });
      });
    } catch (e: any) {
      console.warn(`[setupsheet] ラベル上書き失敗 ${L.tpl} ${L.ja}: ${e?.message}`);
    }
  }
}

// ──────────────────────────────────────────────────────────────
// NC 段取シート(HTML)の文言
// ──────────────────────────────────────────────────────────────
const NC_TEXT: Record<string, Pair> = {
  title:         { ja: 'NC段取シート', vi: 'Giấy set máy cho sp làm lần đầu' },
  reference:     { ja: '参考資料', vi: 'Tài liệu tham khảo' },
  outputAt:      { ja: '出力日時', vi: 'Ngày giờ' },
  partId:        { ja: '部品id', vi: 'Mã số sp' },
  machiningId:   { ja: '加工id', vi: 'Mã số gia công' },
  client:        { ja: '納入先', vi: 'Khách hàng' },
  drawingNo:     { ja: '図面番号', vi: 'Số bảng vẽ' },
  name:          { ja: '名　称', vi: 'Tên sp' },
  mainModel:     { ja: '主機種型式', vi: 'Kiểu máy chính' },
  processL:      { ja: 'Ｌ', vi: 'L' },
  machine:       { ja: '機　械', vi: 'Máy' },
  time:          { ja: 'タ イ ム', vi: 'Thời gian' },
  status:        { ja: '承認ステ', vi: 'Trạng thái' },
  fileName:      { ja: 'ﾌｧｲﾙ名', vi: 'Tên file' },
  oNumber:       { ja: 'ｏﾅﾝﾊﾞｰ', vi: 'Chương trình chính' },
  folderName:    { ja: 'フォルダ名', vi: 'Tên thư mục' },
  clampAllow:    { ja: '掴　代', vi: 'Lượng kẹp sp' },
  note:          { ja: '備　考', vi: 'Ghi chú' },
  toolList:      { ja: '加工リスト', vi: 'Danh sách gia công' },
  noTools:       { ja: '加工データなし', vi: 'Không có dữ liệu gia công' },
  colProcess:    { ja: '加　工', vi: 'Gia công' },
  colShape:      { ja: '形　状', vi: 'Hình dạng' },
  colHolder:     { ja: 'ホルダー', vi: 'Đầu kẹp dao' },
  colNoseR:      { ja: 'ノーズR', vi: 'Nose R' },
  colNote:       { ja: '備　考', vi: 'Ghi chú' },
  drawings:      { ja: '段取図', vi: 'Bản vẽ cài đặt' },
  drawingN:      { ja: '段取図', vi: 'Bản vẽ cài đặt' },
  approver:      { ja: '承認者', vi: 'Người chứng nhận' },
  approvedAt:    { ja: '承認日', vi: 'Ngày duyệt' },
  setupOperator: { ja: '段取担当', vi: 'Người setup' },
  prodOperator:  { ja: '量産担当', vi: 'Người sản xuất' },
  qty:           { ja: '個　数', vi: 'Số lượng' },
  setupTime:     { ja: '段取時間', vi: 'TG setup' },
  prodTime:      { ja: '量産時間', vi: 'TG sản xuất' },
  input:         { ja: '入　力', vi: 'Nhập' },
  changeNotice:  { ja: '変更届', vi: 'Đơn thay đổi' },
  chgSheet:      { ja: 'シート', vi: 'Phiếu' },
  chgProgram:    { ja: 'プログラム', vi: 'Chương trình' },
  chgDrawing:    { ja: '図', vi: 'Bản vẽ' },
  chgPhoto:      { ja: '写真', vi: 'Ảnh' },
  content:       { ja: '内　容', vi: 'Nội dung' },
  footerSystem:  { ja: 'NC旋盤プログラム管理システム MachCore', vi: 'Hệ thống quản lý chương trình máy tiện NC MachCore' },
  footerDrawing: { ja: '図面番号', vi: 'Số bảng vẽ' },
  footerPart:    { ja: '部品ID', vi: 'Mã số sp' },
  preview:       { ja: 'プレビュー', vi: 'XEM TRƯỚC' },
  stApproved:    { ja: '承認済', vi: 'Đã duyệt' },
  stChanging:    { ja: '変更中', vi: 'Đang thay đổi' },
  stPending:     { ja: '未承認', vi: 'Chưa duyệt' },
  stNew:         { ja: '新規', vi: 'Mới' },
};
export function ncSheetText(lang: SheetLang, key: keyof typeof NC_TEXT | string): string {
  const p = NC_TEXT[key];
  return p ? p[lang] : String(key);
}

/** NC段取シート(HTML)用: Noto Sans の @font-face(base64 埋め込み)。ベトナム語のときだけ返す(外部通信なし) */
let notoFaceCache: string | null = null;
export function notoFontFaceCss(): string {
  if (notoFaceCache !== null) return notoFaceCache;
  try {
    const b64 = fs.readFileSync(path.join(assetsDir(), 'fonts', 'NotoSansVN-Regular.ttf')).toString('base64');
    notoFaceCache = `@font-face { font-family: "SheetNotoSans"; src: url(data:font/ttf;base64,${b64}) format("truetype"); font-weight: 100 900; font-style: normal; }`;
  } catch (e: any) {
    console.warn('[setupsheet] NotoSans を読めません:', e?.message);
    notoFaceCache = '';
  }
  return notoFaceCache;
}

/** HTMLに埋め込む値のエスケープ */
export function escHtml(v: unknown): string {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
