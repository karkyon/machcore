"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { adminAuthApi } from "../../../lib/api";

export default function AdminLoginPage() {
  const router = useRouter();
  const [employeeCode, setEmployeeCode] = useState("");
  const [password, setPassword]         = useState("");
  const [error, setError]               = useState<string | null>(null);
  const [loading, setLoading]           = useState(false);

  // 既にログイン済みなら /admin/users へリダイレクト
  useEffect(() => {
    if (typeof window !== "undefined" && sessionStorage.getItem("admin_token")) {
      router.replace("/admin/users");
    }
  }, [router]);

  const handleSubmit = async () => {
    if (!employeeCode || !password) {
      setError("社員コードとパスワードを入力してください");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await adminAuthApi.login(employeeCode, password);
      sessionStorage.setItem("admin_token", res.data.access_token);
      sessionStorage.setItem("admin_user",  JSON.stringify(res.data.user));
      router.push("/admin/users");
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "ログインに失敗しました";
      setError(Array.isArray(msg) ? msg.join(", ") : msg);
      setPassword("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 overflow-hidden">

        {/* ヘッダー */}
        <div className="bg-slate-800 px-8 py-6 text-center">
          <div className="text-white text-2xl font-bold tracking-wide">MachCore</div>
          <div className="text-slate-400 text-xs mt-1">管理者ログイン</div>
        </div>

        {/* フォーム */}
        <div className="px-8 py-7 space-y-5">
          <div>
            <label className="block text-xs font-bold text-slate-500 mb-1 uppercase tracking-wide">
              社員コード
            </label>
            <input
              type="text"
              value={employeeCode}
              onChange={e => setEmployeeCode(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              autoFocus
              autoComplete="username"
              placeholder="例: ADMIN001"
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-sky-400"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 mb-1 uppercase tracking-wide">
              パスワード
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              autoComplete="current-password"
              placeholder="パスワードを入力"
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-sky-400"
            />
          </div>

          {error && (
            <p className="text-red-600 text-sm bg-red-50 border border-red-200
                          rounded-lg px-4 py-2">
              {error}
            </p>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full bg-sky-600 hover:bg-sky-700 text-white font-bold
                       rounded-lg py-2.5 text-sm transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "確認中..." : "ログイン"}
          </button>
        </div>

        <div className="border-t border-slate-100 px-8 py-4 text-center">
          <p className="text-xs text-slate-400">管理者アカウントのみログイン可能です</p>
        </div>
      </div>
    </div>
  );
}
