// [No.62] ダッシュボード(MC/NC)の未回収段取シート一覧を印刷したとき、左メニュー込みの画面のまま出力され、
//   「図番/部品名/納入先」列が狭くなって1文字ずつ縦に折り返し、16枚で9ページになっていた。
//   印刷時は左メニュー・操作ボタンを隠し、A4横・列幅固定・折り返さない(はみ出しは…で省略)一覧にする。
export const DASHBOARD_PRINT_CSS = `
@media print {
  @page { size: A4 landscape; margin: 8mm; }
  html, body { height: auto !important; overflow: visible !important; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .dash-root { height: auto !important; display: block !important; background: #fff !important; }
  .dash-root header button { display: none !important; }
  .dash-body { display: block !important; min-height: 0 !important; }
  .dash-aside { display: none !important; }
  .dash-main { overflow: visible !important; padding: 0 !important; }
  .dash-main section { margin-bottom: 6px !important; }
  .dash-card { break-inside: avoid; box-shadow: none !important; margin-bottom: 6px !important; }
  .dash-grid {
    grid-template-columns: 46px 48px 48px 52px 78px minmax(0, 1fr) 104px 78px 58px 0 !important;
    padding: 2px 6px !important; column-gap: 6px !important; font-size: 10px !important;
  }
  .dash-grid > * { white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; min-width: 0 !important; }
  .dash-grid svg { display: none !important; }
}
`;
