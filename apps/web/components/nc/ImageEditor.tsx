"use client";
import { useEffect, useRef, useState, useCallback } from "react";

type Props = {
  imageUrl:    string;
  fileId:      number;
  ncId:        number;
  processingId?: string | null;
  token:       string;
  onSaved:     () => void;
  onClose:     () => void;
};

export default function ImageEditor({ imageUrl, fileId, ncId, processingId, token, onSaved, onClose }: Props) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const fabricRef  = useRef<any>(null);
  const [saving,   setSaving]   = useState(false);
  const [saveMsg,  setSaveMsg]  = useState<string | null>(null);
  const [tool,     setTool]     = useState<"select"|"text"|"arrow">("select");
  const [color,    setColor]    = useState("#ef4444");

  // Fabric.js 初期化（SSR回避のため動的import）
  useEffect(() => {
    let fabric: any;
    let canvas: any;

    (async () => {
      fabric = (await import("fabric")).fabric;
      if (!canvasRef.current) return;

      canvas = new fabric.Canvas(canvasRef.current, {
        width:           800,
        height:          600,
        backgroundColor: "#1e293b",
        selection:       true,
      });
      fabricRef.current = canvas;

      // 画像読み込み
      fabric.Image.fromURL(
        imageUrl,
        (img: any) => {
          const maxW = 780, maxH = 580;
          const scale = Math.min(maxW / img.width, maxH / img.height, 1);
          img.set({
            left:        (800 - img.width * scale) / 2,
            top:         (600 - img.height * scale) / 2,
            scaleX:      scale,
            scaleY:      scale,
            selectable:  false,
            evented:     false,
          });
          canvas.add(img);
          canvas.sendToBack(img);
        },
        { crossOrigin: "anonymous" },
      );
    })();

    return () => { canvas?.dispose(); };
  }, [imageUrl]);

  // ツール切替
  useEffect(() => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    canvas.isDrawingMode = false;
    canvas.selection     = tool === "select";
  }, [tool]);

  // キャンバスクリック → テキスト/矢印追加
  const handleCanvasClick = useCallback(async (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = fabricRef.current;
    if (!canvas || tool === "select") return;

    const fabric = (await import("fabric")).fabric;
    const rect   = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (tool === "text") {
      const txt = new fabric.IText("テキスト", {
        left: x, top: y, fontSize: 20, fill: color,
        fontFamily: "sans-serif", fontWeight: "bold",
        stroke: "#000", strokeWidth: 0.5,
      });
      canvas.add(txt);
      canvas.setActiveObject(txt);
      txt.enterEditing();
    } else if (tool === "arrow") {
      const len = 80;
      const arrow = new fabric.Group([
        new fabric.Line([0, 0, len, 0], { stroke: color, strokeWidth: 3 }),
        new fabric.Triangle({
          width: 14, height: 14, fill: color,
          left: len - 7, top: -7, angle: 90,
        }),
      ], { left: x, top: y, selectable: true });
      canvas.add(arrow);
    }
    canvas.renderAll();
  }, [tool, color]);

  // 回転
  const rotate = (deg: number) => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject();
    if (obj) {
      obj.rotate((obj.angle + deg) % 360);
      canvas.renderAll();
    } else {
      // 全体回転: 画像オブジェクトのみ対象
      canvas.getObjects().forEach((o: any) => {
        if (o.type === "image") { o.rotate((o.angle + deg) % 360); }
      });
      canvas.renderAll();
    }
  };

  // 選択オブジェクト削除
  const deleteSelected = () => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject();
    if (obj) { canvas.remove(obj); canvas.renderAll(); }
  };

  // 保存
  const handleSave = async () => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    setSaving(true); setSaveMsg(null);

    try {
      // PNG として Base64 出力
      const dataUrl = canvas.toDataURL({ format: "png", quality: 1, multiplier: 1 });
      const blob    = await (await fetch(dataUrl)).blob();
      const fd      = new FormData();
      fd.append("image", blob, "edited.png");
      fd.append("nc_program_id", String(ncId));
      fd.append("processing_id", processingId ?? "");

      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiBase}/files/${fileId}/save-edited`, {
        method:  "POST",
        headers: { Authorization: `Bearer ${token}` },
        body:    fd,
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.message ?? `HTTP ${res.status}`);
      }
      setSaveMsg("✅ 保存しました");
      setTimeout(() => { onSaved(); onClose(); }, 1200);
    } catch (e: any) {
      setSaveMsg(`⚠️ ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const btnCls = (active?: boolean) =>
    `px-3 py-1.5 text-xs rounded-lg font-bold transition-colors ${
      active
        ? "bg-sky-600 text-white"
        : "bg-slate-700 text-slate-200 hover:bg-slate-600"
    }`;

  return (
    <div className="fixed inset-0 z-[60] bg-black/90 flex items-center justify-center p-4">
      <div className="bg-slate-800 rounded-xl shadow-2xl flex flex-col max-w-5xl w-full max-h-[95vh]">
        {/* ヘッダー */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <span className="text-white font-bold text-sm">✏️ 画像編集</span>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg">✕</button>
        </div>

        {/* ツールバー */}
        <div className="flex items-center flex-wrap gap-2 px-4 py-2 border-b border-slate-700">
          <span className="text-xs text-slate-400">ツール:</span>
          <button onClick={() => setTool("select")} className={btnCls(tool === "select")}>▶ 選択</button>
          <button onClick={() => setTool("text")}   className={btnCls(tool === "text")}>T テキスト</button>
          <button onClick={() => setTool("arrow")}  className={btnCls(tool === "arrow")}>→ 矢印</button>
          <div className="border-l border-slate-600 mx-1 self-stretch" />
          <span className="text-xs text-slate-400">色:</span>
          {["#ef4444","#f59e0b","#22c55e","#3b82f6","#ffffff","#000000"].map(c => (
            <button key={c} onClick={() => setColor(c)}
              className={`w-6 h-6 rounded-full border-2 ${color === c ? "border-white" : "border-transparent"}`}
              style={{ background: c }} />
          ))}
          <div className="border-l border-slate-600 mx-1 self-stretch" />
          <span className="text-xs text-slate-400">回転:</span>
          <button onClick={() => rotate(-90)} className={btnCls()}>↺ -90°</button>
          <button onClick={() => rotate(90)}  className={btnCls()}>↻ +90°</button>
          <button onClick={deleteSelected}    className="px-3 py-1.5 text-xs rounded-lg font-bold bg-red-800 text-red-200 hover:bg-red-700 transition-colors">
            🗑 削除
          </button>
          <div className="ml-auto flex items-center gap-2">
            {saveMsg && <span className="text-xs text-slate-300">{saveMsg}</span>}
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-1.5 text-xs rounded-lg font-bold bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white transition-colors">
              {saving ? "保存中…" : "💾 保存"}
            </button>
          </div>
        </div>

        {/* キャンバス */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-2 min-h-0">
          <canvas
            ref={canvasRef}
            onClick={handleCanvasClick}
            style={{ border: "1px solid #334155", borderRadius: "8px", cursor: tool === "select" ? "default" : "crosshair" }}
          />
        </div>

        <p className="text-[10px] text-slate-500 text-center pb-2">
          テキスト: クリックで追加 → ダブルクリックで編集 ／ 矢印: クリックで追加 ／ 回転: 画像全体または選択オブジェクト
        </p>
      </div>
    </div>
  );
}
