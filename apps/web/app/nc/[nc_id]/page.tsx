"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import axios from "axios";

export default function NcDetailPage() {
  const { nc_id } = useParams();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    axios.get(`/api/nc/${nc_id}`)
      .then(r => setData(r.data))
      .catch(e => setError(e.message));
  }, [nc_id]);

  return (
    <div className="min-h-screen bg-slate-50 p-6 font-mono">
      <button
        onClick={() => router.push("/nc/search")}
        className="mb-4 text-sky-600 hover:underline text-sm"
      >
        ← 検索結果に戻る
      </button>

      <h1 className="text-xl font-bold text-slate-700 mb-4">
        NC 詳細 — NC#{nc_id}
      </h1>

      {error && <div className="text-red-500">{error}</div>}

      {data && (
        <pre className="bg-white border border-slate-200 rounded-xl p-4 text-xs overflow-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}

      {!data && !error && (
        <div className="text-slate-400">読み込み中...</div>
      )}
    </div>
  );
}
