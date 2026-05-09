"use client";
import { useState, useEffect } from "react";
import { usersApi, authApi, UserInfo } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";

type Props = {
  isOpen: boolean;
  sessionType: string;
  ncProgramId: number;
  onSuccess: () => void;
  onCancel: () => void;
};

export default function AuthModal({ isOpen, sessionType, ncProgramId, onSuccess, onCancel }: Props) {
  const { login } = useAuth();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserInfo | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      usersApi.list().then(r => setUsers(r.data)).catch(() => {});
      setSelectedUser(null);
      setPassword("");
      setError(null);
    }
  }, [isOpen]);

  const handleSubmit = async () => {
    if (!selectedUser || !password) return;
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.createWorkSession({
        operator_id: selectedUser.id,
        password,
        session_type: sessionType,
        nc_program_id: ncProgramId,
        mc_program_id: mcProgramId,
      });
      login(res.data);
      onSuccess();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "認証に失敗しました";
      setError(Array.isArray(msg) ? msg.join(", ") : msg);
      setPassword("");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const SESSION_LABELS: Record<string, string> = {
    edit: "変更・登録",
    setup_print: "段取シート印刷",
    work_record: "作業記録",
    usb_download: "PG書き出し",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* ヘッダー */}
        <div className="bg-slate-800 px-6 py-4">
          <h2 className="text-white font-bold text-lg">作業を開始する</h2>
          <p className="text-slate-400 text-xs mt-1">
            {SESSION_LABELS[sessionType] ?? sessionType} — 担当者を選択してパスワードを入力してください
          </p>
        </div>

        <div className="p-6 space-y-5">
          {/* 担当者選択 */}
          <div>
            <p className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">担当者</p>
            <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
              {users.map(u => (
                <button
                  key={u.id}
                  onClick={() => { setSelectedUser(u); setError(null); }}
                  className={`px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                    selectedUser?.id === u.id
                      ? "border-sky-500 bg-sky-50 text-sky-700"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                  }`}
                >
                  {u.name}
                </button>
              ))}
            </div>
          </div>

          {/* パスワード入力 */}
          {selectedUser && (
            <div>
              <p className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">
                パスワード（{selectedUser.name}）
              </p>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmit()}
                autoFocus
                className="w-full border border-slate-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                placeholder="パスワードを入力"
              />
            </div>
          )}

          {/* エラー */}
          {error && (
            <p className="text-red-600 text-sm bg-red-50 rounded-lg px-4 py-2">{error}</p>
          )}

          {/* ボタン */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium hover:bg-slate-50"
            >
              キャンセル
            </button>
            <button
              onClick={handleSubmit}
              disabled={!selectedUser || !password || loading}
              className="flex-1 px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold hover:bg-sky-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? "確認中..." : "確認してこの作業を開始する"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
